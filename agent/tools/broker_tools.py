"""Broker-specific tool handlers."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Negotiation, Offer
from services.event_store import EventStore
from services.market_data import MarketDataService


async def mediate_negotiation(
    db: AsyncSession,
    event_store: EventStore,
    negotiation_id: str,
    correlation_id: str | None = None,
    **_kwargs,
) -> dict:
    """Facilitate a round of negotiation between buyer and seller."""
    result = await db.execute(
        select(Negotiation).where(Negotiation.id == negotiation_id)
    )
    neg = result.scalar_one_or_none()
    if not neg:
        return {"error": "Negotiation not found"}

    # Get all offers for this negotiation's property
    offers_result = await db.execute(
        select(Offer)
        .where(Offer.property_id == neg.property_id)
        .order_by(Offer.created_at.desc())
    )
    offers = list(offers_result.scalars().all())

    latest_buyer_price = None
    latest_seller_price = None
    for offer in offers:
        if offer.buyer_id == neg.buyer_id and latest_buyer_price is None:
            latest_buyer_price = offer.offer_price
        elif latest_seller_price is None:
            latest_seller_price = offer.offer_price

    spread = None
    if latest_buyer_price and latest_seller_price:
        spread = abs(latest_seller_price - latest_buyer_price) / latest_seller_price * 100

    await event_store.append(
        event_type="negotiation.mediated",
        aggregate_type="negotiation",
        aggregate_id=negotiation_id,
        payload={
            "round": neg.round_count,
            "buyer_price": latest_buyer_price,
            "seller_price": latest_seller_price,
            "spread_percent": round(spread, 1) if spread else None,
        },
        actor_type="agent",
        actor_id="broker",
        correlation_id=correlation_id,
    )

    return {
        "negotiation_id": negotiation_id,
        "round": neg.round_count,
        "status": neg.status.value if hasattr(neg.status, "value") else str(neg.status),
        "buyer_latest_price": latest_buyer_price,
        "seller_latest_price": latest_seller_price,
        "spread_percent": round(spread, 1) if spread else None,
        "recommendation": "suggest_split" if spread and spread < 5 else "continue_negotiation",
    }


async def market_analysis(
    market_data: MarketDataService,
    location: str,
    radius_miles: float = 5.0,
    **_kwargs,
) -> dict:
    """Provide comprehensive market analysis for a location."""
    stats = await market_data.get_local_stats(location)
    listings = await market_data.get_active_listings(0, 0)  # Will use mock data

    return {
        "location": location,
        "market_stats": stats,
        "active_listing_count": len(listings),
        "analysis": {
            "market_temperature": "hot" if stats.get("months_inventory", 3) < 2 else "balanced",
            "price_trend": "rising" if stats.get("yoy_change", 0) > 2 else "stable",
        },
    }


async def generate_contract(
    db: AsyncSession,
    event_store: EventStore,
    deal_id: str,
    correlation_id: str | None = None,
    **_kwargs,
) -> dict:
    """Draft a purchase agreement for an accepted deal."""
    await event_store.append(
        event_type="contract.generated",
        aggregate_type="negotiation",
        aggregate_id=deal_id,
        payload={"status": "draft"},
        actor_type="agent",
        actor_id="broker",
        correlation_id=correlation_id,
    )

    return {
        "deal_id": deal_id,
        "contract_status": "draft",
        "message": "Purchase agreement drafted. Requires review by both parties.",
    }


async def schedule_inspection(
    event_store: EventStore,
    property_id: str,
    inspection_type: str = "general",
    correlation_id: str | None = None,
    **_kwargs,
) -> dict:
    """Schedule a property inspection."""
    await event_store.append(
        event_type="inspection.scheduled",
        aggregate_type="property",
        aggregate_id=property_id,
        payload={"inspection_type": inspection_type},
        actor_type="agent",
        actor_id="broker",
        correlation_id=correlation_id,
    )

    return {
        "property_id": property_id,
        "inspection_type": inspection_type,
        "status": "scheduled",
    }
