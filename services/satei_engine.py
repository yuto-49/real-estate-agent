"""Satei (査定) engine — comparable-based property valuation with hedonic adjustments.

Pulls cached SaleComp records, filters by similarity, applies a hedonic
adjustment grid, and produces a weighted-average satei price with confidence band.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Property, SaleComp, SateiSession

log = logging.getLogger(__name__)

# Default adjustment factors (percentage per unit difference)
_AGE_FACTOR = -0.5          # -0.5% per year older than subject
_AREA_FACTOR = -0.3         # -0.3% per m² smaller than subject
_WALK_FACTOR = -1.0         # -1.0% per minute farther from station
_CONSTRUCTION_PREMIA: dict[str, float] = {
    "SRC": 5.0, "RC": 3.0, "鉄骨": 1.0, "軽量鉄骨": 0.0, "木造": -2.0,
}


@dataclass(frozen=True)
class AdjustmentDetail:
    factor_name: str
    comp_value: float | int | str | None
    subject_value: float | int | str | None
    adjustment_pct: float


@dataclass(frozen=True)
class AdjustedComp:
    comp_id: str
    address_hint: str | None
    raw_price_yen: int
    adjusted_price_yen: int
    menseki_m2: float | None
    built_year: int | None
    construction_type: str | None
    walk_minutes: int | None
    transaction_year: int | None
    transaction_quarter: int | None
    adjustments: tuple[AdjustmentDetail, ...] = ()
    total_adjustment_pct: float = 0.0


@dataclass(frozen=True)
class SateiResult:
    satei_price_yen: int
    confidence_low_yen: int
    confidence_high_yen: int
    comp_count: int
    comps: tuple[AdjustedComp, ...] = ()
    method: str = "hedonic_comparable"


async def compute_satei(
    db: AsyncSession,
    *,
    city_code: str | None = None,
    zip_code: str | None = None,
    menseki_m2: float | None = None,
    built_year: int | None = None,
    construction_type: str | None = None,
    walk_minutes: int | None = None,
    menseki_tolerance: float = 0.30,
    walk_tolerance: int = 5,
    min_comps: int = 3,
    max_comps: int = 20,
    overrides: dict[str, dict[str, float]] | None = None,
) -> SateiResult:
    """Compute satei price from cached SaleComp records.

    Parameters
    ----------
    overrides:
        Optional per-comp adjustment overrides.
        Keys are comp IDs, values are dicts of {factor_name: override_pct}.
    """
    lookup_key = city_code or zip_code or ""
    if not lookup_key:
        return SateiResult(satei_price_yen=0, confidence_low_yen=0, confidence_high_yen=0, comp_count=0)

    # Query comps
    stmt = select(SaleComp)
    if city_code:
        stmt = stmt.where(SaleComp.city_code == city_code)
    elif zip_code:
        stmt = stmt.where(SaleComp.zip_code == zip_code)
    stmt = stmt.order_by(SaleComp.fetched_at.desc()).limit(200)

    result = await db.execute(stmt)
    all_comps = result.scalars().all()

    # Filter by similarity
    filtered: list[SaleComp] = []
    for comp in all_comps:
        if menseki_m2 and comp.menseki_m2:
            ratio = comp.menseki_m2 / menseki_m2
            if ratio < (1 - menseki_tolerance) or ratio > (1 + menseki_tolerance):
                continue
        if walk_minutes is not None and comp.walk_minutes is not None:
            if abs(comp.walk_minutes - walk_minutes) > walk_tolerance:
                continue
        filtered.append(comp)

    if len(filtered) < min_comps:
        return SateiResult(satei_price_yen=0, confidence_low_yen=0, confidence_high_yen=0, comp_count=len(filtered))

    # Limit to most recent comps
    filtered = filtered[:max_comps]

    # Apply hedonic adjustments
    adjusted_comps: list[AdjustedComp] = []
    for comp in filtered:
        adjustments, total_pct = _compute_adjustments(
            comp, menseki_m2, built_year, construction_type, walk_minutes,
            overrides.get(comp.id, {}) if overrides else {},
        )
        adj_price = int(comp.trade_price_yen * (1 + total_pct / 100))
        adjusted_comps.append(AdjustedComp(
            comp_id=comp.id,
            address_hint=comp.address_hint,
            raw_price_yen=comp.trade_price_yen,
            adjusted_price_yen=adj_price,
            menseki_m2=comp.menseki_m2,
            built_year=comp.built_year,
            construction_type=comp.construction_type,
            walk_minutes=comp.walk_minutes,
            transaction_year=comp.transaction_year,
            transaction_quarter=comp.transaction_quarter,
            adjustments=tuple(adjustments),
            total_adjustment_pct=total_pct,
        ))

    prices = [c.adjusted_price_yen for c in adjusted_comps]
    satei = int(statistics.mean(prices))
    stdev = int(statistics.stdev(prices)) if len(prices) > 1 else 0

    return SateiResult(
        satei_price_yen=satei,
        confidence_low_yen=satei - stdev,
        confidence_high_yen=satei + stdev,
        comp_count=len(adjusted_comps),
        comps=tuple(adjusted_comps),
    )


def _compute_adjustments(
    comp: SaleComp,
    subject_menseki: float | None,
    subject_year: int | None,
    subject_construction: str | None,
    subject_walk: int | None,
    overrides: dict[str, float],
) -> tuple[list[AdjustmentDetail], float]:
    """Compute hedonic adjustments for a single comp. Returns (details, total_pct)."""
    details: list[AdjustmentDetail] = []
    total = 0.0

    # Age adjustment
    if subject_year and comp.built_year:
        age_diff = comp.built_year - subject_year  # positive = comp is newer
        pct = overrides.get("age", age_diff * _AGE_FACTOR)
        details.append(AdjustmentDetail("age", comp.built_year, subject_year, pct))
        total += pct

    # Floor area adjustment
    if subject_menseki and comp.menseki_m2:
        area_diff = comp.menseki_m2 - subject_menseki  # positive = comp is larger
        pct = overrides.get("area", area_diff * _AREA_FACTOR)
        details.append(AdjustmentDetail("area", comp.menseki_m2, subject_menseki, pct))
        total += pct

    # Walk time adjustment
    if subject_walk is not None and comp.walk_minutes is not None:
        walk_diff = comp.walk_minutes - subject_walk  # positive = comp farther
        pct = overrides.get("walk", walk_diff * _WALK_FACTOR)
        details.append(AdjustmentDetail("walk", comp.walk_minutes, subject_walk, pct))
        total += pct

    # Construction type adjustment
    if subject_construction and comp.construction_type:
        comp_premium = _CONSTRUCTION_PREMIA.get(comp.construction_type, 0.0)
        subj_premium = _CONSTRUCTION_PREMIA.get(subject_construction, 0.0)
        pct = overrides.get("construction", comp_premium - subj_premium)
        details.append(AdjustmentDetail("construction", comp.construction_type, subject_construction, pct))
        total += pct

    return details, round(total, 2)


async def save_satei_session(
    db: AsyncSession,
    result: SateiResult,
    *,
    user_id: str | None = None,
    property_id: str | None = None,
    address: str | None = None,
    menseki_m2: float | None = None,
    built_year: int | None = None,
    construction_type: str | None = None,
    walk_minutes: int | None = None,
) -> str:
    """Persist a satei result and return the session ID."""
    session = SateiSession(
        user_id=user_id,
        property_id=property_id,
        address=address,
        menseki_m2=menseki_m2,
        built_year=built_year,
        construction_type=construction_type,
        walk_minutes=walk_minutes,
        satei_price_yen=result.satei_price_yen,
        confidence_low_yen=result.confidence_low_yen,
        confidence_high_yen=result.confidence_high_yen,
        comp_count=result.comp_count,
        adjustment_grid=[
            {
                "comp_id": c.comp_id,
                "raw_price": c.raw_price_yen,
                "adjusted_price": c.adjusted_price_yen,
                "total_adjustment_pct": c.total_adjustment_pct,
                "adjustments": [
                    {"factor": a.factor_name, "comp_val": a.comp_value,
                     "subject_val": a.subject_value, "pct": a.adjustment_pct}
                    for a in c.adjustments
                ],
            }
            for c in result.comps
        ],
        result_payload={
            "satei_price_yen": result.satei_price_yen,
            "confidence_low_yen": result.confidence_low_yen,
            "confidence_high_yen": result.confidence_high_yen,
            "comp_count": result.comp_count,
            "method": result.method,
        },
    )
    db.add(session)
    await db.flush()
    return session.id
