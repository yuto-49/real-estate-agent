"""Phase D reaction engine.

Takes a stream of :class:`ReactionEvent`s and folds them into per-actor
:class:`ReactionVector` state. Provides convergence / divergence metrics and
narrative-cluster extraction so reaction state is queryable without touching
the legacy social-simulator loop.

Pure-Python, side-effect free, lenient: unknown variables warn but never raise.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, fields, replace
from typing import Iterable

from domain.reactions.models import REACTION_VARIABLES, ReactionEvent, ReactionVector

logger = logging.getLogger(__name__)


def _clamp_signed(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _apply_delta(vector: ReactionVector, variable: str, delta: float) -> ReactionVector:
    """Return a new ReactionVector with ``variable`` adjusted by ``delta``."""
    if variable not in REACTION_VARIABLES:
        logger.warning(
            "Unknown reaction variable %r — dropping delta. Register it in REACTION_VARIABLES.",
            variable,
        )
        return vector
    current = float(getattr(vector, variable))
    return replace(vector, **{variable: _clamp_signed(current + delta)})


@dataclass(frozen=True, slots=True)
class NarrativeCluster:
    """A group of reaction events that move the same variable in the same direction."""

    variable: str
    direction: str  # "positive" | "negative"
    total_delta: float
    event_count: int
    sample_narratives: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConvergenceReport:
    """Per-variable variance across actor reaction vectors."""

    per_variable_variance: dict[str, float]
    aggregate_variance: float
    is_converged: bool


class ReactionEngine:
    """Stateful fold over reaction events. Cheap, deterministic, no I/O."""

    def __init__(self, *, convergence_threshold: float = 0.02) -> None:
        self.convergence_threshold = convergence_threshold
        self._vectors: dict[str, ReactionVector] = {}

    @property
    def vectors(self) -> dict[str, ReactionVector]:
        """Return a shallow copy of current per-actor vectors."""
        return dict(self._vectors)

    def vector_for(self, actor_id: str) -> ReactionVector:
        return self._vectors.get(actor_id, ReactionVector())

    def apply(self, actor_id: str, event: ReactionEvent) -> ReactionVector:
        """Apply one event to one actor and return the updated vector."""
        current = self._vectors.get(actor_id, ReactionVector())
        updated = _apply_delta(current, event.variable, float(event.delta))
        self._vectors[actor_id] = updated
        return updated

    def apply_batch(
        self,
        actor_events: Iterable[tuple[str, ReactionEvent]],
    ) -> dict[str, ReactionVector]:
        """Apply many ``(actor_id, event)`` pairs. Returns final per-actor vectors."""
        for actor_id, event in actor_events:
            self.apply(actor_id, event)
        return self.vectors

    def convergence(self) -> ConvergenceReport:
        """Compute variance per reaction variable across all tracked actors.

        Convergence = low variance. The aggregate metric is the mean of
        per-variable variances; ``is_converged`` flips true once the aggregate
        drops below ``convergence_threshold``.
        """
        if not self._vectors:
            return ConvergenceReport(
                per_variable_variance={var: 0.0 for var in REACTION_VARIABLES},
                aggregate_variance=0.0,
                is_converged=True,
            )

        per_var: dict[str, float] = {}
        for variable in REACTION_VARIABLES:
            samples = [float(getattr(vector, variable)) for vector in self._vectors.values()]
            mean = sum(samples) / len(samples)
            per_var[variable] = sum((s - mean) ** 2 for s in samples) / len(samples)

        aggregate = sum(per_var.values()) / len(per_var)
        return ConvergenceReport(
            per_variable_variance=per_var,
            aggregate_variance=aggregate,
            is_converged=aggregate < self.convergence_threshold,
        )

    def divergence_score(self) -> float:
        """Convenience wrapper: aggregate variance as a non-negative scalar."""
        return self.convergence().aggregate_variance


def extract_narratives(
    events: Iterable[ReactionEvent],
    *,
    sample_limit: int = 3,
) -> list[NarrativeCluster]:
    """Group ``events`` by ``(variable, direction)`` and rank by absolute delta.

    Returns clusters sorted descending by ``total_delta`` magnitude. Unknown
    variables are skipped (with a warning) so callers can pass raw event
    streams without pre-validation.
    """
    buckets: dict[tuple[str, str], list[ReactionEvent]] = defaultdict(list)

    for event in events:
        if event.variable not in REACTION_VARIABLES:
            logger.warning("Skipping narrative for unknown variable %r", event.variable)
            continue
        if event.delta == 0:
            continue
        direction = "positive" if event.delta > 0 else "negative"
        buckets[(event.variable, direction)].append(event)

    clusters: list[NarrativeCluster] = []
    for (variable, direction), grouped in buckets.items():
        total = sum(event.delta for event in grouped)
        narratives = tuple(
            event.narrative
            for event in sorted(grouped, key=lambda e: abs(e.delta), reverse=True)[:sample_limit]
            if event.narrative
        )
        clusters.append(
            NarrativeCluster(
                variable=variable,
                direction=direction,
                total_delta=total,
                event_count=len(grouped),
                sample_narratives=narratives,
            )
        )

    clusters.sort(key=lambda cluster: abs(cluster.total_delta), reverse=True)
    return clusters


def vector_distance(a: ReactionVector, b: ReactionVector) -> float:
    """Euclidean distance between two reaction vectors across the 8 variables."""
    diffs = [
        float(getattr(a, field_def.name)) - float(getattr(b, field_def.name))
        for field_def in fields(ReactionVector)
    ]
    return math.sqrt(sum(diff * diff for diff in diffs))


__all__ = [
    "ConvergenceReport",
    "NarrativeCluster",
    "ReactionEngine",
    "extract_narratives",
    "vector_distance",
]
