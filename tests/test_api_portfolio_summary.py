"""GET /api/portfolio/{id}/summary endpoint tests — Phase S3."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import (
    HoldingFinancials,
    InvestorPortfolio,
    MarketSignal,
    PortfolioHolding,
    UserProfile,
)


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


def _override_db(db_engine):
    from db.database import get_db
    from main import app

    factory = _factory(db_engine)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    return app


async def _seed_one_holding_portfolio(db_engine, *, email_tag: str) -> str:
    factory = _factory(db_engine)
    async with factory() as s:
        user = UserProfile(name="Investor", email=f"inv-{email_tag}@t.com")
        s.add(user)
        await s.flush()
        portfolio = InvestorPortfolio(user_id=user.id, name="P")
        s.add(portfolio)
        await s.flush()

        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            address="123 Main St, Chicago, IL 60615",
            zip_code="60615",
        )
        s.add(holding)
        await s.flush()
        s.add(
            HoldingFinancials(
                holding_id=holding.id,
                current_value_estimate=400_000.0,
                loan_balance=240_000.0,
                interest_rate=0.085,  # high → REFI flagged
                monthly_piti=2_100.0,
                monthly_rent=2_400.0,
                vacancy_rate=0.05,
                monthly_opex_estimate=200.0,
                property_tax_annual=6_000.0,
                insurance_annual=1_200.0,
            )
        )
        s.add(
            MarketSignal(
                signal_type="inventory_pressure",
                subject_type="neighborhood",
                subject_id="60615",
                value=0.2,
            )
        )
        s.add(
            MarketSignal(
                signal_type="median_rent",
                subject_type="neighborhood",
                subject_id="60615",
                value=2_000.0,
            )
        )
        await s.commit()
        return portfolio.id


@pytest.mark.asyncio
async def test_summary_endpoint_returns_report(db_engine):
    portfolio_id = await _seed_one_holding_portfolio(db_engine, email_tag="ok")
    app = _override_db(db_engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/portfolio/{portfolio_id}/summary")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["portfolio_id"] == portfolio_id
    assert body["holding_count"] == 1
    assert len(body["per_holding"]) == 1
    row = body["per_holding"][0]
    assert row["recommendation"] in {"HOLD", "RAISE_RENT", "REFI", "SELL", "IMPROVE"}
    assert row["cap_rate"] is not None
    assert body["aggregates"]["total_value"] == 400_000.0
    assert body["aggregates"]["total_equity"] == 160_000.0
    assert body["market_coverage"]["total"] == 1
    assert body["market_coverage"]["with_signals"] == 1
    assert "generated_at" in body


@pytest.mark.asyncio
async def test_summary_endpoint_404_for_unknown(db_engine):
    app = _override_db(db_engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/portfolio/missing-portfolio/summary")
    app.dependency_overrides.clear()

    assert r.status_code == 404
