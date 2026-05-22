"""Phase G report builders.

Each builder is a pure function: it takes already-projected layer state
(market snapshot, reaction vectors, decision recommendations, outcome
snapshot, narrative clusters) and composes a frozen report dataclass.

No DB I/O, no Claude calls. Failure mode: lenient — missing inputs yield
neutral defaults rather than raises.
"""

from __future__ import annotations

from domain.decisions.runtime import DecisionRecommendation
from domain.market.models import MarketContextSnapshot
from domain.outcomes.projections import MarketOutcomeSnapshot
from domain.reactions.engine import NarrativeCluster
from domain.reactions.models import ReactionVector
from domain.reports.models import (
    NegotiationBriefing,
    PolicyRiskBrief,
    UnderwritingReport,
)


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def build_underwriting_report(
    *,
    listing_id: str | None,
    asking_price: float | None,
    outcome: MarketOutcomeSnapshot,
    reaction: ReactionVector | None = None,
) -> UnderwritingReport:
    """Compose an underwriting recommendation from outcome + reaction layers."""
    reaction = reaction or ReactionVector()

    sentiment = outcome.neighborhood_sentiment
    friction = outcome.permit_friction or 0.0
    optimism = (reaction.investor_optimism + 1.0) / 2.0
    affordability = (reaction.affordability_pressure + 1.0) / 2.0

    score = _clamp_unit(
        0.4 * (sentiment if sentiment is not None else 0.5)
        + 0.3 * optimism
        + 0.2 * (1.0 - affordability)
        + 0.1 * (1.0 - friction)
    )

    if score >= 0.65:
        recommendation = "buy"
        headline = f"Strong fundamentals for {listing_id or 'listing'}"
    elif score <= 0.35:
        recommendation = "pass"
        headline = f"Headwinds against {listing_id or 'listing'}"
    else:
        recommendation = "hold"
        headline = f"Mixed signals for {listing_id or 'listing'}"

    drivers: list[str] = []
    if outcome.price_change_pct is not None:
        drivers.append(f"price_change={outcome.price_change_pct:.1f}%")
    if outcome.time_on_market_days is not None:
        drivers.append(f"days_on_market={outcome.time_on_market_days}")
    if sentiment is not None:
        drivers.append(f"sentiment={sentiment:.2f}")
    if outcome.concession_rate is not None:
        drivers.append(f"concession={outcome.concession_rate:.1f}%")

    return UnderwritingReport(
        listing_id=listing_id,
        asking_price=asking_price,
        outcome=outcome,
        headline=headline,
        recommendation=recommendation,
        confidence=score,
        drivers=tuple(drivers),
    )


def build_negotiation_briefing(
    *,
    negotiation_id: str | None,
    round_count: int,
    current_state: str,
    decision: DecisionRecommendation | None,
) -> NegotiationBriefing:
    """Compose a negotiation briefing from a decision-runtime recommendation."""
    if decision is None:
        return NegotiationBriefing(
            negotiation_id=negotiation_id,
            round_count=round_count,
            current_state=current_state,
            next_action="await_offer",
            rationale="No decision signal yet — waiting on offer history.",
            spread_percent=None,
            zopa_detected=False,
            top_decision_score=0.0,
        )

    payload = decision.payload or {}
    spread = payload.get("spread_percent")
    spread_value = float(spread) if isinstance(spread, (int, float)) else None

    return NegotiationBriefing(
        negotiation_id=negotiation_id,
        round_count=round_count,
        current_state=current_state,
        next_action=decision.action,
        rationale=decision.rationale or "decision-runtime recommendation",
        spread_percent=spread_value,
        zopa_detected=bool(payload.get("zopa_detected")),
        top_decision_score=float(decision.score),
    )


def build_policy_risk_brief(
    *,
    market: MarketContextSnapshot,
    reaction: ReactionVector,
    outcome: MarketOutcomeSnapshot | None = None,
    narratives: list[NarrativeCluster] | None = None,
    narrative_limit: int = 3,
) -> PolicyRiskBrief:
    """Compose a policy / community-resistance brief for development proposals."""
    resistance = _clamp_unit((reaction.resistance_to_development + 1.0) / 2.0)
    displacement = _clamp_unit((reaction.displacement_concern + 1.0) / 2.0)
    risk = _clamp_unit(0.6 * resistance + 0.4 * displacement)

    if risk >= 0.7:
        recommendation = "expect_pushback"
        headline = "High community resistance projected"
    elif risk >= 0.45:
        recommendation = "engage_community"
        headline = "Material resistance — early outreach advised"
    else:
        recommendation = "proceed"
        headline = "Low community-resistance projection"

    key_narratives: tuple[str, ...] = ()
    if narratives:
        ranked = [
            cluster
            for cluster in narratives
            if cluster.variable
            in ("resistance_to_development", "displacement_concern")
        ]
        ranked.sort(key=lambda cluster: abs(cluster.total_delta), reverse=True)
        key_narratives = tuple(
            sample
            for cluster in ranked[:narrative_limit]
            for sample in cluster.sample_narratives
        )[:narrative_limit]

    permit_friction = outcome.permit_friction if outcome else None
    sentiment = outcome.neighborhood_sentiment if outcome else None

    return PolicyRiskBrief(
        jurisdiction=market.jurisdiction,
        zoning_code=market.zoning_code,
        resistance_score=resistance,
        displacement_risk=displacement,
        permit_friction=permit_friction,
        sentiment=sentiment,
        headline=headline,
        recommendation=recommendation,
        key_narratives=key_narratives,
    )


__all__ = [
    "build_negotiation_briefing",
    "build_policy_risk_brief",
    "build_underwriting_report",
]
