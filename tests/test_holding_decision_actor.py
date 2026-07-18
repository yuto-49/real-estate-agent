"""Service-level tests for the actor → reaction → decision pipeline.

These exercise ``services.holding_decision.compute_holding_decision`` directly
against an in-memory session (no slow ASGITransport) to prove the holding
decision now reflects the owner's actor signals — derived through
``domain/actors`` + ``domain/reactions`` — and not just a market heuristic.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import (
    HoldingFinancials,
    InvestorPortfolio,
    MarketSignal,
    PortfolioHolding,
    UserProfile,
)
from services.holding_decision import compute_holding_decision


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed(
    db_engine,
    *,
    email: str,
    budget_min: float | None = None,
    budget_max: float | None = None,
    zip_code: str | None = "60615",
    monthly_rent: float | None = 2_400.0,
    with_signals: bool = True,
) -> tuple[str, str]:
    """Seed owner + portfolio + holding + financials (+ neighborhood signals).

    Returns ``(holding_id, portfolio_id)``.
    """
    async with _factory(db_engine)() as s:
        owner = UserProfile(
            name="Investor",
            email=email,
            role="investor",
            budget_min=budget_min,
            budget_max=budget_max,
        )
        s.add(owner)
        await s.flush()

        portfolio = InvestorPortfolio(user_id=owner.id, name="P")
        s.add(portfolio)
        await s.flush()

        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            address="123 Test St, Chicago, IL 60615",
            zip_code=zip_code,
        )
        s.add(holding)
        await s.flush()

        s.add(
            HoldingFinancials(
                holding_id=holding.id,
                interest_rate=0.04,  # below REFI benchmark — keep REFI out of the way
                loan_balance=250_000.0,
                monthly_rent=monthly_rent,
                current_value_estimate=400_000.0,
            )
        )

        if zip_code and with_signals:
            for signal_type, value in (
                ("inventory_pressure", 0.2),
                ("median_rent", 2_000.0),
                ("safety_score", 7.5),
            ):
                s.add(
                    MarketSignal(
                        signal_type=signal_type,
                        subject_type="neighborhood",
                        subject_id=zip_code,
                        value=value,
                    )
                )
        await s.commit()
        return holding.id, portfolio.id


async def _decide(db_engine, holding_id: str):
    async with _factory(db_engine)() as s:
        holding = (
            await s.execute(
                select(PortfolioHolding).where(PortfolioHolding.id == holding_id)
            )
        ).scalar_one()
        fin = (
            await s.execute(
                select(HoldingFinancials).where(
                    HoldingFinancials.holding_id == holding_id
                )
            )
        ).scalar_one()
        return await compute_holding_decision(s, holding, fin)


def _score_for(decision, action: str) -> float | None:
    for cand in decision.candidates:
        if cand.action == action:
            return cand.score
    return None


@pytest.mark.asyncio
async def test_owner_budget_pressure_shifts_decision(db_engine):
    """A tight-budget owner raises affordability pressure → stronger HOLD signal.

    Identical market + financials; only the owner's budget spread differs. The
    affordability pressure flows owner → actor signals → reaction vector →
    LeasePolicy, so the tight-budget holding's HOLD candidate must outscore the
    wide-budget one. If the reaction were still market-only, the two would be
    identical.
    """
    tight_id, _ = await _seed(
        db_engine, email="tight@t.com", budget_min=900_000.0, budget_max=1_000_000.0
    )
    wide_id, _ = await _seed(
        db_engine, email="wide@t.com", budget_min=0.0, budget_max=1_000_000.0
    )

    tight = await _decide(db_engine, tight_id)
    wide = await _decide(db_engine, wide_id)

    tight_hold = _score_for(tight, "HOLD")
    wide_hold = _score_for(wide, "HOLD")

    assert tight_hold is not None and wide_hold is not None
    assert tight_hold > wide_hold, (
        f"owner actor signals not influencing decision: "
        f"tight={tight_hold} wide={wide_hold}"
    )


@pytest.mark.asyncio
async def test_decision_lenient_without_market_context(db_engine):
    """No zip / no signals → no snapshot → falls back gracefully, never raises."""
    holding_id, _ = await _seed(
        db_engine, email="nomkt@t.com", zip_code=None, with_signals=False
    )
    decision = await _decide(db_engine, holding_id)

    assert decision.market_context_available is False
    assert decision.recommendation in {"HOLD", "RAISE_RENT", "REFI", "SELL", "IMPROVE"}
    assert 0.0 <= decision.score <= 1.0
    assert decision.candidates
