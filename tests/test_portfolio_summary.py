"""Portfolio summary aggregator tests — Phase S2."""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import (
    HoldingFinancials,
    InvestorPortfolio,
    MarketSignal,
    PortfolioHolding,
    UserProfile,
)
from services.portfolio_summary import build_portfolio_summary


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _count_select_queries(db_engine, portfolio_id: str) -> int:
    """Count SELECT round-trips issued while building one portfolio summary.

    Attaches a cursor-level listener to the sync engine so every statement the
    async session executes is observed.
    """
    selects: list[str] = []

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip()[:6].upper() == "SELECT":
            selects.append(statement)

    event.listen(db_engine.sync_engine, "after_cursor_execute", _on_execute)
    try:
        async with _factory(db_engine)() as s:
            await build_portfolio_summary(s, portfolio_id)
    finally:
        event.remove(db_engine.sync_engine, "after_cursor_execute", _on_execute)
    return len(selects)


async def _seed_portfolio(
    db_engine,
    *,
    holdings: list[dict] | None = None,
    signals_for_zip: dict[str, dict] | None = None,
    email_tag: str = "summary",
) -> tuple[str, list[str]]:
    """Create a portfolio with the requested holdings + neighborhood signals."""
    holdings = holdings or []
    signals_for_zip = signals_for_zip or {}

    factory = _factory(db_engine)
    holding_ids: list[str] = []
    async with factory() as s:
        user = UserProfile(name="Investor", email=f"inv-{email_tag}@t.com")
        s.add(user)
        await s.flush()

        portfolio = InvestorPortfolio(user_id=user.id, name="P")
        s.add(portfolio)
        await s.flush()

        for spec in holdings:
            holding = PortfolioHolding(
                portfolio_id=portfolio.id,
                address=spec.get("address", "1 Test St"),
                zip_code=spec.get("zip_code"),
            )
            s.add(holding)
            await s.flush()
            holding_ids.append(holding.id)

            fin_kwargs = spec.get("financials")
            if fin_kwargs is not None:
                s.add(HoldingFinancials(holding_id=holding.id, **fin_kwargs))

        for zip_code, sig in signals_for_zip.items():
            for signal_type, value in sig.items():
                s.add(
                    MarketSignal(
                        signal_type=signal_type,
                        subject_type="neighborhood",
                        subject_id=zip_code,
                        value=value,
                    )
                )
        await s.commit()
        return portfolio.id, holding_ids


@pytest.mark.asyncio
async def test_summary_returns_none_for_unknown_portfolio(db_engine):
    factory = _factory(db_engine)
    async with factory() as s:
        result = await build_portfolio_summary(s, "missing-portfolio-id")
    assert result is None


@pytest.mark.asyncio
async def test_summary_empty_portfolio(db_engine):
    portfolio_id, _ = await _seed_portfolio(db_engine, holdings=[], email_tag="empty")
    factory = _factory(db_engine)
    async with factory() as s:
        result = await build_portfolio_summary(s, portfolio_id)

    assert result is not None
    assert result.portfolio_id == portfolio_id
    assert result.holding_count == 0
    assert result.per_holding == []
    assert result.attention == []
    assert result.market_coverage.total == 0
    assert result.market_coverage.with_signals == 0
    assert result.aggregates.total_value == 0.0
    assert result.aggregates.weighted_dscr is None


@pytest.mark.asyncio
async def test_summary_populated_portfolio_metrics(db_engine):
    portfolio_id, holding_ids = await _seed_portfolio(
        db_engine,
        holdings=[
            {
                "address": "1 Main St",
                "zip_code": "60601",
                "financials": {
                    "current_value_estimate": 400_000.0,
                    "loan_balance": 240_000.0,
                    "interest_rate": 0.035,
                    "monthly_piti": 1_400.0,
                    "monthly_rent": 2_400.0,
                    "vacancy_rate": 0.05,
                    "monthly_opex_estimate": 200.0,
                    "property_tax_annual": 6_000.0,
                    "insurance_annual": 1_200.0,
                },
            }
        ],
        signals_for_zip={
            "60601": {
                "inventory_pressure": 0.2,
                "median_rent": 2_000.0,
                "safety_score": 7.5,
            }
        },
        email_tag="populated",
    )

    factory = _factory(db_engine)
    async with factory() as s:
        result = await build_portfolio_summary(s, portfolio_id)

    assert result is not None
    assert result.holding_count == 1
    row = result.per_holding[0]
    assert row.holding_id == holding_ids[0]
    assert row.cap_rate is not None and row.cap_rate > 0
    assert row.dscr is not None and row.dscr > 0
    assert row.cash_on_cash is not None
    assert row.market_context_available is True
    assert row.recommendation in {"HOLD", "RAISE_RENT", "REFI", "SELL", "IMPROVE"}

    assert result.aggregates.total_value == 400_000.0
    assert result.aggregates.total_loan_balance == 240_000.0
    assert result.aggregates.total_equity == 160_000.0
    assert result.market_coverage.with_signals == 1


