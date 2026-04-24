"""Outcome-layer snapshot helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class MarketOutcomeSnapshot:
    """Observable market metrics projected from decision and reaction state."""

    listing_id: str | None = None
    price_change_pct: float | None = None
    time_on_market_days: int | None = None
    offer_volume: int = 0
    concession_rate: float | None = None
    turnover_rate: float | None = None
    permit_friction: float | None = None
    neighborhood_sentiment: float | None = None


@dataclass(frozen=True, slots=True)
class NegotiationOfferSnapshot:
    """Projection-friendly view of a negotiation price move."""

    offer_id: str
    property_id: str
    buyer_id: str | None
    offer_price: float
    actor_role: str | None = None
    actor_user_id: str | None = None
    status: str | None = None
    parent_offer_id: str | None = None
    correlation_id: str | None = None
    message: str | None = None
    created_at: datetime | None = None


def merge_outcome_snapshot(
    snapshot: MarketOutcomeSnapshot,
    **updates: Any,
) -> MarketOutcomeSnapshot:
    """Return a new outcome snapshot with updated observable metrics."""
    return replace(snapshot, **updates)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _status_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def project_negotiation_session(
    *,
    negotiation: Any,
    offers: list[NegotiationOfferSnapshot],
    events: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """Build the canonical negotiation session read model."""
    offer_history = [
        {
            "id": offer.offer_id,
            "property_id": offer.property_id,
            "buyer_id": offer.buyer_id,
            "offer_price": offer.offer_price,
            "actor_role": offer.actor_role,
            "actor_user_id": offer.actor_user_id,
            "status": offer.status,
            "parent_offer_id": offer.parent_offer_id,
            "correlation_id": offer.correlation_id,
            "message": offer.message,
            "created_at": _serialize_datetime(offer.created_at),
        }
        for offer in offers
    ]

    return {
        "id": negotiation.id,
        "property_id": negotiation.property_id,
        "buyer_id": negotiation.buyer_id,
        "seller_id": negotiation.seller_id,
        "status": _status_value(negotiation.status),
        "round_count": negotiation.round_count,
        "final_price": negotiation.final_price,
        "deadline_at": _serialize_datetime(getattr(negotiation, "deadline_at", None)),
        "offer_history": offer_history,
        "current_analysis": analysis,
        "events": events,
    }
