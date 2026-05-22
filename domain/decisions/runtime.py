"""Phase E decision runtime.

Lets multiple decision streams (negotiation, list/hold, leasing, churn,
dev-resistance) consume a shared snapshot of market + actor + reaction state
without coupling to any specific orchestrator. Policies plug in via a Protocol;
the runtime ranks their recommendations by score.

Pure-Python, side-effect free, lenient: a misbehaving policy logs a warning
and is skipped rather than aborting the whole evaluation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from domain.actors.profiles import ActorSignalState
from domain.market.models import MarketContextSnapshot
from domain.reactions.models import ReactionVector

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """Immutable snapshot of layered state passed to every decision policy."""

    market: MarketContextSnapshot
    reaction: ReactionVector = field(default_factory=ReactionVector)
    actor: ActorSignalState | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DecisionRecommendation:
    """A scored suggestion produced by a single decision policy."""

    kind: str  # e.g. "negotiation", "list_hold", "lease", "churn", "dev_resistance"
    action: str  # policy-specific action label
    score: float  # higher = stronger recommendation; not normalized across kinds
    rationale: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class DecisionPolicy(Protocol):
    """Pluggable decision producer. Must be deterministic and side-effect free."""

    kind: str

    def evaluate(self, context: DecisionContext) -> DecisionRecommendation | None:
        ...


class DecisionRuntime:
    """Aggregates decision policies and ranks their recommendations."""

    def __init__(self, policies: list[DecisionPolicy] | None = None) -> None:
        self._policies: list[DecisionPolicy] = []
        for policy in policies or []:
            self.register(policy)

    @property
    def policies(self) -> tuple[DecisionPolicy, ...]:
        return tuple(self._policies)

    def register(self, policy: DecisionPolicy) -> None:
        """Add a policy. Duplicates by ``kind`` log a warning but are kept."""
        if not hasattr(policy, "kind") or not hasattr(policy, "evaluate"):
            raise TypeError(
                f"Policy {policy!r} must define 'kind' and 'evaluate'"
            )
        if any(existing.kind == policy.kind for existing in self._policies):
            logger.warning(
                "Duplicate decision policy kind %r registered — both will run.",
                policy.kind,
            )
        self._policies.append(policy)

    def evaluate(self, context: DecisionContext) -> list[DecisionRecommendation]:
        """Run every policy against ``context`` and return recommendations.

        Returns a list sorted by descending score. A policy that returns
        ``None`` is silently skipped; a policy that raises is logged and
        skipped so one bad policy can't break the whole evaluation.
        """
        recommendations: list[DecisionRecommendation] = []
        for policy in self._policies:
            try:
                result = policy.evaluate(context)
            except Exception as exc:  # noqa: BLE001 — lenient by design
                logger.warning(
                    "Decision policy %r raised %s — skipping.",
                    policy.kind,
                    exc,
                )
                continue
            if result is None:
                continue
            recommendations.append(result)
        recommendations.sort(key=lambda rec: rec.score, reverse=True)
        return recommendations

    def top(self, context: DecisionContext) -> DecisionRecommendation | None:
        """Convenience: return the highest-scoring recommendation, or None."""
        recs = self.evaluate(context)
        return recs[0] if recs else None


__all__ = [
    "DecisionContext",
    "DecisionPolicy",
    "DecisionRecommendation",
    "DecisionRuntime",
]
