"""Actor → reaction bridge.

Turns layered actor signals (``domain.actors``) and market-observable signals
(``domain.market``) into a single :class:`ReactionVector` by folding
:class:`ReactionEvent`s through the real :class:`ReactionEngine`. This is the
missing seam that lets the decision layer consume reaction state produced by
the intended ``actors → reactions`` pipeline instead of a hand-built vector.

Pure-Python, deterministic, side-effect free, and lenient: missing or neutral
inputs simply emit fewer events (a zeroed vector in the limit) — never a raise.

Range convention
----------------
:class:`~domain.actors.ActorSignalState` carries unit-magnitude signals in
``[0, 1]`` (e.g. ``perceived_safety``), except ``trust_in_trajectory`` which is
already signed in ``[-1, 1]``. :class:`~domain.reactions.models.ReactionVector`
is signed throughout. The bridge maps each unit actor signal into signed
reaction space via ``2x - 1`` (so a neutral ``0.5`` → ``0.0`` and is dropped),
and passes ``trust_in_trajectory`` through unchanged.

A raw ``0.0`` is treated as *unset* (the dataclass default) and emits no event,
so a zeroed or partially-filled actor state degrades gracefully rather than
flooding the fold with spurious ``-1.0`` deltas.
"""

from __future__ import annotations

from domain.actors.profiles import ActorSignalState
from domain.market.models import MarketContextSnapshot
from domain.reactions.engine import ReactionEngine
from domain.reactions.models import REACTION_VARIABLES, ReactionEvent, ReactionVector

# Actor signal that is already expressed in the signed reaction range.
_SIGNED_ACTOR_VARIABLES = frozenset({"trust_in_trajectory"})

# Synthetic actor id under which the holding's folded reaction is tracked.
_HOLDING_ACTOR_ID = "holding"


def _clamp_signed(value: float) -> float:
    return max(-1.0, min(1.0, value))


def actor_reaction_events(
    actor: ActorSignalState, *, topic: str = "actor_signal"
) -> list[ReactionEvent]:
    """Project an actor signal state into one reaction event per variable.

    Unit-range signals are remapped to signed deltas (``2x - 1``); already-signed
    signals pass through. An unset field (raw ``0.0``) and any signal that maps to
    a zero delta (e.g. a neutral ``0.5``) are dropped so a neutral or empty actor
    contributes nothing to the fold.
    """
    events: list[ReactionEvent] = []
    for variable in REACTION_VARIABLES:
        raw = float(getattr(actor, variable, 0.0) or 0.0)
        if raw == 0.0:
            continue
        if variable in _SIGNED_ACTOR_VARIABLES:
            delta = _clamp_signed(raw)
        else:
            delta = _clamp_signed(2.0 * raw - 1.0)
        if delta == 0.0:
            continue
        events.append(
            ReactionEvent(
                topic=topic,
                variable=variable,
                delta=delta,
                narrative=f"actor {variable}={raw:.3f}",
            )
        )
    return events


def market_reaction_events(
    market: MarketContextSnapshot,
    *,
    monthly_rent: float | None = None,
    topic: str = "market_signal",
) -> list[ReactionEvent]:
    """Project market-observable signals into signed reaction events.

    Mirrors the observable readings the decision layer cares about: inventory
    slack → investor optimism / willingness, neighborhood safety → perceived
    safety / displacement concern, and the asking-rent-vs-market gap →
    affordability pressure. Every field is optional; missing data emits fewer
    events rather than raising.
    """
    events: list[ReactionEvent] = []

    def _emit(variable: str, delta: float, narrative: str) -> None:
        clamped = _clamp_signed(delta)
        if clamped == 0.0:
            return
        events.append(
            ReactionEvent(
                topic=topic, variable=variable, delta=clamped, narrative=narrative
            )
        )

    if market.inventory_pressure is not None:
        slack = _clamp_signed(1.0 - 2.0 * market.inventory_pressure)
        _emit("investor_optimism", slack, f"inventory_pressure={market.inventory_pressure:.3f}")
        _emit("willingness_to_transact", slack, f"inventory_pressure={market.inventory_pressure:.3f}")

    if market.safety_score is not None:
        safety = _clamp_signed(market.safety_score / 5.0 - 1.0)
        _emit("perceived_safety", safety, f"safety_score={market.safety_score:.3f}")
        _emit("displacement_concern", -safety, f"safety_score={market.safety_score:.3f}")

    if market.median_rent and monthly_rent:
        gap = (monthly_rent - market.median_rent) / market.median_rent
        _emit(
            "affordability_pressure",
            gap,
            f"rent {monthly_rent:.0f} vs median {market.median_rent:.0f}",
        )

    return events


def build_reaction_vector(
    actor: ActorSignalState | None,
    market: MarketContextSnapshot,
    *,
    monthly_rent: float | None = None,
) -> ReactionVector:
    """Fold actor + market events through a :class:`ReactionEngine`.

    Returns the holding's reaction vector. ``actor=None`` yields a market-only
    projection; no signal at all yields a zeroed :class:`ReactionVector`.
    """
    engine = ReactionEngine()
    events: list[ReactionEvent] = []
    if actor is not None:
        events.extend(actor_reaction_events(actor))
    events.extend(market_reaction_events(market, monthly_rent=monthly_rent))
    engine.apply_batch((_HOLDING_ACTOR_ID, event) for event in events)
    return engine.vector_for(_HOLDING_ACTOR_ID)


__all__ = [
    "actor_reaction_events",
    "build_reaction_vector",
    "market_reaction_events",
]
