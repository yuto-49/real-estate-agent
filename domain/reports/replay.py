"""Phase G scenario replay engine.

Re-applies a stream of :class:`ReactionEvent`s through a fresh
:class:`ReactionEngine`, capturing per-step state snapshots so callers can
narrate what happened and when. Pure-Python; no I/O, no persistence.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from domain.outcomes.builders import project_neighborhood_sentiment
from domain.reactions.engine import ReactionEngine
from domain.reactions.models import ReactionEvent
from domain.reports.models import ReplayFrame, ReplayNarrative


def replay_reactions(
    actor_events: Sequence[tuple[str, ReactionEvent]],
    *,
    summary: str = "",
) -> ReplayNarrative:
    """Replay ``(actor_id, event)`` pairs and return per-step frames.

    Each frame captures: step index, actor that moved, the event variable and
    delta, the actor's new vector, and aggregate neighborhood sentiment after
    the event was applied. Ordering is preserved exactly as given.
    """
    engine = ReactionEngine()
    frames: list[ReplayFrame] = []

    for index, (actor_id, event) in enumerate(actor_events):
        engine.apply(actor_id, event)
        sentiment = project_neighborhood_sentiment(_collect_vectors(engine))
        frames.append(
            ReplayFrame(
                step=index,
                occurred_at=event.occurred_at,
                actor_id=actor_id,
                event_topic=event.topic,
                event_variable=event.variable,
                event_delta=float(event.delta),
                actor_vector=engine.vector_for(actor_id),
                aggregate_sentiment=sentiment,
                metadata=event.metadata,
            )
        )

    final_sentiment = (
        project_neighborhood_sentiment(_collect_vectors(engine)) if frames else None
    )

    return ReplayNarrative(
        frames=tuple(frames),
        summary=summary,
        final_sentiment=final_sentiment,
    )


def _collect_vectors(engine: ReactionEngine) -> Iterable:
    return list(engine.vectors.values())


__all__ = ["replay_reactions"]
