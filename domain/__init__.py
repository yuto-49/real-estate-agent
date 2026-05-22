"""Core business-domain packages for the layered market knowledge system.

The domain layer holds business concepts and state transitions independent of
FastAPI transport, orchestration adapters, or external integrations.

Phase A canonical event taxonomy lives in :mod:`domain.events`.
"""

from domain.events import (
    ACTOR,
    ACTOR_EVENTS,
    DECISION,
    DECISION_EVENTS,
    EventNamespace,
    MARKET,
    MARKET_EVENTS,
    OUTCOME,
    OUTCOME_EVENTS,
    REACTION,
    REACTION_EVENTS,
    canonical_event,
    is_known_event,
    namespace_of,
)

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
    "actors",
    "canonical_event",
    "decisions",
    "is_known_event",
    "market",
    "namespace_of",
    "outcomes",
    "reactions",
]
