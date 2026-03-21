"""Background task that transitions expired negotiations."""

import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Negotiation, NegotiationStatus
from services.event_store import EventStore
from services.logging import get_logger

logger = get_logger(__name__)


async def check_expired_negotiations(db: AsyncSession) -> list[str]:
    """Find and transition expired negotiations. Returns list of expired negotiation IDs."""
    now = datetime.utcnow()

    # States that can timeout
    expirable_states = [
        NegotiationStatus.OFFER_PENDING,
        NegotiationStatus.COUNTER_PENDING,
        NegotiationStatus.CONTRACT_PHASE,
        NegotiationStatus.INSPECTION,
        NegotiationStatus.CLOSING,
    ]

    result = await db.execute(
        select(Negotiation).where(
            Negotiation.status.in_(expirable_states),
            Negotiation.deadline_at.isnot(None),
            Negotiation.deadline_at < now,
        )
    )
    expired = list(result.scalars().all())

    event_store = EventStore(db)
    expired_ids = []

    for neg in expired:
        old_status = neg.status
        neg.status = NegotiationStatus.WITHDRAWN
        neg.updated_at = now

        await event_store.append(
            event_type="negotiation.expired",
            aggregate_type="negotiation",
            aggregate_id=neg.id,
            payload={
                "previous_status": old_status.value if hasattr(old_status, "value") else str(old_status),
                "deadline_at": neg.deadline_at.isoformat() if neg.deadline_at else None,
                "expired_at": now.isoformat(),
            },
            actor_type="system",
            actor_id="timeout_checker",
            correlation_id=neg.correlation_id,
        )
        expired_ids.append(neg.id)

    if expired_ids:
        await db.commit()

    return expired_ids


async def run_timeout_checker(session_factory, interval_seconds: int = 60):
    """Background loop that checks for expired negotiations."""
    while True:
        try:
            async with session_factory() as db:
                expired = await check_expired_negotiations(db)
                if expired:
                    logger.info("timeout_checker.expired", count=len(expired), ids=expired)
        except Exception as e:
            logger.error("timeout_checker.error", error=str(e))
        await asyncio.sleep(interval_seconds)
