"""Holding decision service — Phase S1.

Pure-ish orchestration of the layered domain runtime for a single holding.
Extracted from ``api/decisions.py`` so both the read endpoint and the
portfolio summary aggregator (Phase S2) can share one implementation.

The function owns the I/O of building the market snapshot (reading
``market_signals``) and resolving the holding's owner profile, but takes
pre-loaded ``PortfolioHolding`` + ``HoldingFinancials`` so callers that already
have them in hand do not round-trip the database again.

The reaction vector that feeds the decision policies is produced by the real
layered pipeline — ``domain/actors`` (owner → :class:`ActorSignalState` /
cohort) folded through ``domain/reactions`` (:func:`build_reaction_vector`) —
rather than a hand-built heuristic. All projection math stays pure in
``domain/``; this module only performs the I/O and assembly.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import DecisionCandidate, HoldingDecisionResponse
from db.models import (
    HoldingFinancials,
    InvestorPortfolio,
    MarketSignal,
    PortfolioHolding,
    UserProfile,
)
from domain.actors.profiles import (
    ActorSignalState,
    cohort_signals,
    infer_actor_type,
    user_profile_signals,
)
from domain.decisions.policies import ChurnPolicy, LeasePolicy, ListHoldPolicy
from domain.decisions.runtime import (
    DecisionContext,
    DecisionRecommendation,
    DecisionRuntime,
)
from domain.market.models import MarketContextSnapshot
from domain.reactions.derive import build_reaction_vector
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


async def _load_owner_profile(
    db: AsyncSession, holding: PortfolioHolding
) -> UserProfile | None:
    """Resolve the investor who owns ``holding`` (holding → portfolio → user).

    Lenient: a holding without a resolvable owner returns ``None`` so the
    decision falls back to a market-only reaction.
    """
    if not holding.portfolio_id:
        return None
    return (
        await db.execute(
            select(UserProfile)
            .join(InvestorPortfolio, InvestorPortfolio.user_id == UserProfile.id)
            .where(InvestorPortfolio.id == holding.portfolio_id)
        )
    ).scalar_one_or_none()


def _build_actor_state(
    owner: UserProfile | None, *, label: str
) -> ActorSignalState | None:
    """Project the owner profile into a cohort actor state via the actors layer.

    Wraps the single owner in a one-member cohort so the same path extends to a
    real tenant/peer cohort later. Returns ``None`` when there is no owner to
    project, which the reaction bridge treats as a market-only signal.
    """
    if owner is None:
        return None
    actor_type = infer_actor_type(owner)
    investor_signals = user_profile_signals(owner)
    return cohort_signals([investor_signals], actor_type=actor_type, label=label)


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
    function touches the database only to resolve the market snapshot and the
    holding's owner profile, then delegates the pure scoring to
    :func:`compute_holding_decision_preloaded`. Batch callers that already have
    the snapshot + owner in hand should call that function directly to avoid the
    per-holding round-trips.
    """
    snapshot = await _resolve_snapshot(db, holding)
    owner = await _load_owner_profile(db, holding) if snapshot is not None else None
    return compute_holding_decision_preloaded(
        holding, fin, snapshot=snapshot, owner=owner
    )


def compute_holding_decision_preloaded(
    holding: PortfolioHolding,
    fin: HoldingFinancials | None,
    *,
    snapshot: MarketContextSnapshot | None,
    owner: UserProfile | None,
) -> HoldingDecisionResponse:
    """Pure decision scoring over preloaded inputs — no database access.

    Identical logic to :func:`compute_holding_decision`, but the market snapshot
    and owner profile are supplied by the caller (resolved in bulk). ``owner`` is
    consulted only when ``snapshot`` is present, mirroring the I/O wrapper.
    """
    market_context_available = snapshot is not None and any(
        getattr(snapshot, f) is not None for f in _SCALAR_SIGNAL_FIELDS.values()
    )

    candidates: list[DecisionCandidate] = []

    if snapshot is not None:
        actor_state = _build_actor_state(owner, label=holding.zip_code or "")
        reaction = build_reaction_vector(
            actor_state,
            snapshot,
            monthly_rent=fin.monthly_rent if fin else None,
        )
        context = DecisionContext(
            market=snapshot,
            reaction=reaction,
            actor=actor_state,
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
