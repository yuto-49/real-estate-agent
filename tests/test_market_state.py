"""Phase B market-state snapshot builder tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from db.models import MarketSignal, Property
from domain.market.models import MarketContextSnapshot
from services.market_state import (
    SUBJECT_NEIGHBORHOOD,
    SUBJECT_PROPERTY,
    build_snapshot,
)


async def _make_property(db, **overrides) -> Property:
    prop = Property(
        address=overrides.pop("address", "100 Main St"),
        asking_price=overrides.pop("asking_price", 500_000.0),
        latitude=overrides.pop("latitude", 37.7749),
        longitude=overrides.pop("longitude", -122.4194),
        neighborhood_data=overrides.pop("neighborhood_data", {}),
        hazard_flags=overrides.pop("hazard_flags", {}),
        jurisdiction=overrides.pop("jurisdiction", "us"),
        **overrides,
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return prop


async def _add_signal(
    db,
    *,
    signal_type: str,
    subject_type: str,
    subject_id: str,
    value: float | None = None,
    payload: dict | None = None,
    observed_at: datetime | None = None,
) -> MarketSignal:
    signal = MarketSignal(
        signal_type=signal_type,
        subject_type=subject_type,
        subject_id=subject_id,
        value=value,
        payload=payload or {},
        observed_at=observed_at or datetime.utcnow(),
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal


@pytest.mark.asyncio
async def test_build_snapshot_returns_none_for_missing_property(db):
    snapshot = await build_snapshot(db, property_id="does-not-exist")
    assert snapshot is None


@pytest.mark.asyncio
async def test_build_snapshot_populates_property_context(db):
    prop = await _make_property(
        db,
        neighborhood_data={"neighborhood_id": "mission-sf", "zip_code": "94110"},
        jurisdiction="us",
    )

    snapshot = await build_snapshot(db, property_id=prop.id)

    assert isinstance(snapshot, MarketContextSnapshot)
    assert snapshot.property_id == prop.id
    assert snapshot.neighborhood_id == "mission-sf"
    assert snapshot.zip_code == "94110"
    assert snapshot.jurisdiction == "us"


@pytest.mark.asyncio
async def test_build_snapshot_folds_scalar_signals(db):
    prop = await _make_property(db)
    await _add_signal(
        db,
        signal_type="transit_score",
        subject_type=SUBJECT_PROPERTY,
        subject_id=prop.id,
        value=87.5,
    )
    await _add_signal(
        db,
        signal_type="school_score",
        subject_type=SUBJECT_PROPERTY,
        subject_id=prop.id,
        value=72.0,
    )
    await _add_signal(
        db,
        signal_type="median_rent",
        subject_type=SUBJECT_PROPERTY,
        subject_id=prop.id,
        value=3400.0,
    )

    snapshot = await build_snapshot(db, property_id=prop.id)

    assert snapshot is not None
    assert snapshot.transit_score == 87.5
    assert snapshot.school_score == 72.0
    assert snapshot.median_rent == 3400.0


@pytest.mark.asyncio
async def test_build_snapshot_uses_most_recent_signal_per_type(db):
    prop = await _make_property(db)
    older = datetime.utcnow() - timedelta(days=30)
    newer = datetime.utcnow()

    await _add_signal(
        db,
        signal_type="transit_score",
        subject_type=SUBJECT_PROPERTY,
        subject_id=prop.id,
        value=50.0,
        observed_at=older,
    )
    await _add_signal(
        db,
        signal_type="transit_score",
        subject_type=SUBJECT_PROPERTY,
        subject_id=prop.id,
        value=90.0,
        observed_at=newer,
    )

    snapshot = await build_snapshot(db, property_id=prop.id)

    assert snapshot is not None
    assert snapshot.transit_score == 90.0


@pytest.mark.asyncio
async def test_build_snapshot_extracts_zoning_from_payload(db):
    prop = await _make_property(db)
    await _add_signal(
        db,
        signal_type="zoning",
        subject_type=SUBJECT_PROPERTY,
        subject_id=prop.id,
        payload={"code": "RH-2", "max_height_ft": 40},
    )

    snapshot = await build_snapshot(db, property_id=prop.id)

    assert snapshot is not None
    assert snapshot.zoning_code == "RH-2"


@pytest.mark.asyncio
async def test_build_snapshot_merges_hazard_flags(db):
    prop = await _make_property(db, hazard_flags={"flood_zone": "X"})
    await _add_signal(
        db,
        signal_type="hazard",
        subject_type=SUBJECT_PROPERTY,
        subject_id=prop.id,
        payload={"liquefaction": True, "wildfire_risk": "moderate"},
    )

    snapshot = await build_snapshot(db, property_id=prop.id)

    assert snapshot is not None
    assert snapshot.hazard_flags["flood_zone"] == "X"
    assert snapshot.hazard_flags["liquefaction"] is True
    assert snapshot.hazard_flags["wildfire_risk"] == "moderate"


@pytest.mark.asyncio
async def test_neighborhood_signals_fill_gaps_only(db):
    prop = await _make_property(
        db, neighborhood_data={"neighborhood_id": "soma-sf"}
    )
    # Property-level transit signal wins.
    await _add_signal(
        db,
        signal_type="transit_score",
        subject_type=SUBJECT_PROPERTY,
        subject_id=prop.id,
        value=95.0,
    )
    # Neighborhood-level transit signal should be ignored when property-level exists.
    await _add_signal(
        db,
        signal_type="transit_score",
        subject_type=SUBJECT_NEIGHBORHOOD,
        subject_id="soma-sf",
        value=60.0,
    )
    # Neighborhood-only median_rent fills the gap.
    await _add_signal(
        db,
        signal_type="median_rent",
        subject_type=SUBJECT_NEIGHBORHOOD,
        subject_id="soma-sf",
        value=4200.0,
    )

    snapshot = await build_snapshot(db, property_id=prop.id)

    assert snapshot is not None
    assert snapshot.transit_score == 95.0
    assert snapshot.median_rent == 4200.0


@pytest.mark.asyncio
async def test_unknown_signal_type_is_ignored(db):
    prop = await _make_property(db)
    await _add_signal(
        db,
        signal_type="something_made_up",
        subject_type=SUBJECT_PROPERTY,
        subject_id=prop.id,
        value=42.0,
    )

    snapshot = await build_snapshot(db, property_id=prop.id)

    assert snapshot is not None
    # No exception, no field corruption.
    assert snapshot.transit_score is None
