"""Reaction-layer structured state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping


REACTION_VARIABLES = (
    "trust_in_trajectory",
    "affordability_pressure",
    "perceived_safety",
    "social_proof",
    "displacement_concern",
    "investor_optimism",
    "willingness_to_transact",
    "resistance_to_development",
)


@dataclass(frozen=True, slots=True)
class ReactionVector:
    """Structured reaction state that can be diffed and replayed."""

    trust_in_trajectory: float = 0.0
    affordability_pressure: float = 0.0
    perceived_safety: float = 0.0
    social_proof: float = 0.0
    displacement_concern: float = 0.0
    investor_optimism: float = 0.0
    willingness_to_transact: float = 0.0
    resistance_to_development: float = 0.0


@dataclass(frozen=True, slots=True)
class ReactionEvent:
    """A structured reaction update emitted by the reaction layer."""

    topic: str
    variable: str
    delta: float
    narrative: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
