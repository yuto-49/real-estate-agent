"""Tests for GET /api/properties/{id}/market-context (Phase M2.4)."""

from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.database import get_db
from db.models import MarketSignal, Property
from main import app


@pytest_asyncio.fixture
async def client(db_engine):
    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )

    async def _override_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_property_with_signals(db):
    prop = Property(
        address="123 Market Ctx Ave",
        asking_price=600_000,
        neighborhood_data={"neighborhood_id": "lincoln-park", "zip_code": "60614"},
        hazard_flags={"flood": False},
        jurisdiction="us",
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)

    db.add_all(
        [
            MarketSignal(
                signal_type="median_sale_price",
                subject_type="neighborhood",
                subject_id="60614",
                value=750_000.0,
                observed_at=datetime.utcnow(),
            ),
            MarketSignal(
                signal_type="inventory_pressure",
                subject_type="neighborhood",
                subject_id="60614",
                value=2.5,
                observed_at=datetime.utcnow(),
            ),
            MarketSignal(
                signal_type="transit_score",
                subject_type="property",
                subject_id=prop.id,
                value=72.0,
                observed_at=datetime.utcnow(),
            ),
        ]
    )
    await db.commit()
    return prop


@pytest.mark.asyncio
async def test_market_context_returns_snapshot_fields(client, seeded_property_with_signals):
    prop = seeded_property_with_signals

    response = await client.get(f"/api/properties/{prop.id}/market-context")

    assert response.status_code == 200
    body = response.json()
    assert body["property_id"] == prop.id
    assert body["zip_code"] == "60614"
    assert body["neighborhood_id"] == "lincoln-park"
    assert body["jurisdiction"] == "us"
    assert body["transit_score"] == 72.0
    assert body["median_sale_price"] == 750_000.0
    assert body["inventory_pressure"] == 2.5
    assert body["hazard_flags"] == {"flood": False}


@pytest.mark.asyncio
async def test_market_context_404_for_unknown_property(client):
    response = await client.get("/api/properties/does-not-exist/market-context")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_market_context_returns_nulls_when_no_signals(client, db):
    prop = Property(
        address="No Signals St",
        asking_price=400_000,
        neighborhood_data={"zip_code": "60601"},
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)

    response = await client.get(f"/api/properties/{prop.id}/market-context")
    assert response.status_code == 200
    body = response.json()
    assert body["property_id"] == prop.id
    assert body["transit_score"] is None
    assert body["median_sale_price"] is None
    assert body["inventory_pressure"] is None
