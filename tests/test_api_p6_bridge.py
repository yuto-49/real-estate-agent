"""Phase P6 endpoints: /api/strategy/recent + /api/portfolio/from-property."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.schemas import StrategyProfile
from db.models import (
    AssetClass,
    HoldingFinancials,
    HoldingStatus,
    InvestmentStrategy,
    InvestorPortfolio,
    PortfolioHolding,
    Property,
    PropertyStatus,
    UserProfile,
)
from services.strategy_runner import (
    execute_strategy_run,
    reset_strategy_runs,
    start_strategy_run,
)


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_user(db_engine, email: str = "p6@test.com") -> str:
    async with _factory(db_engine)() as s:
        u = UserProfile(name="P6", email=email)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u.id


async def _seed_property(db_engine, *, address: str = "10 P6 Way 60601") -> str:
    async with _factory(db_engine)() as s:
        p = Property(
            address=address,
            asking_price=300_000.0,
            property_type="sfr",
            status=PropertyStatus.ACTIVE,
        )
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return p.id


async def _seed_portfolio_with_holding(db_engine, user_id: str) -> str:
    async with _factory(db_engine)() as s:
        p = InvestorPortfolio(
            user_id=user_id, name="P6", investment_strategy=InvestmentStrategy.BUY_HOLD
        )
        s.add(p)
        await s.flush()
        h = PortfolioHolding(
            portfolio_id=p.id,
            address="100 P6 Step 60601",
            asset_class=AssetClass.SFR,
            status=HoldingStatus.HELD,
        )
        s.add(h)
        await s.flush()
        s.add(
            HoldingFinancials(
                holding_id=h.id,
                cost_basis=300_000,
                current_value_estimate=350_000,
                monthly_rent=2_400,
            )
        )
        await s.commit()
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


@pytest.mark.asyncio
async def test_from_property_creates_single_holding_portfolio(db_engine):
    user_id = await _seed_user(db_engine)
    property_id = await _seed_property(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post(
            "/api/portfolio/from-property",
            json={"user_id": user_id, "property_id": property_id},
        )
    app.dependency_overrides.clear()

    assert r.status_code == 201, r.text
    portfolio_id = r.json()["id"]

    async with _factory(db_engine)() as s:
        holdings = (
            await s.execute(
                select(PortfolioHolding).where(
                    PortfolioHolding.portfolio_id == portfolio_id
                )
            )
        ).scalars().all()
        assert len(holdings) == 1
        assert holdings[0].property_id == property_id

        fin = (
            await s.execute(
                select(HoldingFinancials).where(
                    HoldingFinancials.holding_id == holdings[0].id
                )
            )
        ).scalar_one()
        assert fin.cost_basis == 300_000.0
        assert fin.value_estimate_source == "listing"


@pytest.mark.asyncio
async def test_from_property_is_idempotent(db_engine):
    user_id = await _seed_user(db_engine)
    property_id = await _seed_property(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r1 = await ac.post(
            "/api/portfolio/from-property",
            json={"user_id": user_id, "property_id": property_id},
        )
        r2 = await ac.post(
            "/api/portfolio/from-property",
            json={"user_id": user_id, "property_id": property_id},
        )
    app.dependency_overrides.clear()

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_from_property_404_when_property_missing(db_engine):
    user_id = await _seed_user(db_engine)
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.post(
            "/api/portfolio/from-property",
            json={
                "user_id": user_id,
                "property_id": "00000000-0000-0000-0000-000000000000",
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 404
    assert r.json()["detail"] == "property_not_found"


@pytest.mark.asyncio
async def test_strategy_recent_returns_user_runs_descending(db_engine):
    await reset_strategy_runs()
    user_id = await _seed_user(db_engine)
    portfolio_id = await _seed_portfolio_with_holding(db_engine, user_id)
    profile = StrategyProfile()
    rec1 = await start_strategy_run(portfolio_id, profile)
    async with _factory(db_engine)() as s:
        await execute_strategy_run(s, rec1.run_id, portfolio_id, profile)
    rec2 = await start_strategy_run(portfolio_id, profile)
    async with _factory(db_engine)() as s:
        await execute_strategy_run(s, rec2.run_id, portfolio_id, profile)

    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.get(f"/api/strategy/recent?user_id={user_id}&limit=10")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    runs = r.json()
    assert len(runs) == 2
    # Newest first.
    assert runs[0]["run_id"] == rec2.run_id
    assert runs[1]["run_id"] == rec1.run_id


@pytest.mark.asyncio
async def test_strategy_recent_filters_to_user_portfolios(db_engine):
    await reset_strategy_runs()
    user_a = await _seed_user(db_engine, email="a@p6.test")
    user_b = await _seed_user(db_engine, email="b@p6.test")
    portfolio_a = await _seed_portfolio_with_holding(db_engine, user_a)
    portfolio_b = await _seed_portfolio_with_holding(db_engine, user_b)
    profile = StrategyProfile()

    rec_a = await start_strategy_run(portfolio_a, profile)
    async with _factory(db_engine)() as s:
        await execute_strategy_run(s, rec_a.run_id, portfolio_a, profile)
    rec_b = await start_strategy_run(portfolio_b, profile)
    async with _factory(db_engine)() as s:
        await execute_strategy_run(s, rec_b.run_id, portfolio_b, profile)

    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.get(f"/api/strategy/recent?user_id={user_a}")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    runs = r.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == rec_a.run_id


@pytest.mark.asyncio
async def test_strategy_recent_empty_when_no_portfolios(db_engine):
    await reset_strategy_runs()
    user_id = await _seed_user(db_engine, email="empty@p6.test")
    app, ac = await _client(db_engine)
    async with ac:
        r = await ac.get(f"/api/strategy/recent?user_id={user_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == []
