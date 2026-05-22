"""Investor profile API + recommendation endpoint tests — Phase P4."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import (
    InvestorProfile,
    Property,
    PropertyStatus,
    UserProfile,
)


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_user(db_engine, email: str = "profile@test.com") -> str:
    async with _factory(db_engine)() as s:
        user = UserProfile(name="Profiler", email=email)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user.id


async def _seed_property(
    db_engine,
    *,
    address: str = "123 Main St 60601",
    asking_price: float = 350_000.0,
) -> str:
    async with _factory(db_engine)() as s:
        p = Property(
            address=address,
            asking_price=asking_price,
            property_type="sfr",
            status=PropertyStatus.ACTIVE,
        )
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return p.id


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


def _profile_payload(user_id: str, **overrides):
    body = {
        "user_id": user_id,
        "budget": 500_000,
        "strategy": "buy_and_hold",
        "target_cap_rate": 7.0,
        "target_coc": 8.0,
        "geography": {"zip": "60601"},
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_upsert_profile_creates_row(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post("/api/investor-profile/", json=_profile_payload(user_id))
    app.dependency_overrides.clear()

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["budget"] == 500_000
    assert body["strategy"] == "buy_and_hold"
    assert body["geography"]["zip"] == "60601"


@pytest.mark.asyncio
async def test_upsert_profile_updates_in_place(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r1 = await ac.post("/api/investor-profile/", json=_profile_payload(user_id))
        assert r1.status_code == 201
        r2 = await ac.post(
            "/api/investor-profile/",
            json=_profile_payload(user_id, budget=750_000, strategy="flip"),
        )
    app.dependency_overrides.clear()

    assert r2.status_code == 201, r2.text
    assert r2.json()["budget"] == 750_000
    assert r2.json()["strategy"] == "flip"

    async with _factory(db_engine)() as s:
        rows = (await s.execute(select(InvestorProfile))).scalars().all()
        assert len(rows) == 1, "upsert should not duplicate"


@pytest.mark.asyncio
async def test_get_profile_404_when_missing(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.get(f"/api/investor-profile/?user_id={user_id}")
    app.dependency_overrides.clear()
    assert r.status_code == 404
    assert r.json()["detail"] == "profile_not_found"


@pytest.mark.asyncio
async def test_onboarding_state_reflects_profile(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        # Before saving
        r1 = await ac.get(f"/api/onboarding/state?user_id={user_id}")
        assert r1.json()["has_profile"] is False
        await ac.post("/api/investor-profile/", json=_profile_payload(user_id))
        r2 = await ac.get(f"/api/onboarding/state?user_id={user_id}")
    app.dependency_overrides.clear()

    assert r2.status_code == 200
    assert r2.json()["has_profile"] is True


@pytest.mark.asyncio
async def test_recommend_returns_ranked_properties(db_engine):
    user_id = await _seed_user(db_engine)
    await _seed_property(db_engine, address="A St 60601", asking_price=200_000)
    await _seed_property(db_engine, address="B St 60601", asking_price=400_000)
    await _seed_property(db_engine, address="C St 60615", asking_price=300_000)

    app, ac = await _client(db_engine)
    async with ac:
        await ac.post("/api/investor-profile/", json=_profile_payload(user_id))
        r = await ac.get(f"/api/properties/recommend?user_id={user_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["candidates_considered"] == 3
    # ZIP filter drops C St — only 60601 zips remain
    addresses = [rec["address"] for rec in body["recommendations"]]
    assert all("60601" in addr for addr in addresses)
    # Each card carries non-empty rationale
    for rec in body["recommendations"]:
        assert rec["rationale"]
        assert 0.0 <= rec["score"] <= 1.0


@pytest.mark.asyncio
async def test_recommend_404_when_no_profile(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.get(f"/api/properties/recommend?user_id={user_id}")
    app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_recommend_drops_over_budget(db_engine):
    user_id = await _seed_user(db_engine)
    await _seed_property(db_engine, address="Cheap 60601", asking_price=200_000)
    await _seed_property(db_engine, address="Expensive 60601", asking_price=900_000)

    app, ac = await _client(db_engine)
    async with ac:
        await ac.post(
            "/api/investor-profile/",
            json=_profile_payload(user_id, budget=300_000),
        )
        r = await ac.get(f"/api/properties/recommend?user_id={user_id}")
    app.dependency_overrides.clear()

    addresses = [rec["address"] for rec in r.json()["recommendations"]]
    assert "Expensive 60601" not in " ".join(addresses)
