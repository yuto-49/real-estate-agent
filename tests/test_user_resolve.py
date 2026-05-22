"""User identifier resolution (Supabase id ↔ internal id) — onboarding fix."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import InvestorProfile, UserProfile
from services.user_resolve import resolve_user_id, resolve_user_profile


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_user(
    db_engine, *, email: str, supabase_user_id: str | None = None
) -> str:
    async with _factory(db_engine)() as s:
        u = UserProfile(name="U", email=email, supabase_user_id=supabase_user_id)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u.id


# ── unit: resolver ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_by_internal_id(db_engine):
    internal = await _seed_user(db_engine, email="a@test.com")
    async with _factory(db_engine)() as s:
        assert await resolve_user_id(s, internal) == internal


@pytest.mark.asyncio
async def test_resolve_by_supabase_id(db_engine):
    internal = await _seed_user(
        db_engine, email="b@test.com", supabase_user_id="sub-xyz"
    )
    async with _factory(db_engine)() as s:
        assert await resolve_user_id(s, "sub-xyz") == internal


@pytest.mark.asyncio
async def test_resolve_links_supabase_by_email(db_engine):
    internal = await _seed_user(db_engine, email="c@test.com")  # no sub yet
    async with _factory(db_engine)() as s:
        profile = await resolve_user_profile(
            s, "sub-new", email="c@test.com"
        )
        assert profile.id == internal
        assert profile.supabase_user_id == "sub-new"


@pytest.mark.asyncio
async def test_resolve_raises_when_unknown_and_no_email(db_engine):
    async with _factory(db_engine)() as s:
        with pytest.raises(LookupError):
            await resolve_user_id(s, "ghost-id")


@pytest.mark.asyncio
async def test_resolve_auto_creates_with_email(db_engine):
    async with _factory(db_engine)() as s:
        profile = await resolve_user_profile(
            s, "sub-fresh", email="fresh@test.com", auto_create=True
        )
        await s.commit()
        assert profile.supabase_user_id == "sub-fresh"
        assert profile.email == "fresh@test.com"

    async with _factory(db_engine)() as s:
        rows = (await s.execute(select(UserProfile))).scalars().all()
        assert any(r.supabase_user_id == "sub-fresh" for r in rows)


# ── integration: wizard endpoint accepts a Supabase id ──────────────────


async def _client(db_engine):
    from db.database import get_db
    from main import app

    factory = _factory(db_engine)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    return app, AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_investor_profile_accepts_supabase_id(db_engine):
    """The wizard sends the Supabase id; the endpoint must resolve it."""
    await _seed_user(db_engine, email="wiz@test.com", supabase_user_id="sub-wiz")
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post(
            "/api/investor-profile/",
            json={
                "user_id": "sub-wiz",  # Supabase id, not internal
                "budget": 500000,
                "strategy": "buy_and_hold",
                "target_cap_rate": 7,
                "target_coc": 8,
                "geography": {"zip": "60601"},
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 201, r.text
    async with _factory(db_engine)() as s:
        prof = (await s.execute(select(InvestorProfile))).scalar_one()
        # Stored against the internal id, not the Supabase id.
        assert prof.user_id != "sub-wiz"


@pytest.mark.asyncio
async def test_investor_profile_auto_provisions_for_new_supabase_user(db_engine):
    """A signed-in Supabase user with no UserProfile gets one auto-created."""
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post(
            "/api/investor-profile/",
            json={
                "user_id": "sub-brandnew",
                "user_email": "brandnew@test.com",
                "budget": 400000,
                "strategy": "flip",
                "target_cap_rate": 9,
                "target_coc": 10,
                "geography": {"city": "Chicago"},
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 201, r.text
    async with _factory(db_engine)() as s:
        users = (await s.execute(select(UserProfile))).scalars().all()
        assert any(u.supabase_user_id == "sub-brandnew" for u in users)


@pytest.mark.asyncio
async def test_investor_profile_404_when_no_email_and_unknown(db_engine):
    """Unknown id with no email can't auto-provision → user_not_found."""
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post(
            "/api/investor-profile/",
            json={
                "user_id": "sub-unknown",
                "budget": 400000,
                "strategy": "flip",
                "target_cap_rate": 9,
                "target_coc": 10,
                "geography": {"city": "Chicago"},
            },
        )
    app.dependency_overrides.clear()
    assert r.status_code == 404
    assert r.json()["detail"] == "user_not_found"
