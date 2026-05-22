"""Tests for the market-signal backfill (Phase M1.1).

Covers:
- median_sale_price derived per zip from properties.asking_price
- inventory_pressure derived per zip from active vs sold counts
- hazard signals derived from properties.hazard_flags
- idempotent re-runs (same-day rows are replaced, not duplicated)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from db.models import MarketSignal, Property, PropertyStatus
from scripts.backfill_market_signals import backfill_market_signals


async def _make_property(
    db,
    *,
    zip_code: str,
    asking_price: float,
    status: PropertyStatus = PropertyStatus.ACTIVE,
    hazard_flags: dict | None = None,
) -> Property:
    prop = Property(
        address=f"{int(asking_price)} Main St",
        asking_price=asking_price,
        status=status,
        neighborhood_data={"zip_code": zip_code, "city": "Chicago"},
        hazard_flags=hazard_flags or {},
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return prop


@pytest.mark.asyncio
async def test_backfill_writes_median_sale_price_per_zip(db):
    await _make_property(db, zip_code="60601", asking_price=300_000.0)
    await _make_property(db, zip_code="60601", asking_price=500_000.0)
    await _make_property(db, zip_code="60601", asking_price=700_000.0)
    await _make_property(db, zip_code="60610", asking_price=1_000_000.0)

    counts = await backfill_market_signals(db)

    assert counts["median_sale_price"] == 2  # one row per zip

    rows = (
        await db.execute(
            select(MarketSignal).where(MarketSignal.signal_type == "median_sale_price")
        )
    ).scalars().all()

    by_zip = {r.subject_id: r.value for r in rows}
    assert by_zip["60601"] == 500_000.0  # median of 300k/500k/700k
    assert by_zip["60610"] == 1_000_000.0
    assert all(r.subject_type == "neighborhood" for r in rows)


@pytest.mark.asyncio
async def test_backfill_writes_inventory_pressure_per_zip(db):
    # 60601: 3 active, 1 sold → pressure = 3/1 = 3.0
    await _make_property(db, zip_code="60601", asking_price=400_000, status=PropertyStatus.ACTIVE)
    await _make_property(db, zip_code="60601", asking_price=400_000, status=PropertyStatus.ACTIVE)
    await _make_property(db, zip_code="60601", asking_price=400_000, status=PropertyStatus.ACTIVE)
    await _make_property(db, zip_code="60601", asking_price=400_000, status=PropertyStatus.SOLD)
    # 60610: 1 active, 2 sold → pressure = 1/2 = 0.5
    await _make_property(db, zip_code="60610", asking_price=400_000, status=PropertyStatus.ACTIVE)
    await _make_property(db, zip_code="60610", asking_price=400_000, status=PropertyStatus.SOLD)
    await _make_property(db, zip_code="60610", asking_price=400_000, status=PropertyStatus.SOLD)

    counts = await backfill_market_signals(db)

    assert counts["inventory_pressure"] == 2

    rows = (
        await db.execute(
            select(MarketSignal).where(MarketSignal.signal_type == "inventory_pressure")
        )
    ).scalars().all()

    by_zip = {r.subject_id: r.value for r in rows}
    assert by_zip["60601"] == pytest.approx(3.0)
    assert by_zip["60610"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_backfill_writes_hazard_signals_per_property(db):
    p_with_hazards = await _make_property(
        db,
        zip_code="60601",
        asking_price=500_000,
        hazard_flags={"flood": True, "earthquake": False},
    )
    p_without = await _make_property(db, zip_code="60601", asking_price=500_000, hazard_flags={})

    counts = await backfill_market_signals(db)

    assert counts["hazard"] == 1

    rows = (
        await db.execute(
            select(MarketSignal).where(MarketSignal.signal_type == "hazard")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].subject_type == "property"
    assert rows[0].subject_id == p_with_hazards.id
    assert rows[0].payload == {"flood": True, "earthquake": False}


@pytest.mark.asyncio
async def test_backfill_is_idempotent_within_same_day(db):
    await _make_property(db, zip_code="60601", asking_price=500_000)
    await _make_property(db, zip_code="60601", asking_price=600_000)

    fixed_now = datetime(2026, 5, 9, 12, 0, 0)
    await backfill_market_signals(db, observed_at=fixed_now)
    await backfill_market_signals(db, observed_at=fixed_now)

    rows = (
        await db.execute(
            select(MarketSignal).where(
                MarketSignal.signal_type == "median_sale_price",
                MarketSignal.subject_id == "60601",
            )
        )
    ).scalars().all()
    # Same day → exactly one row, not duplicated.
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_backfill_inserts_new_row_on_different_day(db):
    await _make_property(db, zip_code="60601", asking_price=500_000)

    day1 = datetime(2026, 5, 8, 12, 0, 0)
    day2 = datetime(2026, 5, 9, 12, 0, 0)
    await backfill_market_signals(db, observed_at=day1)
    await backfill_market_signals(db, observed_at=day2)

    rows = (
        await db.execute(
            select(MarketSignal).where(
                MarketSignal.signal_type == "median_sale_price",
                MarketSignal.subject_id == "60601",
            )
        )
    ).scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_backfill_skips_zip_with_no_active_listings(db):
    # Inventory pressure is undefined when active count = 0 → row should not be written.
    await _make_property(db, zip_code="60601", asking_price=500_000, status=PropertyStatus.SOLD)

    counts = await backfill_market_signals(db)

    rows = (
        await db.execute(
            select(MarketSignal).where(
                MarketSignal.signal_type == "inventory_pressure",
                MarketSignal.subject_id == "60601",
            )
        )
    ).scalars().all()
    assert rows == []
    assert counts["inventory_pressure"] == 0


@pytest.mark.asyncio
async def test_backfill_skips_properties_without_zip(db):
    prop = Property(
        address="No Zip Property",
        asking_price=500_000,
        status=PropertyStatus.ACTIVE,
        neighborhood_data={},
    )
    db.add(prop)
    await db.commit()

    counts = await backfill_market_signals(db)
    assert counts["median_sale_price"] == 0
    assert counts["inventory_pressure"] == 0
