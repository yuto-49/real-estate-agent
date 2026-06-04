"""Persona analyst council endpoint — POST /api/listings/{id}/analyze."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.analyst_council import review_listing
from api.schemas import (
    AnalystVerdictSchema,
    ListingAnalysisRequest,
    ListingAnalysisResponse,
)
from db.database import get_db
from db.models import Property

router = APIRouter()


def _infer_age_years(prop: Property) -> int | None:
    if prop.built_year is None:
        return None
    age = datetime.utcnow().year - int(prop.built_year)
    return max(0, age)


@router.post("/{listing_id}/analyze", response_model=ListingAnalysisResponse)
async def analyze_listing(
    listing_id: str,
    overrides: ListingAnalysisRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> ListingAnalysisResponse:
    prop = (
        await db.execute(select(Property).where(Property.id == listing_id))
    ).scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="listing_not_found")

    overrides = overrides or ListingAnalysisRequest()
    age_years = (
        overrides.building_age_years
        if overrides.building_age_years is not None
        else _infer_age_years(prop)
    )

    analysis = await review_listing(
        prop,
        building_basis_yen=overrides.building_basis_yen,
        building_age_years=age_years,
        marginal_tax_rate=overrides.marginal_tax_rate,
    )

    return ListingAnalysisResponse(
        listing_id=analysis.listing_id,
        overall_score=analysis.overall_score,
        summary=analysis.summary,
        verdicts=[
            AnalystVerdictSchema(
                persona_key=v.persona_key,
                persona_title_ja=v.persona_title_ja,
                payload=v.payload,
                error=v.error,
            )
            for v in analysis.verdicts
        ],
    )
