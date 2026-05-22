"""Backfill ``market_signals`` from the existing ``properties`` table.

Phase M1.1 of the market-signals adoption plan. Derives three signal families
from data already in the DB so the layered runtime has something to read:

* ``median_sale_price`` per zip — median of ``properties.asking_price``
  across listings (any status) keyed by neighborhood/zip.
* ``inventory_pressure`` per zip — ``active_count / sold_count`` where
  ``sold_count`` is floored at 1. Skipped when there are zero active listings.
* ``hazard`` per property — copies any non-empty ``properties.hazard_flags``
  into a hazard signal row keyed by the property id.

Idempotent within a calendar day: re-running with the same ``observed_at``
date overwrites the prior row instead of duplicating it. Different days
produce additional rows so callers can graph the time series.

Usage::

    python scripts/backfill_market_signals.py
    python scripts/backfill_market_signals.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Final

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session
from db.models import Property, PropertyStatus
from services.signal_writer import upsert_signal


SOURCE: Final[str] = "backfill"


def _zip_of(prop: Property) -> str | None:
    data = prop.neighborhood_data or {}
    zip_code = data.get("zip_code") or data.get("zip")
    return str(zip_code) if zip_code else None


async def backfill_market_signals(
    db: AsyncSession,
    *,
    observed_at: datetime | None = None,
) -> dict[str, int]:
    """Derive market_signals from the current properties table.

    Returns a count of rows written/updated per signal family. Idempotent
    within a calendar day; safe to run repeatedly.
    """
    when = observed_at or datetime.utcnow()

    properties = list((await db.execute(select(Property))).scalars().all())

    prices_by_zip: dict[str, list[float]] = defaultdict(list)
    status_counts_by_zip: dict[str, dict[PropertyStatus, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    hazard_props: list[Property] = []

    for prop in properties:
        if prop.hazard_flags:
            hazard_props.append(prop)

        zip_code = _zip_of(prop)
        if zip_code is None:
            continue

        if prop.asking_price is not None:
            prices_by_zip[zip_code].append(float(prop.asking_price))

        if prop.status is not None:
            status_counts_by_zip[zip_code][prop.status] += 1

    counts = {"median_sale_price": 0, "inventory_pressure": 0, "hazard": 0}

    for zip_code, prices in prices_by_zip.items():
        if not prices:
            continue
        median = float(statistics.median(prices))
        await upsert_signal(
            db,
            signal_type="median_sale_price",
            subject_type="neighborhood",
            subject_id=zip_code,
            value=median,
            observed_at=when,
            source=SOURCE,
        )
        counts["median_sale_price"] += 1

    for zip_code, status_counts in status_counts_by_zip.items():
        active = status_counts.get(PropertyStatus.ACTIVE, 0)
        if active == 0:
            continue
        sold = max(status_counts.get(PropertyStatus.SOLD, 0), 1)
        pressure = float(active) / float(sold)
        await upsert_signal(
            db,
            signal_type="inventory_pressure",
            subject_type="neighborhood",
            subject_id=zip_code,
            value=pressure,
            observed_at=when,
            source=SOURCE,
        )
        counts["inventory_pressure"] += 1

    for prop in hazard_props:
        await upsert_signal(
            db,
            signal_type="hazard",
            subject_type="property",
            subject_id=prop.id,
            payload=dict(prop.hazard_flags or {}),
            observed_at=when,
            source=SOURCE,
        )
        counts["hazard"] += 1

    await db.commit()
    return counts


async def _main(dry_run: bool) -> None:
    async with async_session() as db:
        if dry_run:
            counts = await backfill_market_signals(db)
            await db.rollback()
            print(f"[dry-run] would write: {counts}")
            return
        counts = await backfill_market_signals(db)
        print(f"Backfill complete: {counts}")


def _cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Roll back the transaction.")
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    _cli()
