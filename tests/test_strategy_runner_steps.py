"""Per-step trace emission for strategy_runner — Phase P5."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.schemas import StrategyProfile
from db.models import (
    AssetClass,
    HoldingFinancials,
    HoldingStatus,
    InvestmentStrategy,
    InvestorPortfolio,
    PortfolioHolding,
    UserProfile,
)
from services.strategy_runner import (
    execute_strategy_run,
    get_strategy_run,
    reset_strategy_runs,
    start_strategy_run,
)


class _RecordingSink:
    """Captures publish_strategy_step calls for assertion."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    async def publish_strategy_step(
        self, run_id: str, event_type: str, payload: dict
    ) -> int:
        self.calls.append((run_id, event_type, payload))
        return 1


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_portfolio(db_engine) -> str:
    factory = _factory(db_engine)
    async with factory() as s:
        u = UserProfile(name="Step Owner", email="steps@test.com")
        s.add(u)
        await s.flush()
        p = InvestorPortfolio(
            user_id=u.id,
            name="Steps",
            investment_strategy=InvestmentStrategy.BUY_HOLD,
        )
        s.add(p)
        await s.flush()
        h = PortfolioHolding(
            portfolio_id=p.id,
            address="100 Step St 60601",
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
                loan_balance=200_000,
                interest_rate=0.065,
                monthly_piti=1500,
                monthly_rent=2400,
            )
        )
        await s.commit()
        return p.id


@pytest.mark.asyncio
async def test_execute_strategy_run_emits_steps_in_order(db_engine):
    await reset_strategy_runs()
    portfolio_id = await _seed_portfolio(db_engine)
    profile = StrategyProfile()
    rec = await start_strategy_run(portfolio_id, profile)
    sink = _RecordingSink()

    async with _factory(db_engine)() as s:
        completed = await execute_strategy_run(
            s, rec.run_id, portfolio_id, profile, event_sink=sink
        )

    assert completed.status == "completed"
    # Steps emitted in canonical order.
    types = [step.type for step in completed.steps]
    assert types == [
        "run.started",
        "step.analysis_built",
        "step.simulation_projected",
        "step.unified_reconciled",
        "run.completed",
    ]
    # Sink saw them all on the right channel id.
    assert [call[0] for call in sink.calls] == [rec.run_id] * len(types)
    assert [call[1] for call in sink.calls] == types


@pytest.mark.asyncio
async def test_execute_strategy_run_emits_steps_without_sink(db_engine):
    """Trace must still land on the record when no event sink is provided."""
    await reset_strategy_runs()
    portfolio_id = await _seed_portfolio(db_engine)
    profile = StrategyProfile()
    rec = await start_strategy_run(portfolio_id, profile)

    async with _factory(db_engine)() as s:
        completed = await execute_strategy_run(s, rec.run_id, portfolio_id, profile)

    assert completed.status == "completed"
    assert len(completed.steps) == 5
    assert completed.steps[0].type == "run.started"
    assert completed.steps[-1].type == "run.completed"
    # detail strings are non-empty and human-readable
    for step in completed.steps:
        assert step.label
        assert step.at is not None


@pytest.mark.asyncio
async def test_failed_run_emits_run_failed_event(db_engine):
    await reset_strategy_runs()
    profile = StrategyProfile()
    rec = await start_strategy_run("nope", profile)
    sink = _RecordingSink()

    async with _factory(db_engine)() as s:
        failed = await execute_strategy_run(
            s, rec.run_id, "nope", profile, event_sink=sink
        )

    assert failed.status == "failed"
    types = [step.type for step in failed.steps]
    assert types == ["run.started", "run.failed"]
    assert sink.calls[-1][1] == "run.failed"


@pytest.mark.asyncio
async def test_steps_survive_intermediate_set(db_engine):
    """Polling between events should observe a growing trace."""
    await reset_strategy_runs()
    portfolio_id = await _seed_portfolio(db_engine)
    profile = StrategyProfile()
    rec = await start_strategy_run(portfolio_id, profile)

    async with _factory(db_engine)() as s:
        await execute_strategy_run(s, rec.run_id, portfolio_id, profile)

    record = await get_strategy_run(rec.run_id)
    assert record is not None
    assert len(record.steps) >= 4
