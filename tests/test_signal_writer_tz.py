"""``upsert_signal`` must normalise timezone-aware timestamps to naive UTC.

``market_signals.observed_at`` is ``TIMESTAMP WITHOUT TIME ZONE``. The JP
(REINFOLIB) providers stamp signals with ``datetime.now(UTC)`` — timezone-aware
— which asyncpg rejects outright ("can't subtract offset-naive and offset-aware
datetimes"). SQLite silently accepts it, so this only fails against real
Postgres; normalising at the single shared writer keeps every provider safe.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from services.signal_writer import upsert_signal


def _factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_aware_observed_at_is_stored_naive(db_engine):
    """An aware UTC stamp must be persisted as naive UTC."""
    async with _factory(db_engine)() as db:
        row = await upsert_signal(
            db,
            signal_type="median_sale_price",
            subject_type="neighborhood",
            subject_id="13103",
            value=94_000_000.0,
            observed_at=datetime.now(UTC),
            source="reinfolib_transaction",
        )
        await db.commit()

    assert row.observed_at.tzinfo is None, "aware datetime reached a naive column"


@pytest.mark.asyncio
async def test_non_utc_offset_is_converted_to_utc_not_truncated(db_engine):
    """A +09:00 (JST) stamp must convert to UTC, not just drop its offset."""
    jst = timezone(timedelta(hours=9))
    # 2026-07-17 09:00 JST == 2026-07-17 00:00 UTC
    aware = datetime(2026, 7, 17, 9, 0, tzinfo=jst)

    async with _factory(db_engine)() as db:
        row = await upsert_signal(
            db,
            signal_type="land_price_psm",
            subject_type="neighborhood",
            subject_id="13104",
            value=4_100_000.0,
            observed_at=aware,
            source="reinfolib_land_price",
        )
        await db.commit()

    assert row.observed_at.tzinfo is None
    assert row.observed_at == datetime(2026, 7, 17, 0, 0), (
        f"expected UTC conversion, got {row.observed_at}"
    )


@pytest.mark.asyncio
async def test_naive_observed_at_still_passes_through(db_engine):
    """Regression: the existing naive path (US providers/backfill) is untouched."""
    naive = datetime(2026, 7, 17, 12, 30)

    async with _factory(db_engine)() as db:
        row = await upsert_signal(
            db,
            signal_type="median_rent",
            subject_type="neighborhood",
            subject_id="60614",
            value=2_400.0,
            observed_at=naive,
        )
        await db.commit()

    assert row.observed_at == naive
