"""Offer-related tool handlers."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Offer, Property, UserProfile
from agent.guardrails import validate_offer
from services.event_store import EventStore


async def place_offer(
    db: AsyncSession,
    event_store: EventStore,
    property_id: str,
    offer_price: float,
    buyer_id: str = "",
    contingencies: list[str] | None = None,
    correlation_id: str | None = None,
    **_kwargs,
) -> dict:
    """Submit a purchase offer on a property."""
    prop_result = await db.execute(select(Property).where(Property.id == property_id))
    prop = prop_result.scalar_one_or_none()
    if not prop:
        return {"error": "Property not found"}

    buyer_result = await db.execute(select(UserProfile).where(UserProfile.id == buyer_id))
    buyer = buyer_result.scalar_one_or_none()
    budget = buyer.budget_max if buyer else float("inf")

    guardrail = validate_offer(offer_price, prop.asking_price, budget)
    if not guardrail.passed:
        return {"error": guardrail.reason, "guardrail_blocked": True}

    offer = Offer(
        property_id=property_id,
        buyer_id=buyer_id,
        offer_price=offer_price,
        contingencies=contingencies or [],
        correlation_id=correlation_id,
    )
    db.add(offer)
    await db.flush()

    await event_store.append(
        event_type="offer.created",
        aggregate_type="negotiation",
        aggregate_id=property_id,
        payload={"offer_id": offer.id, "offer_price": offer_price},
        actor_type="agent",
        actor_id=buyer_id,
        correlation_id=correlation_id,
    )

    return {
        "offer_id": offer.id,
        "property_id": property_id,
        "offer_price": offer_price,
        "status": "pending",
    }


async def evaluate_offer(
    db: AsyncSession,
    offer_id: str,
    **_kwargs,
) -> dict:
    """Analyze an incoming offer against market data."""
    result = await db.execute(select(Offer).where(Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        return {"error": "Offer not found"}

    prop_result = await db.execute(select(Property).where(Property.id == offer.property_id))
    prop = prop_result.scalar_one_or_none()
    if not prop:
        return {"error": "Property not found"}

    spread = (prop.asking_price - offer.offer_price) / prop.asking_price * 100

    return {
        "offer_id": offer.id,
        "offer_price": offer.offer_price,
        "asking_price": prop.asking_price,
        "spread_percent": round(spread, 1),
        "recommendation": "counter" if spread > 3 else "accept",
        "contingencies": offer.contingencies,
    }


async def accept_offer(
    db: AsyncSession,
    event_store: EventStore,
    offer_id: str,
    correlation_id: str | None = None,
    **_kwargs,
) -> dict:
    """Accept an offer and move to contract phase."""
    result = await db.execute(select(Offer).where(Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        return {"error": "Offer not found"}

    offer.status = "accepted"
    await db.flush()

    await event_store.append(
        event_type="offer.accepted",
        aggregate_type="negotiation",
        aggregate_id=offer.property_id,
        payload={"offer_id": offer.id, "accepted_price": offer.offer_price},
        actor_type="agent",
        correlation_id=correlation_id,
    )

    return {"offer_id": offer.id, "status": "accepted", "price": offer.offer_price}
