"""Property CRUD API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import PropertyCreate, PropertyUpdate, PropertyResponse, PropertyListResponse
from db.database import get_db
from db.models import Property, PropertyStatus

router = APIRouter()


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


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(property_id: str, db: AsyncSession = Depends(get_db)):
    """Get property details."""
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return PropertyResponse.model_validate(prop)


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
