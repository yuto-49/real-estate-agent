"""Event Store — append-only event sourcing for audit trail and replay."""

from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import DomainEvent


class EventStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def append(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict,
        actor_type: str | None = None,
        actor_id: str | None = None,
        correlation_id: str | None = None,
    ) -> DomainEvent:
        """Append a new domain event."""
        seq_result = await self.db.execute(
            select(func.coalesce(func.max(DomainEvent.sequence), 0)).where(
                DomainEvent.aggregate_type == aggregate_type,
                DomainEvent.aggregate_id == aggregate_id,
            )
        )
        next_seq = seq_result.scalar() + 1

        event = DomainEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            sequence=next_seq,
            created_at=datetime.utcnow(),
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def get_events(
        self, aggregate_type: str, aggregate_id: str
    ) -> list[DomainEvent]:
        """Get all events for an aggregate, ordered by sequence."""
        result = await self.db.execute(
            select(DomainEvent)
            .where(
                DomainEvent.aggregate_type == aggregate_type,
                DomainEvent.aggregate_id == aggregate_id,
            )
            .order_by(DomainEvent.sequence)
        )
        return list(result.scalars().all())

    async def get_by_correlation(self, correlation_id: str) -> list[DomainEvent]:
        """Get all events sharing a correlation ID."""
        result = await self.db.execute(
            select(DomainEvent)
            .where(DomainEvent.correlation_id == correlation_id)
            .order_by(DomainEvent.created_at)
        )
        return list(result.scalars().all())

    async def replay_aggregate(
        self, aggregate_type: str, aggregate_id: str
    ) -> list[dict]:
        """Replay events for an aggregate as a list of dicts."""
        events = await self.get_events(aggregate_type, aggregate_id)
        return [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "sequence": e.sequence,
                "actor_type": e.actor_type,
                "actor_id": e.actor_id,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
