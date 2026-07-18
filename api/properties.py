"""Property CRUD API endpoints."""

from dataclasses import asdict
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    PropertyCreate,
    PropertyListResponse,
    PropertyRecommendation,
    PropertyRecommendationsResponse,
    PropertyResponse,
    PropertyUpdate,
)
from db.database import get_db
from db.models import InvestorProfile, Property, PropertyStatus
from services.market_state import build_snapshot, build_snapshots
from services.property_recommender import rank_properties

router = APIRouter()

_JP_ZIP_RE = re.compile(r"^\d{3}-?\d{4}$")


def _profile_targets_japan(profile: InvestorProfile) -> bool:
    geo = dict(profile.geography or {})
    if any(
        geo.get(key)
        for key in ("prefecture", "municipality", "ward", "neighborhood", "station")
    ):
        return True

    zip_code = str(geo.get("zip") or "").strip()
    if _JP_ZIP_RE.fullmatch(zip_code):
        return True

    for key in ("state", "city"):
        value = str(geo.get(key) or "").strip()
        if not value:
            continue
        if any(suffix in value for suffix in ("都", "道", "府", "県", "区", "市", "町", "村")):
            return True
    return False


@router.get("/", response_model=PropertyListResponse)
async def list_properties(
    status: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    property_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List properties with optional filters."""
    query = select(Property)
    if status:
        query = query.where(Property.status == status)
    else:
        query = query.where(Property.status == PropertyStatus.ACTIVE)
    if min_price is not None:
        query = query.where(Property.asking_price >= min_price)
    if max_price is not None:
        query = query.where(Property.asking_price <= max_price)
    if property_type:
        query = query.where(Property.property_type == property_type)

    query = query.order_by(Property.listed_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    properties = list(result.scalars().all())

    count_query = select(Property)
    if status:
        count_query = count_query.where(Property.status == status)
    else:
        count_query = count_query.where(Property.status == PropertyStatus.ACTIVE)
    from sqlalchemy import func
    count_result = await db.execute(select(func.count()).select_from(count_query.subquery()))
    total = count_result.scalar()

    return PropertyListResponse(
        properties=[PropertyResponse.model_validate(p) for p in properties],
        count=total,
    )


@router.get("/recommend", response_model=PropertyRecommendationsResponse)
async def recommend_properties(
    user_id: str,
    top_n: int = 10,
    db: AsyncSession = Depends(get_db),
) -> PropertyRecommendationsResponse:
    """Rank active listings for the investor's profile.

    Pre-filter on budget + geography, then score via the deterministic
    ``services.property_recommender`` ranker. The user must have an
    ``InvestorProfile`` row (created by the onboarding wizard's "no portfolio"
    branch).
    """
    profile = (
        await db.execute(
            select(InvestorProfile).where(InvestorProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="profile_not_found")

    query = select(Property).where(Property.status == PropertyStatus.ACTIVE)
    if _profile_targets_japan(profile):
        query = query.where(Property.jurisdiction == "jp")

    candidates = (await db.execute(query)).scalars().all()
    if _profile_targets_japan(profile) and not candidates:
        candidates = (
            await db.execute(
                select(Property).where(Property.status == PropertyStatus.ACTIVE)
            )
        ).scalars().all()

    try:
        # Batched: two signal queries for all candidates instead of per-property.
        snapshots = await build_snapshots(db, candidates)
    except Exception:
        # Snapshots are optional — the ranker tolerates missing snapshots.
        snapshots = {}

    scored = rank_properties(
        profile, list(candidates), snapshots=snapshots, top_n=max(1, min(top_n, 50))
    )

    return PropertyRecommendationsResponse(
        recommendations=[
            PropertyRecommendation(
                property_id=s.property_id,
                address=s.property.address,
                asking_price=s.property.asking_price,
                property_type=s.property.property_type,
                bedrooms=s.property.bedrooms,
                bathrooms=s.property.bathrooms,
                sqft=s.property.sqft,
                score=s.score,
                rationale=s.rationale,
            )
            for s in scored
        ],
        profile_id=profile.id,
        candidates_considered=len(candidates),
    )


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(property_id: str, db: AsyncSession = Depends(get_db)):
    """Get property details."""
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return PropertyResponse.model_validate(prop)


@router.get("/{property_id}/market-context")
async def get_market_context(property_id: str, db: AsyncSession = Depends(get_db)):
    """Return the latest layered MarketContextSnapshot for a property.

    Wraps :func:`services.market_state.build_snapshot` — fields derive from the
    most recent ``market_signals`` rows for the property and its neighborhood,
    with property-level signals winning over neighborhood-level on overlap.
    Missing signals stay ``null`` (lenient), so callers can render partial
    context without coordinating writes.
    """
    snapshot = await build_snapshot(db, property_id=property_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return asdict(snapshot)


@router.post("/", response_model=PropertyResponse, status_code=201)
async def create_property(data: PropertyCreate, db: AsyncSession = Depends(get_db)):
    """Create a new property listing."""
    prop = Property(**data.model_dump())
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return PropertyResponse.model_validate(prop)


@router.patch("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: str, data: PropertyUpdate, db: AsyncSession = Depends(get_db)
):
    """Update property details."""
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(prop, key, value)
    await db.commit()
    await db.refresh(prop)
    return PropertyResponse.model_validate(prop)
