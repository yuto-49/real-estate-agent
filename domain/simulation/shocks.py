"""Shock-to-reaction-event translators.

Converts ``PolicyShock`` instances into ``ReactionEvent`` tuples that the
reaction engine can consume.
"""

from __future__ import annotations

from domain.reactions.models import ReactionEvent
from domain.simulation.models import PolicyShock

_SHOCK_MAP: dict[str, list[tuple[str, float]]] = {
    "rent_decline": [
        ("affordability_pressure", -3.0),
        ("investor_optimism", 2.0),
        ("willingness_to_transact", 1.5),
    ],
    "expense_spike": [
        ("affordability_pressure", 2.0),
        ("investor_optimism", -1.5),
    ],
    "transit_disruption": [
        ("perceived_safety", 2.0),
        ("trust_in_trajectory", 1.5),
        ("social_proof", 1.0),
    ],
    "rent_regulation": [
        ("affordability_pressure", -2.0),
        ("resistance_to_development", -1.0),
        ("investor_optimism", 3.0),
    ],
    "shield_expiry": [
        ("investor_optimism", -0.3),
        ("willingness_to_transact", -0.15),
    ],
}


def translate_shock(shock: PolicyShock) -> tuple[ReactionEvent, ...]:
    """Translate a *PolicyShock* into zero or more *ReactionEvent* instances."""

    if shock.shock_type == "custom":
        variable = shock.metadata.get("variable", "")
        delta = float(shock.metadata.get("delta", 0))
        if not variable:
            return ()
        return (
            ReactionEvent(
                topic=shock.label or "custom",
                variable=variable,
                delta=delta,
            ),
        )

    mappings = _SHOCK_MAP.get(shock.shock_type)
    if mappings is None:
        return ()

    results: list[ReactionEvent] = []
    for variable, scale in mappings:
        delta = (
            scale
            if shock.shock_type == "shield_expiry"
            else scale * shock.magnitude
        )
        results.append(
            ReactionEvent(
                topic=shock.shock_type,
                variable=variable,
                delta=delta,
                narrative=shock.label or shock.shock_type,
            )
        )
    return tuple(results)
