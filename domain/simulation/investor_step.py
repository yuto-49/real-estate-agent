"""Investor trace step — updates investor sentiment and derives buy/hold/sell recommendation."""

from __future__ import annotations

from dataclasses import replace

from domain.reactions.models import ReactionEvent, ReactionVector, REACTION_VARIABLES
from domain.simulation.models import InvestorTrace, PropertyState


def _apply_events(vec: ReactionVector, events: tuple[ReactionEvent, ...]) -> ReactionVector:
    """Apply reaction events to the vector, clamping each variable to [-1, 1]."""
    if not events:
        return vec
    updates: dict[str, float] = {}
    for ev in events:
        if ev.variable in REACTION_VARIABLES:
            current = getattr(vec, ev.variable, 0.0)
            updates[ev.variable] = max(-1.0, min(1.0, current + ev.delta))
    return replace(vec, **updates) if updates else vec


def _noi_delta_event(prev_prop: PropertyState, new_prop: PropertyState) -> ReactionEvent | None:
    """Derive a reaction event from NOI change between rounds."""
    if prev_prop.annual_noi == 0:
        return None
    change = (new_prop.annual_noi - prev_prop.annual_noi) / abs(prev_prop.annual_noi)
    if abs(change) < 0.001:
        return None
    return ReactionEvent(
        topic="noi_change",
        variable="investor_optimism",
        delta=round(change * 2, 4),
        narrative=f"NOI {'rose' if change > 0 else 'fell'} {abs(change) * 100:.1f}%",
    )


def _decide(reaction: ReactionVector, prop: PropertyState) -> tuple[str, float, str]:
    """Return (recommendation, score, rationale) based on reaction state and property fundamentals."""
    opt = reaction.investor_optimism
    if prop.dscr < 1.0 and opt < -0.25:
        return "SELL", max(0.0, 0.5 - opt), "DSCR below 1.0 with negative sentiment"
    if prop.dscr < 1.15 and opt > 0:
        return "REFI", 0.6, "DSCR marginal but outlook positive — refinance"
    if opt < -0.25:
        return "SELL", max(0.0, 0.5 - opt), "Negative investor sentiment"
    if prop.occupancy_rate < 0.85:
        return "IMPROVE", 0.6, "Low occupancy — invest in improvements"
    return "HOLD", min(1.0, 0.7 + opt * 0.3), "Stable fundamentals"


def update_investor(
    prev: InvestorTrace,
    prev_prop: PropertyState,
    new_prop: PropertyState,
    events: tuple[ReactionEvent, ...],
) -> InvestorTrace:
    """Compute the next investor trace from previous state, property change, and external events."""
    all_events = list(events)
    noi_ev = _noi_delta_event(prev_prop, new_prop)
    if noi_ev:
        all_events.append(noi_ev)
    new_reaction = _apply_events(prev.reaction, tuple(all_events))
    rec, score, rationale = _decide(new_reaction, new_prop)
    return InvestorTrace(
        reaction=new_reaction,
        recommendation=rec,
        recommendation_score=round(score, 4),
        rationale=rationale,
    )
