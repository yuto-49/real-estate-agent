"""Holding decision API tests — Phase P4."""

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


def _client_factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_holding(
    db_engine,
    *,
    zip_code: str | None = "60615",
    interest_rate: float | None = 0.085,
    loan_balance: float | None = 280_000.0,
    monthly_rent: float | None = 2_400.0,
    inventory_pressure: float | None = 0.2,
    median_rent: float | None = 2_000.0,
    safety_score: float | None = 7.5,
) -> str:
    """Create a portfolio + holding + financials + neighborhood signals."""
    factory = _client_factory(db_engine)
    async with factory() as s:
        user = UserProfile(name="Investor", email=f"inv-{zip_code}-{loan_balance}@t.com")
        s.add(user)
        await s.flush()

        portfolio = InvestorPortfolio(user_id=user.id, name="P")
        s.add(portfolio)
        await s.flush()

        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            address="123 Test St, Chicago, IL 60615",
            zip_code=zip_code,
        )
        s.add(holding)
        await s.flush()

        fin = HoldingFinancials(
            holding_id=holding.id,
            interest_rate=interest_rate,
            loan_balance=loan_balance,
            monthly_rent=monthly_rent,
            current_value_estimate=400_000.0,
        )
        s.add(fin)

        if zip_code:
            if inventory_pressure is not None:
                s.add(
                    MarketSignal(
                        signal_type="inventory_pressure",
                        subject_type="neighborhood",
                        subject_id=zip_code,
                        value=inventory_pressure,
                    )
                )
            if median_rent is not None:
                s.add(
                    MarketSignal(
                        signal_type="median_rent",
                        subject_type="neighborhood",
                        subject_id=zip_code,
                        value=median_rent,
                    )
                )
            if safety_score is not None:
                s.add(
                    MarketSignal(
                        signal_type="safety_score",
                        subject_type="neighborhood",
                        subject_id=zip_code,
                        value=safety_score,
                    )
                )
        await s.commit()
        return holding.id


def _override_db(db_engine):
    from db.database import get_db
    from main import app

    factory = _client_factory(db_engine)

    async def override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    return app


@pytest.mark.asyncio
async def test_decision_returns_recommendation(db_engine):
    holding_id = await _seed_holding(db_engine)
    app = _override_db(db_engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/decisions/holding/{holding_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["holding_id"] == holding_id
    assert body["recommendation"] in {"HOLD", "RAISE_RENT", "REFI", "SELL", "IMPROVE"}
    assert 0.0 <= body["score"] <= 1.0
    assert body["rationale"]
    assert isinstance(body["candidates"], list)
    assert body["candidates"]
    for cand in body["candidates"]:
        assert cand["action"] in {"HOLD", "RAISE_RENT", "REFI", "SELL", "IMPROVE"}


@pytest.mark.asyncio
async def test_decision_flags_refi_for_high_rate_loan(db_engine):
    # 8.5% rate on a real loan balance → REFI should be a candidate.
    holding_id = await _seed_holding(db_engine, interest_rate=0.085)
    app = _override_db(db_engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/decisions/holding/{holding_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    actions = {c["action"] for c in r.json()["candidates"]}
    assert "REFI" in actions


@pytest.mark.asyncio
async def test_decision_no_refi_for_low_rate_loan(db_engine):
    holding_id = await _seed_holding(db_engine, interest_rate=0.035)
    app = _override_db(db_engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/decisions/holding/{holding_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    actions = {c["action"] for c in r.json()["candidates"]}
    assert "REFI" not in actions


@pytest.mark.asyncio
async def test_decision_holding_not_found(db_engine):
    app = _override_db(db_engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/decisions/holding/does-not-exist")
    app.dependency_overrides.clear()

    assert r.status_code == 404


@pytest.mark.asyncio
async def test_decision_without_market_context_still_responds(db_engine):
    # No zip → no market signals → policies stay quiet, financial heuristics carry it.
    holding_id = await _seed_holding(db_engine, zip_code=None, interest_rate=0.09)
    app = _override_db(db_engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/decisions/holding/{holding_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["market_context_available"] is False
    assert body["recommendation"] in {"HOLD", "RAISE_RENT", "REFI", "SELL", "IMPROVE"}
