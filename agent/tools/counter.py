"""Counter-offer tool handler."""

from sqlalchemy.ext.asyncio import AsyncSession

from agent.negotiation_engine import NegotiationEngine
from services.event_store import EventStore


async def counter_offer(
    db: AsyncSession,
    event_store: EventStore,
    negotiation_id: str,
    counter_price: float,
    from_role: str = "buyer",
    message: str = "",
    **_kwargs,
) -> dict:
    """Submit a counter-offer in an active negotiation."""
    engine = NegotiationEngine(db=db, event_store=event_store)
    result = await engine.process_offer(
        negotiation_id=negotiation_id,
        offer_price=counter_price,
        from_role=from_role,
        message=message,
    )
    return result
