"""Offer CRUD API endpoints with guardrail validation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import OfferCreate, OfferResponse
from db.database import get_db
from db.models import Offer, Property, UserProfile
from agent.guardrails import validate_offer
from middleware.correlation import get_correlation_id

router = APIRouter()


@router.post("/", response_model=OfferResponse, status_code=201)
async def create_offer(data: OfferCreate, db: AsyncSession = Depends(get_db)):
    """Create a new offer — validates through guardrails first."""
    # Fetch property and buyer for validation
    prop_result = await db.execute(select(Property).where(Property.id == data.property_id))
    prop = prop_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    buyer_result = await db.execute(select(UserProfile).where(UserProfile.id == data.buyer_id))
    buyer = buyer_result.scalar_one_or_none()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")

    # Run guardrail validation
    budget = buyer.budget_max or float("inf")
    guardrail = validate_offer(data.offer_price, prop.asking_price, budget)
    if not guardrail.passed:
        raise HTTPException(status_code=422, detail=guardrail.reason)

    offer = Offer(
        property_id=data.property_id,
        buyer_id=data.buyer_id,
        offer_price=data.offer_price,
        contingencies=data.contingencies,
        parent_offer_id=data.parent_offer_id,
        correlation_id=get_correlation_id() or None,
    )
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return OfferResponse.model_validate(offer)


@router.get("/{offer_id}", response_model=OfferResponse)
async def get_offer(offer_id: str, db: AsyncSession = Depends(get_db)):
    """Get offer details."""
    result = await db.execute(select(Offer).where(Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return OfferResponse.model_validate(offer)


@router.get("/", response_model=list[OfferResponse])
async def list_offers(
    property_id: str | None = None,
    buyer_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List offers with optional filters."""
    query = select(Offer)
    if property_id:
        query = query.where(Offer.property_id == property_id)
    if buyer_id:
        query = query.where(Offer.buyer_id == buyer_id)
    query = query.order_by(Offer.created_at.desc())
    result = await db.execute(query)
    offers = list(result.scalars().all())
    return [OfferResponse.model_validate(o) for o in offers]
