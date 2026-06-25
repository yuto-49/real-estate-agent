"""Strategy-run domain-event audit tests.

Every strategy run is a state change and must be recorded in ``domain_events``
with the request correlation id (CLAUDE.md critical pattern #1). These tests
exercise the ``execute_strategy_run`` audit path directly against the DB.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.schemas import StrategyProfile
from db.models import (
    HoldingFinancials,
    InvestorPortfolio,
    PortfolioHolding,
    UserProfile,
)
from services.event_store import EventStore
from services.strategy_runner import (
    execute_strategy_run,
    reset_strategy_runs,
    start_strategy_run,
)


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_portfolio(db_engine, *, tag: str) -> str:
    factory = _factory(db_engine)
    async with factory() as s:
        user = UserProfile(name="Investor", email=f"events-{tag}@t.com")
        s.add(user)
        await s.flush()
        portfolio = InvestorPortfolio(user_id=user.id, name=tag)
        s.add(portfolio)
        await s.flush()
        holding = PortfolioHolding(
            portfolio_id=portfolio.id, address="1 Audit St", zip_code="60601"
        )
        s.add(holding)
        await s.flush()
        s.add(
            HoldingFinancials(
                holding_id=holding.id,
                current_value_estimate=400_000.0,
                loan_balance=200_000.0,
                interest_rate=0.04,
                monthly_piti=1_400.0,
                monthly_rent=2_400.0,
                vacancy_rate=0.05,
                monthly_opex_estimate=200.0,
                property_tax_annual=6_000.0,
                insurance_annual=1_200.0,
            )
        )
        await s.commit()
        return portfolio.id


@pytest.mark.asyncio
async def test_execute_strategy_run_writes_started_and_completed_events(db_engine):
    await reset_strategy_runs()
    portfolio_id = await _seed_portfolio(db_engine, tag="ok")
    profile = StrategyProfile()
    record = await start_strategy_run(portfolio_id, profile)

    factory = _factory(db_engine)
    async with factory() as s:
        await execute_strategy_run(
            s, record.run_id, portfolio_id, profile, correlation_id="cid-ok"
        )

    async with factory() as s:
        events = await EventStore(s).get_by_correlation("cid-ok")

    types = {e.event_type for e in events}
    assert "strategy.run_started" in types
    assert "strategy.run_completed" in types
    assert events, "expected audit events"
    assert all(e.aggregate_type == "strategy_run" for e in events)
    assert all(e.aggregate_id == record.run_id for e in events)


@pytest.mark.asyncio
async def test_execute_strategy_run_writes_failure_event_for_missing_portfolio(db_engine):
    await reset_strategy_runs()
    profile = StrategyProfile()
    record = await start_strategy_run("missing", profile)

    factory = _factory(db_engine)
    async with factory() as s:
        await execute_strategy_run(
            s, record.run_id, "missing", profile, correlation_id="cid-fail"
        )

    async with factory() as s:
        events = await EventStore(s).get_by_correlation("cid-fail")

    types = {e.event_type for e in events}
    assert "strategy.run_started" in types
    assert "strategy.run_failed" in types
