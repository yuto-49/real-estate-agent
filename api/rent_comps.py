"""Rent comp API endpoints."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import Property, RentComp
from services.rent_validator import RentValidation, validate_rent
from services.signal_providers.rent_comp_mock import generate_mock_comps

log = logging.getLogger(__name__)

router = APIRouter()


class RentCompResponse(BaseModel):
    id: str
    source: str
    address_hint: str | None
    menseki_m2: float | None
    madori: str | None
    walk_minutes: int | None
    monthly_rent_yen: int
    management_fee_yen: int | None
    built_year: int | None
    construction_type: str | None


class RentValidationResponse(BaseModel):
    property_id: str
    assumed_rent_yen: int
    comp_median_yen: int
    comp_count: int
    percentile: float
    deviation_pct: float
    verdict: str
    flag: bool
    comps: list[RentCompResponse]


class RefreshResponse(BaseModel):
    comps_added: int
    validation: RentValidationResponse


@router.get("/{property_id}/rent-comps")
async def get_rent_comps(
    property_id: str,
    db: AsyncSession = Depends(get_db),
) -> RentValidationResponse:
    """Return rent validation + comparable listings for a property."""
    prop = await db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    validation = await validate_rent(db, property_id)

    return RentValidationResponse(
        property_id=validation.property_id,
        assumed_rent_yen=validation.assumed_rent_yen,
        comp_median_yen=validation.comp_median_yen,
        comp_count=validation.comp_count,
        percentile=validation.percentile,
        deviation_pct=validation.deviation_pct,
        verdict=validation.verdict,
        flag=validation.flag,
        comps=[
            RentCompResponse(**c)
            for c in validation.comps_used
        ],
    )


@router.post("/{property_id}/rent-comps/refresh")
async def refresh_rent_comps(
    property_id: str,
    db: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    """Fetch fresh comps from providers and re-validate.

    Currently uses mock provider; real SUUMO scraper available via
    services.signal_providers.suumo_rent for live fetching.
    """
    prop = await db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    zip_code = prop.ward_code or prop.zip_code or ""
    if not zip_code:
        raise HTTPException(status_code=400, detail="Property has no zip/ward code")

    # Try real SUUMO scraper first, fall back to mock
    new_comps: list[RentComp] = []
    try:
        from services.signal_providers.suumo_rent import (
            SuumoSearchParams,
            fetch_suumo_comps,
        )
        params = SuumoSearchParams(
            ward_code=zip_code,
            menseki_min=max((prop.menseki_m2 or 20) * 0.7, 10),
            menseki_max=min((prop.menseki_m2 or 30) * 1.3, 100),
            walk_max=min((prop.walk_minutes_to_station or 10) + 5, 20),
        )
        new_comps = await fetch_suumo_comps(params, property_id=property_id)
    except Exception:
        log.info("SUUMO scraper unavailable, using mock comps for %s", zip_code)

    if not new_comps:
        new_comps = generate_mock_comps(zip_code, property_id=property_id)

    for comp in new_comps:
        db.add(comp)
    await db.commit()

    validation = await validate_rent(db, property_id)

    return RefreshResponse(
        comps_added=len(new_comps),
        validation=RentValidationResponse(
            property_id=validation.property_id,
            assumed_rent_yen=validation.assumed_rent_yen,
            comp_median_yen=validation.comp_median_yen,
            comp_count=validation.comp_count,
            percentile=validation.percentile,
            deviation_pct=validation.deviation_pct,
            verdict=validation.verdict,
            flag=validation.flag,
            comps=[RentCompResponse(**c) for c in validation.comps_used],
        ),
    )
