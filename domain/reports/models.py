"""Phase G report-layer artifact dataclasses.

Reports are projections off the layered runtime — each one is a frozen,
serializable read-model produced by a builder in :mod:`domain.reports.builders`
or the replay engine in :mod:`domain.reports.replay`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from domain.outcomes.projections import MarketOutcomeSnapshot
from domain.reactions.models import ReactionVector


@dataclass(frozen=True, slots=True)
class UnderwritingReport:
    """High-level financial / market read-model for an underwriting decision."""

    listing_id: str | None
    asking_price: float | None
    outcome: MarketOutcomeSnapshot
    headline: str
    recommendation: str  # "buy" | "hold" | "pass"
    confidence: float  # [0, 1]
    drivers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NegotiationBriefing:
    """Concise briefing for the next negotiation round."""

    negotiation_id: str | None
    round_count: int
    current_state: str
    next_action: str
    rationale: str
    spread_percent: float | None
    zopa_detected: bool
    top_decision_score: float


@dataclass(frozen=True, slots=True)
class PolicyRiskBrief:
    """Community / policy resistance read-model for a development proposal."""

    jurisdiction: str | None
    zoning_code: str | None
    resistance_score: float  # [0, 1]
    displacement_risk: float  # [0, 1]
    permit_friction: float | None
    sentiment: float | None
    headline: str
    recommendation: str  # "proceed" | "engage_community" | "expect_pushback"
    key_narratives: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplayFrame:
    """One step in a scenario replay — state after applying the event."""

    step: int
    occurred_at: datetime | None
    actor_id: str | None
    event_topic: str
    event_variable: str | None
    event_delta: float | None
    actor_vector: ReactionVector
    aggregate_sentiment: float | None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReplayNarrative:
    """Ordered sequence of replay frames produced by the replay engine."""

    frames: tuple[ReplayFrame, ...]
    summary: str = ""
    final_sentiment: float | None = None
