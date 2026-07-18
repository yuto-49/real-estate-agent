"""REINFOLIB signals must reach the Analysis / Simulation / Portfolio surface.

The MLIT providers key their signals by 5-digit municipality code
(``subject_id="13103"``) and emit JP-native signal types. ``build_snapshot``
historically resolved neighborhood signals by ``neighborhood_id``/``zip_code``
only, and recognised a single generic ``hazard`` type — so REINFOLIB rows were
persisted and then silently dropped at read time.

These tests pin the JP read path: ward-code resolution, the JP scalar fields,
and hazard aggregation across the three REINFOLIB hazard types.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import pytest
from db.models import MarketSignal, Property
from services.market_state import build_snapshot


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_jp_property(db_engine, signals: list[tuple[str, str, float]]) -> str:
    """A Tokyo property in Minato-ku (13103) plus REINFOLIB-shaped signals.

    ``signals`` items are ``(signal_type, subject_id, value)`` at neighborhood level.
    """
    async with _factory(db_engine)() as s:
        prop = Property(
            address="1-1 Motoazabu, Minato-ku",
            asking_price=94_000_000,
            ward_code="13103",
            jurisdiction="jp",
            currency="JPY",
        )
        s.add(prop)
        await s.flush()
        prop_id = prop.id
        for signal_type, subject_id, value in signals:
            s.add(
                MarketSignal(
                    signal_type=signal_type,
                    subject_type="neighborhood",
                    subject_id=subject_id,
                    value=value,
                    observed_at=datetime.utcnow(),
                )
            )
        await s.commit()
    return prop_id


@pytest.mark.asyncio
async def test_ward_code_resolves_reinfolib_municipality_signals(db_engine):
    """A property's ward_code must match REINFOLIB's municipality-keyed signals."""
    prop_id = await _seed_jp_property(
        db_engine, [("median_sale_price", "13103", 94_000_000.0)]
    )
    async with _factory(db_engine)() as s:
        snap = await build_snapshot(s, prop_id)

    assert snap is not None
    assert snap.median_sale_price == 94_000_000.0


@pytest.mark.asyncio
async def test_jp_scalar_signals_reach_snapshot(db_engine):
    """land_price_psm / appraised_value_psm / median_unit_price must not be dropped."""
    prop_id = await _seed_jp_property(
        db_engine,
        [
            ("median_unit_price", "13103", 8_250_000.0),
            ("land_price_psm", "13103", 4_100_000.0),
            ("appraised_value_psm", "13103", 3_900_000.0),
        ],
    )
    async with _factory(db_engine)() as s:
        snap = await build_snapshot(s, prop_id)

    assert snap is not None
    assert snap.median_unit_price == 8_250_000.0
    assert snap.land_price_psm == 4_100_000.0
    assert snap.appraised_value_psm == 3_900_000.0


@pytest.mark.asyncio
async def test_reinfolib_hazard_types_aggregate_into_hazard_flags(db_engine):
    """The three REINFOLIB hazard types must land in hazard_flags."""
    prop_id = await _seed_jp_property(
        db_engine,
        [
            ("hazard_flood", "13103", 3.0),
            ("hazard_landslide", "13103", 1.0),
            ("hazard_liquefaction", "13103", 2.0),
        ],
    )
    async with _factory(db_engine)() as s:
        snap = await build_snapshot(s, prop_id)

    assert snap is not None
    assert snap.hazard_flags.get("flood") == 3.0
    assert snap.hazard_flags.get("landslide") == 1.0
    assert snap.hazard_flags.get("liquefaction") == 2.0


@pytest.mark.asyncio
async def test_zip_code_resolution_still_works(db_engine):
    """Regression: the existing zip-keyed (US/backfill) path must not break."""
    async with _factory(db_engine)() as s:
        prop = Property(
            address="123 W Chicago Ave",
            asking_price=500_000,
            neighborhood_data={"zip_code": "60614"},
            jurisdiction="us",
        )
        s.add(prop)
        await s.flush()
        prop_id = prop.id
        s.add(
            MarketSignal(
                signal_type="median_sale_price",
                subject_type="neighborhood",
                subject_id="60614",
                value=500_000.0,
                observed_at=datetime.utcnow(),
            )
        )
        await s.commit()

    async with _factory(db_engine)() as s:
        snap = await build_snapshot(s, prop_id)

    assert snap is not None
    assert snap.median_sale_price == 500_000.0
