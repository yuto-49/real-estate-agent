from __future__ import annotations

from dataclasses import replace

from domain.reactions.models import ReactionEvent, ReactionVector, REACTION_VARIABLES
from domain.simulation.models import CohortState


def _apply_events(vec: ReactionVector, events: tuple[ReactionEvent, ...]) -> ReactionVector:
    if not events:
        return vec
    updates: dict[str, float] = {}
    for ev in events:
        if ev.variable in REACTION_VARIABLES:
            current = getattr(vec, ev.variable, 0.0)
            updates[ev.variable] = max(-1.0, min(1.0, current + ev.delta))
    return replace(vec, **updates) if updates else vec


def _churn_from_reaction(vec: ReactionVector) -> float:
    raw = (vec.affordability_pressure + vec.displacement_concern) / 2
    return max(0.0, min(1.0, raw))


def update_cohorts(
    cohorts: tuple[CohortState, ...],
    events: tuple[ReactionEvent, ...],
) -> tuple[CohortState, ...]:
    if not events:
        return cohorts
    results: list[CohortState] = []
    for c in cohorts:
        new_reaction = _apply_events(c.reaction, events)
        new_churn = _churn_from_reaction(new_reaction)
        results.append(CohortState(
            cohort_label=c.cohort_label,
            size=c.size,
            reaction=new_reaction,
            churn_probability=round(new_churn, 4),
            affordability_pressure_avg=round(new_reaction.affordability_pressure, 4),
        ))
    return tuple(results)
