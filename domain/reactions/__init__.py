"""Reaction-layer primitives and social-dynamics helpers."""

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
    "REACTION_VARIABLES",
    "ReactionEvent",
    "ReactionVector",
    "SocialReactionRuntime",
    "SOCIAL_REACTION_TOPICS",
    "TOPIC_DESCRIPTIONS",
    "build_initial_opinions",
    "communication_style_multiplier",
    "validate_topics",
]
