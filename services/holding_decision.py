"""Holding decision service — Phase S1.

Pure-ish orchestration of the layered domain runtime for a single holding.
Extracted from ``api/decisions.py`` so both the read endpoint and the
portfolio summary aggregator (Phase S2) can share one implementation.

The function still owns the I/O of building the market snapshot (which has
to read ``market_signals``) but takes pre-loaded ``PortfolioHolding`` +
``HoldingFinancials`` so callers that already have them in hand do not
round-trip the database again.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import DecisionCandidate, HoldingDecisionResponse
from db.models import HoldingFinancials, MarketSignal, PortfolioHolding
from domain.decisions.policies import ChurnPolicy, LeasePolicy, ListHoldPolicy
from domain.decisions.runtime import (
    DecisionContext,
    DecisionRecommendation,
    DecisionRuntime,
)
from domain.market.models import MarketContextSnapshot
from domain.reactions.models import ReactionVector
from services.market_state import build_snapshot

# Investor-facing action labels.
HOLD = "HOLD"
RAISE_RENT = "RAISE_RENT"
REFI = "REFI"
SELL = "SELL"
IMPROVE = "IMPROVE"

INVESTOR_ACTIONS: frozenset[str] = frozenset({HOLD, RAISE_RENT, REFI, SELL, IMPROVE})

# Refinance benchmark — flag a holding for REFI when its note rate clears this.
_REFI_RATE_THRESHOLD = 0.06

# Maps each decision policy's action label onto an investor action.
_POLICY_ACTION_MAP: dict[str, str] = {
    "list": SELL,
    "hold": HOLD,
    "raise_rent": RAISE_RENT,
    "hold_rent": HOLD,
    "freeze_rent": HOLD,
    "intervene": IMPROVE,
    "monitor": HOLD,
}

_SCALAR_SIGNAL_FIELDS = {
    "transit_score": "transit_score",
    "school_score": "school_score",
    "safety_score": "safety_score",
    "median_rent": "median_rent",
    "median_sale_price": "median_sale_price",
    "inventory_pressure": "inventory_pressure",
}


def _clamp_unit(value: float) -> float:
    return max(-1.0, min(1.0, value))


async def _snapshot_from_zip(
    db: AsyncSession, zip_code: str
) -> MarketContextSnapshot:
    """Build a minimal snapshot from neighborhood signals for an off-platform holding."""
    rows = (
        await db.execute(
            select(MarketSignal)
            .where(MarketSignal.subject_type == "neighborhood")
            .where(MarketSignal.subject_id == zip_code)
            .order_by(MarketSignal.observed_at.desc())
        )
    ).scalars().all()

    kwargs: dict[str, object] = {"zip_code": zip_code}
    seen: set[str] = set()
    for row in rows:
        field = _SCALAR_SIGNAL_FIELDS.get(row.signal_type)
        if field and field not in seen and row.value is not None:
            kwargs[field] = float(row.value)
            seen.add(field)
    return MarketContextSnapshot(**kwargs)


def _derive_reaction(
    market: MarketContextSnapshot, fin: HoldingFinancials | None
) -> ReactionVector:
    """Project a lenient reaction vector from observable market + financial signals."""
    kwargs: dict[str, float] = {}

    if market.inventory_pressure is not None:
        slack = _clamp_unit(1.0 - 2.0 * market.inventory_pressure)
        kwargs["investor_optimism"] = slack
        kwargs["willingness_to_transact"] = slack

    if market.safety_score is not None:
        safety = _clamp_unit(market.safety_score / 5.0 - 1.0)
        kwargs["perceived_safety"] = safety
        kwargs["displacement_concern"] = _clamp_unit(-safety)

    if market.median_rent and fin and fin.monthly_rent:
        gap = (fin.monthly_rent - market.median_rent) / market.median_rent
        kwargs["affordability_pressure"] = _clamp_unit(gap)

    return ReactionVector(**kwargs)


def _refi_candidate(fin: HoldingFinancials | None) -> DecisionCandidate | None:
    if fin is None or fin.interest_rate is None or not fin.loan_balance:
        return None
    if fin.interest_rate <= _REFI_RATE_THRESHOLD:
        return None
    gap = fin.interest_rate - _REFI_RATE_THRESHOLD
    score = min(1.0, 0.3 + gap * 10.0)
    return DecisionCandidate(
        action=REFI,
        score=round(score, 4),
        rationale=(
            f"note rate {fin.interest_rate:.3f} exceeds "
            f"{_REFI_RATE_THRESHOLD:.3f} benchmark on "
            f"${fin.loan_balance:,.0f} balance"
        ),
        source="financial_heuristic",
    )


def _map_policy_rec(rec: DecisionRecommendation) -> DecisionCandidate | None:
    action = _POLICY_ACTION_MAP.get(rec.action)
    if action is None:
        return None
    return DecisionCandidate(
        action=action,
        score=round(_clamp_unit(rec.score), 4) if rec.score < 0 else round(rec.score, 4),
        rationale=rec.rationale or f"{rec.kind} → {rec.action}",
        source=rec.kind,
    )


async def _resolve_snapshot(
    db: AsyncSession, holding: PortfolioHolding
) -> MarketContextSnapshot | None:
    if holding.property_id:
        snapshot = await build_snapshot(db, holding.property_id)
        if snapshot is not None:
            return snapshot
    if holding.zip_code:
        return await _snapshot_from_zip(db, holding.zip_code)
    return None


async def compute_holding_decision(
    db: AsyncSession,
    holding: PortfolioHolding,
    fin: HoldingFinancials | None,
) -> HoldingDecisionResponse:
    """Run the layered runtime + financial heuristics for one holding.

    The caller is responsible for loading ``holding`` and ``fin``. This
    function only touches the database to resolve the market snapshot.
    """
    snapshot = await _resolve_snapshot(db, holding)

    market_context_available = snapshot is not None and any(
        getattr(snapshot, f) is not None for f in _SCALAR_SIGNAL_FIELDS.values()
    )

    candidates: list[DecisionCandidate] = []

    if snapshot is not None:
        context = DecisionContext(
            market=snapshot,
            reaction=_derive_reaction(snapshot, fin),
        )
        runtime = DecisionRuntime([ListHoldPolicy(), LeasePolicy(), ChurnPolicy()])
        for rec in runtime.evaluate(context):
            mapped = _map_policy_rec(rec)
            if mapped is not None:
                candidates.append(mapped)

    refi = _refi_candidate(fin)
    if refi is not None:
        candidates.append(refi)

    best_by_action: dict[str, DecisionCandidate] = {}
    for cand in candidates:
        existing = best_by_action.get(cand.action)
        if existing is None or cand.score > existing.score:
            best_by_action[cand.action] = cand

    ranked = sorted(best_by_action.values(), key=lambda c: c.score, reverse=True)

    if not ranked:
        ranked = [
            DecisionCandidate(
                action=HOLD,
                score=0.3,
                rationale="insufficient market and financial signal — defaulting to hold",
                source="fallback",
            )
        ]

    top = ranked[0]
    return HoldingDecisionResponse(
        holding_id=holding.id,
        recommendation=top.action,
        score=top.score,
        rationale=top.rationale,
        market_context_available=market_context_available,
        candidates=ranked,
    )
