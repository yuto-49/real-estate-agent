"""Onboarding state endpoint tests — Phase P1."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import InvestorPortfolio, PortfolioHolding, UserProfile


def _session_factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_user(db_engine, email: str = "wizard@test.com") -> str:
    factory = _session_factory(db_engine)
    async with factory() as s:
        user = UserProfile(name="Wizard", email=email)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user.id


async def _seed_user_with_holding(db_engine) -> str:
    factory = _session_factory(db_engine)
    user_id = await _seed_user(db_engine, email="holder@test.com")
    async with factory() as s:
        portfolio = InvestorPortfolio(user_id=user_id, name="Test", investment_strategy="buy_hold")
        s.add(portfolio)
        await s.flush()
        s.add(
            PortfolioHolding(
                portfolio_id=portfolio.id,
                address="123 Main St",
                zip_code="60601",
            )
        )
        await s.commit()
    return user_id


async def _client(db_engine):
    from db.database import get_db
    from main import app

    factory = _session_factory(db_engine)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    return app, AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_state_without_user_id_is_lenient(db_engine):
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.get("/api/onboarding/state")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"user_id": None, "has_portfolio": False, "has_profile": False}


@pytest.mark.asyncio
async def test_state_user_without_holdings(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.get(f"/api/onboarding/state?user_id={user_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == user_id
    assert body["has_portfolio"] is False
    assert body["has_profile"] is False


@pytest.mark.asyncio
async def test_state_user_with_holdings(db_engine):
    user_id = await _seed_user_with_holding(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.get(f"/api/onboarding/state?user_id={user_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == user_id
    assert body["has_portfolio"] is True
