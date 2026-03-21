"""Property API endpoint tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from db.models import Property


@pytest.mark.asyncio
async def test_create_property(db):
    """Test creating a property via the model directly."""
    prop = Property(
        address="123 Test St, Chicago, IL 60601",
        asking_price=350000,
        bedrooms=2,
        bathrooms=1,
        sqft=1200,
        property_type="condo",
        status="active",
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)

    assert prop.id is not None
    assert prop.asking_price == 350000
    assert prop.status.value == "active"


@pytest.mark.asyncio
async def test_list_properties(db):
    """Test listing properties from DB."""
    from sqlalchemy import select

    for i in range(3):
        db.add(Property(
            address=f"{i} Test St, Chicago, IL 60601",
            asking_price=300000 + i * 10000,
            property_type="sfr",
            status="active",
        ))
    await db.commit()

    result = await db.execute(select(Property))
    props = list(result.scalars().all())
    assert len(props) >= 3
