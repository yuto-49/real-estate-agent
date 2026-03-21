"""Property search tool handler."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Property, PropertyStatus


async def search_properties(
    db: AsyncSession,
    location: str,
    min_price: float | None = None,
    max_price: float | None = None,
    bedrooms: int | None = None,
    property_type: str | None = None,
    **_kwargs,
) -> dict:
    """Search listings matching buyer criteria."""
    query = select(Property).where(Property.status == PropertyStatus.ACTIVE)

    if min_price is not None:
        query = query.where(Property.asking_price >= min_price)
    if max_price is not None:
        query = query.where(Property.asking_price <= max_price)
    if bedrooms is not None:
        query = query.where(Property.bedrooms >= bedrooms)
    if property_type:
        query = query.where(Property.property_type == property_type)

    # Simple location filter: match on address substring
    if location:
        query = query.where(Property.address.ilike(f"%{location}%"))

    query = query.limit(20)
    result = await db.execute(query)
    properties = list(result.scalars().all())

    return {
        "count": len(properties),
        "properties": [
            {
                "id": p.id,
                "address": p.address,
                "asking_price": p.asking_price,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "sqft": p.sqft,
                "property_type": p.property_type,
            }
            for p in properties
        ],
    }