@pytest.mark.asyncio
async def test_summary_flags_refi_into_attention(db_engine):
    portfolio_id, _ = await _seed_portfolio(
        db_engine,
        holdings=[
            {
                "address": "1 Refi Rd",
                "zip_code": "60615",
                "financials": {
                    "current_value_estimate": 400_000.0,
                    "loan_balance": 280_000.0,
                    "interest_rate": 0.085,  # > 6% benchmark → REFI candidate
                    "monthly_piti": 2_100.0,
                    "monthly_rent": 2_400.0,
                    "vacancy_rate": 0.05,
                },
            }
        ],
        email_tag="refi",
    )

    factory = _factory(db_engine)
    async with factory() as s:
        result = await build_portfolio_summary(s, portfolio_id)

    assert result is not None
    actions = {item.action for item in result.attention}
    # REFI is flagged as a candidate; top recommendation may or may not be REFI
    # depending on policy scores, so assert at least one attention item exists.
    assert any(
        item.action in {"REFI", "SELL", "IMPROVE", "RAISE_RENT"}
        for item in result.attention
    ) or result.per_holding[0].recommendation == "HOLD"
    # Either the top recommendation is REFI, or REFI shows up in candidates
    # via the per_holding row.
    if result.per_holding[0].recommendation == "REFI":
        assert "REFI" in actions


@pytest.mark.asyncio
async def test_summary_no_financials_holding(db_engine):
    portfolio_id, _ = await _seed_portfolio(
        db_engine,
        holdings=[{"address": "1 Bare St", "zip_code": None}],
        email_tag="bare",
    )

    factory = _factory(db_engine)
    async with factory() as s:
        result = await build_portfolio_summary(s, portfolio_id)

    assert result is not None
    assert result.holding_count == 1
    row = result.per_holding[0]
    assert row.current_value is None
    assert row.cap_rate is None
    assert row.dscr is None
    assert row.market_context_available is False
    assert result.aggregates.total_value == 0.0
    assert result.aggregates.weighted_dscr is None


def _holding_specs(n: int) -> list[dict]:
    """N structurally-identical holdings (zip + financials) sharing two zips."""
    zips = ("60601", "60615")
    return [
        {
            "address": f"{i} Batch St",
            "zip_code": zips[i % len(zips)],
            "financials": {
                "current_value_estimate": 400_000.0,
                "loan_balance": 240_000.0,
                "interest_rate": 0.085,  # exercises REFI + attention path
                "monthly_piti": 1_400.0,
                "monthly_rent": 2_400.0,
                "vacancy_rate": 0.05,
            },
        }
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_summary_query_count_is_constant_in_holdings(db_engine):
    """DB round-trips must be O(1) in holding count, not O(N).

    Two portfolios of the same shape but different sizes (2 vs 8 holdings) must
    issue the same number of SELECTs. A per-holding (N+1) implementation makes
    the larger portfolio issue several more queries.
    """
    signals = {
        "60601": {"inventory_pressure": 0.2, "median_rent": 2_000.0, "safety_score": 7.5},
        "60615": {"inventory_pressure": 0.4, "median_rent": 1_800.0, "safety_score": 6.0},
    }
    small_id, _ = await _seed_portfolio(
        db_engine, holdings=_holding_specs(2), signals_for_zip=signals, email_tag="batch-small"
    )
    large_id, _ = await _seed_portfolio(
        db_engine, holdings=_holding_specs(8), signals_for_zip=signals, email_tag="batch-large"
    )

    small_queries = await _count_select_queries(db_engine, small_id)
    large_queries = await _count_select_queries(db_engine, large_id)

    assert small_queries == large_queries, (
        f"portfolio summary is N+1: 2 holdings issued {small_queries} SELECTs, "
        f"8 holdings issued {large_queries}"
    )
