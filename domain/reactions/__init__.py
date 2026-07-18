"""Reaction-layer primitives and social-dynamics helpers."""

from domain.reactions.derive import (
    actor_reaction_events,
    build_reaction_vector,
    market_reaction_events,
)
from domain.reactions.engine import (
    ConvergenceReport,
    NarrativeCluster,
    ReactionEngine,
    extract_narratives,
    vector_distance,
)
from domain.reactions.models import REACTION_VARIABLES, ReactionEvent, ReactionVector
from domain.reactions.runtime import SocialReactionRuntime
from domain.reactions.social_dynamics import (
    ALLOWED_REACTION_TOPICS,
    SOCIAL_REACTION_TOPICS,
    TOPIC_DESCRIPTIONS,
    build_initial_opinions,
    communication_style_multiplier,
    validate_topics,
)

__all__ = [
    "ALLOWED_REACTION_TOPICS",
    "ConvergenceReport",
    "NarrativeCluster",
    "REACTION_VARIABLES",
    "ReactionEngine",
    "ReactionEvent",
    "ReactionVector",
    "SocialReactionRuntime",
    "SOCIAL_REACTION_TOPICS",
    "TOPIC_DESCRIPTIONS",
    "build_initial_opinions",
    "communication_style_multiplier",
    "extract_narratives",
    "validate_topics",
    "vector_distance",
    "actor_reaction_events",
    "build_reaction_vector",
    "market_reaction_events",
]
