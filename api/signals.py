"""Lightweight signals read API — serves cached MarketSignal rows.

Supplements the per-property ``/api/properties/{id}/market-context``
endpoint by supporting zip-code-level queries for the dashboard and
search drawer.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import MarketSignal

router = APIRouter()

# Signal types we expose via this endpoint (REINFOLIB + derived)
_KNOWN_TYPES = frozenset({
    "median_sale_price",
    "median_unit_price",
    "median_rent",
    "land_price_psm",
    "appraised_value_psm",
    "hazard_liquefaction",
    "hazard_flood",
    "hazard_landslide",
    "inventory_pressure",
})


@router.get("/reinfolib")
async def get_reinfolib_signals(
    zip_code: Optional[str] = Query(None, description="Filter by zip code"),
    types: Optional[str] = Query(None, description="Comma-separated signal types"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the latest REINFOLIB / market signals for a zip code.

    Returns a flat dict resembling ``MarketContextSnapshot`` so the
    frontend can consume it with the same component used for per-property
    market context.
    """
    if not zip_code:
        return {"signals_count": 0}

    requested_types = _KNOWN_TYPES
    if types:
        requested_types = _KNOWN_TYPES & {t.strip() for t in types.split(",")}

    stmt = (
        select(MarketSignal)
        .where(
            MarketSignal.subject_id == zip_code,
            MarketSignal.signal_type.in_(requested_types),
        )
        .order_by(MarketSignal.observed_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Deduplicate: keep only the most recent row per signal_type
    seen: dict[str, MarketSignal] = {}
    for row in rows:
        if row.signal_type not in seen:
            seen[row.signal_type] = row

    # Build a flat snapshot dict
    snapshot: dict[str, object] = {
        "zip_code": zip_code,
        "signals_count": len(seen),
    }
    for signal_type, row in seen.items():
        snapshot[signal_type] = row.value

    return snapshot
