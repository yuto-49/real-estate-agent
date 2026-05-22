"""Built-in decision policies for the Phase E runtime.

Each policy reads :class:`DecisionContext` (market + reaction + actor) and
emits a single :class:`DecisionRecommendation`. Policies are deterministic,
pure-Python, and never raise on missing data — they return ``None`` when the
context lacks enough signal to recommend anything.

The negotiation policy intentionally wraps :func:`build_negotiation_analysis`
and :func:`resolve_offer_action` from ``domain.decisions.negotiation`` so the
live ``agent/negotiation_engine.py`` stays untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from domain.decisions.negotiation import (
    NegotiationAction,
    NegotiationState,
    build_negotiation_analysis,
    resolve_offer_action,
)
from domain.decisions.runtime import DecisionContext, DecisionRecommendation


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True, slots=True)
class NegotiationPolicy:
    """Recommends the next negotiation action from offer history + reaction state."""

    kind: str = "negotiation"

    def evaluate(self, context: DecisionContext) -> DecisionRecommendation | None:
        meta: Mapping[str, Any] = context.metadata or {}
        offer_prices = list(meta.get("offer_prices") or [])
        current_state = meta.get("negotiation_state") or NegotiationState.IDLE
        round_count = int(meta.get("round_count") or 0)

        if not offer_prices:
            return None

        next_action = resolve_offer_action(current_state)
        analysis = build_negotiation_analysis(
            round_count=round_count,
            offer_prices=offer_prices,
        )

        # Score balances how decisive the next move is + reaction-layer pressure.
        willingness = _clamp_unit((context.reaction.willingness_to_transact + 1.0) / 2.0)
        score = 0.4 + 0.4 * willingness
        if analysis.get("zopa_detected"):
            score = max(score, 0.85)
        if analysis.get("broker_mediation_recommended"):
            score = max(score, 0.9)

        action_label = (
            "place_offer" if next_action is NegotiationAction.PLACE_OFFER else "counter"
        )
        if analysis.get("recommendation") == "escalate_to_broker":
            action_label = "escalate_to_broker"
        elif analysis.get("recommendation") == "suggest_split":
            action_label = "suggest_split"

        rationale = (
            f"round={round_count} state={current_state} "
            f"spread={analysis.get('spread_percent')}%"
        )

        return DecisionRecommendation(
            kind=self.kind,
            action=action_label,
            score=score,
            rationale=rationale,
            payload=dict(analysis),
        )


@dataclass(frozen=True, slots=True)
class ListHoldPolicy:
    """Recommends list-now vs hold based on inventory pressure + investor optimism."""

    kind: str = "list_hold"

    def evaluate(self, context: DecisionContext) -> DecisionRecommendation | None:
        inventory = context.market.inventory_pressure
        if inventory is None:
            return None

        optimism = (context.reaction.investor_optimism + 1.0) / 2.0
        displacement = (context.reaction.displacement_concern + 1.0) / 2.0

        list_score = _clamp_unit(0.5 * (1.0 - inventory) + 0.5 * optimism)
        hold_score = _clamp_unit(0.5 * inventory + 0.5 * displacement)

        if list_score >= hold_score:
            return DecisionRecommendation(
                kind=self.kind,
                action="list",
                score=list_score,
                rationale=f"inventory_pressure={inventory:.2f} optimism={optimism:.2f}",
                payload={"list_score": list_score, "hold_score": hold_score},
            )
        return DecisionRecommendation(
            kind=self.kind,
            action="hold",
            score=hold_score,
            rationale=f"inventory_pressure={inventory:.2f} displacement={displacement:.2f}",
            payload={"list_score": list_score, "hold_score": hold_score},
        )


@dataclass(frozen=True, slots=True)
class LeasePolicy:
    """Recommends rent action: hold rent, raise modestly, or freeze."""

    kind: str = "lease"

    def evaluate(self, context: DecisionContext) -> DecisionRecommendation | None:
        if context.market.median_rent is None:
            return None

        affordability = (context.reaction.affordability_pressure + 1.0) / 2.0
        willingness = (context.reaction.willingness_to_transact + 1.0) / 2.0

        if affordability > 0.7:
            return DecisionRecommendation(
                kind=self.kind,
                action="freeze_rent",
                score=_clamp_unit(affordability),
                rationale=f"affordability_pressure={affordability:.2f} — tenant retention risk",
                payload={"affordability": affordability},
            )
        if willingness > 0.6 and affordability < 0.5:
            return DecisionRecommendation(
                kind=self.kind,
                action="raise_rent",
                score=_clamp_unit(willingness * (1.0 - affordability)),
                rationale=f"willingness={willingness:.2f} affordability={affordability:.2f}",
                payload={"willingness": willingness, "affordability": affordability},
            )
        return DecisionRecommendation(
            kind=self.kind,
            action="hold_rent",
            score=0.4,
            rationale="balanced affordability/willingness — no rent move",
            payload={"affordability": affordability, "willingness": willingness},
        )


@dataclass(frozen=True, slots=True)
class ChurnPolicy:
    """Estimates household churn risk from displacement concern + perceived safety."""

    kind: str = "churn"

    def evaluate(self, context: DecisionContext) -> DecisionRecommendation | None:
        if (
            context.reaction.displacement_concern == 0.0
            and context.reaction.perceived_safety == 0.0
        ):
            return None  # no signal at all

        displacement = (context.reaction.displacement_concern + 1.0) / 2.0
        safety = (context.reaction.perceived_safety + 1.0) / 2.0
        risk = _clamp_unit(0.6 * displacement + 0.4 * (1.0 - safety))

        action = "intervene" if risk > 0.6 else "monitor"
        return DecisionRecommendation(
            kind=self.kind,
            action=action,
            score=risk,
            rationale=f"displacement={displacement:.2f} safety={safety:.2f}",
            payload={"risk": risk},
        )


@dataclass(frozen=True, slots=True)
class DevResistancePolicy:
    """Predicts community resistance to new development proposals."""

    kind: str = "dev_resistance"

    def evaluate(self, context: DecisionContext) -> DecisionRecommendation | None:
        resistance = (context.reaction.resistance_to_development + 1.0) / 2.0
        displacement = (context.reaction.displacement_concern + 1.0) / 2.0
        score = _clamp_unit(0.7 * resistance + 0.3 * displacement)

        action = "expect_pushback" if score > 0.6 else "proceed"
        rationale = f"resistance={resistance:.2f} displacement={displacement:.2f}"
        if context.market.zoning_code:
            rationale += f" zoning={context.market.zoning_code}"

        return DecisionRecommendation(
            kind=self.kind,
            action=action,
            score=score,
            rationale=rationale,
            payload={"resistance": resistance, "displacement": displacement},
        )


def default_policies() -> list[Any]:
    """Return the lean built-in policy bundle."""
    return [
        NegotiationPolicy(),
        ListHoldPolicy(),
        LeasePolicy(),
        ChurnPolicy(),
        DevResistancePolicy(),
    ]


__all__ = [
    "ChurnPolicy",
    "DevResistancePolicy",
    "LeasePolicy",
    "ListHoldPolicy",
    "NegotiationPolicy",
    "default_policies",
]
