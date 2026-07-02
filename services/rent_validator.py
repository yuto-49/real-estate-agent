"""Rent validation service — compares a property's assumed rent against local comps."""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Property, RentComp

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RentValidation:
    property_id: str
    assumed_rent_yen: int
    comp_median_yen: int
    comp_count: int
    percentile: float
    deviation_pct: float
    verdict: str          # "aligned" | "above_market" | "below_market" | "insufficient_data"
    flag: bool            # True if |deviation| > 15%
    comps_used: list[dict] = field(default_factory=list)


async def validate_rent(
    db: AsyncSession,
    property_id: str,
    *,
    min_comps: int = 3,
    menseki_tolerance: float = 0.30,
    walk_tolerance: int = 5,
    max_age_days: int = 30,
) -> RentValidation:
    """Validate a property's assumed rent against comparable listings.

    1. Load property's zip, menseki, walk_minutes
    2. Query rent_comps within same zip
    3. Filter by similar size (+-30%) and walk time (+-5 min)
    4. Compute median, percentile, deviation
    5. Flag if |deviation| > 15%
    """
    prop = await db.get(Property, property_id)
    if prop is None:
        raise ValueError(f"Property {property_id} not found")

    assumed = prop.assumed_monthly_rent_yen
    if assumed is None or assumed <= 0:
        return RentValidation(
            property_id=property_id,
            assumed_rent_yen=0,
            comp_median_yen=0,
            comp_count=0,
            percentile=0.0,
            deviation_pct=0.0,
            verdict="insufficient_data",
            flag=False,
        )

    # Query comps in same zip, not expired
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    stmt = (
        select(RentComp)
        .where(RentComp.zip_code == (prop.ward_code or prop.zip_code or ""))
        .where(RentComp.fetched_at >= cutoff)
    )
    result = await db.execute(stmt)
    all_comps = result.scalars().all()

    # Filter by similar size
    filtered: list[RentComp] = []
    for comp in all_comps:
        if prop.menseki_m2 and comp.menseki_m2:
            ratio = comp.menseki_m2 / prop.menseki_m2
            if ratio < (1 - menseki_tolerance) or ratio > (1 + menseki_tolerance):
                continue
        if prop.walk_minutes_to_station is not None and comp.walk_minutes is not None:
            if abs(comp.walk_minutes - prop.walk_minutes_to_station) > walk_tolerance:
                continue
        filtered.append(comp)

    if len(filtered) < min_comps:
        return RentValidation(
            property_id=property_id,
            assumed_rent_yen=assumed,
            comp_median_yen=0,
            comp_count=len(filtered),
            percentile=0.0,
            deviation_pct=0.0,
            verdict="insufficient_data",
            flag=False,
            comps_used=[_comp_summary(c) for c in filtered],
        )

    rents = sorted(c.monthly_rent_yen for c in filtered)
    median = int(statistics.median(rents))
    below_count = sum(1 for r in rents if r <= assumed)
    percentile = round(below_count / len(rents) * 100, 1)
    deviation = round((assumed - median) / median * 100, 1) if median else 0.0
    flagged = abs(deviation) > 15.0

    if deviation > 15.0:
        verdict = "above_market"
    elif deviation < -15.0:
        verdict = "below_market"
    else:
        verdict = "aligned"

    return RentValidation(
        property_id=property_id,
        assumed_rent_yen=assumed,
        comp_median_yen=median,
        comp_count=len(filtered),
        percentile=percentile,
        deviation_pct=deviation,
        verdict=verdict,
        flag=flagged,
        comps_used=[_comp_summary(c) for c in filtered],
    )


def _comp_summary(comp: RentComp) -> dict:
    return {
        "id": comp.id,
        "source": comp.source,
        "address_hint": comp.address_hint,
        "menseki_m2": comp.menseki_m2,
        "madori": comp.madori,
        "walk_minutes": comp.walk_minutes,
        "monthly_rent_yen": comp.monthly_rent_yen,
        "management_fee_yen": comp.management_fee_yen,
        "built_year": comp.built_year,
    }
