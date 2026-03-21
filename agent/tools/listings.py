"""Listing management tool handlers."""

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Property
from agent.guardrails import validate_disclosures
from services.event_store import EventStore


async def list_property(
    db: AsyncSession,
    event_store: EventStore,
    address: str,
    asking_price: float,
    bedrooms: int,
    bathrooms: float,
    sqft: int,
    seller_id: str | None = None,
    property_type: str = "sfr",
    disclosures: dict | None = None,
    correlation_id: str | None = None,
    **_kwargs,
) -> dict:
    """List a property for sale."""
    if disclosures:
        guardrail = validate_disclosures(disclosures)
        if not guardrail.passed:
            return {"error": guardrail.reason, "guardrail_blocked": True}

    prop = Property(
        seller_id=seller_id,
        address=address,
        asking_price=asking_price,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        sqft=sqft,
        property_type=property_type,
        disclosures=disclosures or {},
        status="active",
    )
    db.add(prop)
    await db.flush()

    await event_store.append(
        event_type="property.listed",
        aggregate_type="property",
        aggregate_id=prop.id,
        payload={"address": address, "asking_price": asking_price},
        actor_type="agent",
        actor_id=seller_id,
        correlation_id=correlation_id,
    )

    return {
        "property_id": prop.id,
        "address": address,
        "asking_price": asking_price,
        "status": "active",
    }


async def set_asking_price(
    db: AsyncSession,
    event_store: EventStore,
    property_id: str,
    new_price: float,
    correlation_id: str | None = None,
    **_kwargs,
) -> dict:
    """Update asking price for a listed property."""
    from sqlalchemy import select
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        return {"error": "Property not found"}

    old_price = prop.asking_price
    prop.asking_price = new_price
    await db.flush()

    await event_store.append(
        event_type="property.price_updated",
        aggregate_type="property",
        aggregate_id=property_id,
        payload={"old_price": old_price, "new_price": new_price},
        actor_type="agent",
        correlation_id=correlation_id,
    )

    return {"property_id": property_id, "old_price": old_price, "new_price": new_price}
