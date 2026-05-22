"""Canonical event taxonomy for the layered market-knowledge runtime.

Phase A of SOCIAL_SIMULATION_IMPLEMENTATION.md: a single catalog of namespaced
event names so the spatial market, actor, social-reaction, decision, and
outcome layers all speak the same vocabulary.

Existing inline event strings (e.g. ``"property.listed"``, ``"offer.created"``,
``"negotiation.started"``) remain valid; this module is additive. Phase B+
migrations should route them through :func:`canonical_event` so the registry
stays authoritative.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Final

logger = logging.getLogger(__name__)


class EventNamespace(str, Enum):
    """Top-level event namespaces for the layered runtime."""

    MARKET = "market"
    ACTOR = "actor"
    REACTION = "reaction"
    DECISION = "decision"
    OUTCOME = "outcome"


# Re-exported as module-level constants for convenience.
MARKET: Final[str] = EventNamespace.MARKET.value
ACTOR: Final[str] = EventNamespace.ACTOR.value
REACTION: Final[str] = EventNamespace.REACTION.value
DECISION: Final[str] = EventNamespace.DECISION.value
OUTCOME: Final[str] = EventNamespace.OUTCOME.value


# Canonical event names per namespace. Keep entries lower_snake_case and
# describe a state transition or signal — never an internal method call.
MARKET_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "property.listed",
        "property.price_updated",
        "property.delisted",
        "zoning.changed",
        "transit.changed",
        "permit.filed",
        "permit.approved",
        "permit.denied",
        "comp.recorded",
        "shock.occurred",
    }
)

ACTOR_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "household.created",
        "household.profile_updated",
        "household.affordability_changed",
        "buyer.registered",
        "seller.registered",
        "broker.registered",
        "investor.registered",
        "cohort.memory_updated",
    }
)

REACTION_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "round.started",
        "round.completed",
        "opinion.updated",
        "narrative.emerged",
        "narrative.converged",
        "narrative.diverged",
        "sentiment.shifted",
    }
)

DECISION_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "negotiation.started",
        "negotiation.mediated",
        "negotiation.escalated",
        "offer.created",
        "offer.accepted",
        "offer.rejected",
        "offer.withdrawn",
        "counter.proposed",
        "contract.generated",
        "inspection.scheduled",
        "lease.signed",
        "listing.held",
        "listing.priced",
    }
)

OUTCOME_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "deal.closed",
        "deal.fell_through",
        "time_on_market.recorded",
        "concession.recorded",
        "turnover.recorded",
        "permit_friction.recorded",
        "neighborhood_sentiment.snapshot",
        "price_movement.recorded",
    }
)


_REGISTRY: Final[dict[str, frozenset[str]]] = {
    MARKET: MARKET_EVENTS,
    ACTOR: ACTOR_EVENTS,
    REACTION: REACTION_EVENTS,
    DECISION: DECISION_EVENTS,
    OUTCOME: OUTCOME_EVENTS,
}


def canonical_event(namespace: str | EventNamespace, name: str) -> str:
    """Tag ``name`` against its namespace registry. Lenient: warns but never raises.

    The namespace must be one of the five layers (``EventNamespace`` coercion
    will raise on a typo there). The event name itself is open-set: if it is
    not yet registered, we log a warning and return the name unchanged so
    callers can adopt the helper without first updating the registry.
    """
    ns = namespace if isinstance(namespace, EventNamespace) else EventNamespace(namespace)
    if name not in _REGISTRY[ns.value]:
        logger.warning(
            "Unregistered %s event %r — add it to domain.events.%s_EVENTS",
            ns.value,
            name,
            ns.name,
        )
    return name


def is_known_event(event_type: str) -> bool:
    """Return True if ``event_type`` appears in any namespace registry."""
    for events in _REGISTRY.values():
        if event_type in events:
            return True
    return False


def namespace_of(event_type: str) -> EventNamespace | None:
    """Return the namespace that owns ``event_type`` or ``None`` if unknown."""
    for ns_value, events in _REGISTRY.items():
        if event_type in events:
            return EventNamespace(ns_value)
    return None


__all__ = [
    "ACTOR",
    "ACTOR_EVENTS",
    "DECISION",
    "DECISION_EVENTS",
    "EventNamespace",
    "MARKET",
    "MARKET_EVENTS",
    "OUTCOME",
    "OUTCOME_EVENTS",
    "REACTION",
    "REACTION_EVENTS",
    "canonical_event",
    "is_known_event",
    "namespace_of",
]
