"""Investor profile router (onboarding wizard P4).

The wizard's "no portfolio" branch collects budget, strategy, return target,
and geography. We persist one row per user — re-submits upsert in place.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    InvestorProfileGeography,
    InvestorProfileResponse,
    InvestorProfileUpsert,
)
from db.database import get_db
from db.models import InvestorProfile
from services.user_resolve import resolve_user_id

router = APIRouter()


def _to_response(row: InvestorProfile) -> InvestorProfileResponse:
    geo = row.geography or {}
    return InvestorProfileResponse(
        id=row.id,
        user_id=row.user_id,
        budget=row.budget,
        strategy=row.strategy,
        target_cap_rate=row.target_cap_rate,
        target_coc=row.target_coc,
        geography=InvestorProfileGeography(
            zip=geo.get("zip"),
            city=geo.get("city"),
            state=geo.get("state"),
            prefecture=geo.get("prefecture"),
            municipality=geo.get("municipality"),
            ward=geo.get("ward"),
            neighborhood=geo.get("neighborhood"),
            station=geo.get("station"),
        ),
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/", response_model=InvestorProfileResponse, status_code=201)
async def upsert_investor_profile(
    payload: InvestorProfileUpsert,
    db: AsyncSession = Depends(get_db),
) -> InvestorProfileResponse:
    """Insert or update the investor profile for ``payload.user_id``.

    Accepts either an internal ``UserProfile.id`` or a Supabase auth id, and
    auto-provisions a profile for an authenticated user who doesn't have one
    yet (when ``user_email`` is supplied).
    """
    try:
        user_id = await resolve_user_id(
            db,
            payload.user_id,
            email=payload.user_email,
            name=payload.user_name,
            auto_create=True,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="user_not_found")

    existing = (
        await db.execute(
            select(InvestorProfile).where(InvestorProfile.user_id == user_id)
        )
    ).scalar_one_or_none()

    geography_payload = payload.geography.model_dump(exclude_none=True)

    if existing is None:
        row = InvestorProfile(
            user_id=user_id,
            budget=payload.budget,
            strategy=payload.strategy,
            target_cap_rate=payload.target_cap_rate,
            target_coc=payload.target_coc,
            geography=geography_payload,
            notes=payload.notes,
        )
        db.add(row)
    else:
        existing.budget = payload.budget
        existing.strategy = payload.strategy
        existing.target_cap_rate = payload.target_cap_rate
        existing.target_coc = payload.target_coc
        existing.geography = geography_payload
        existing.notes = payload.notes
        row = existing

    await db.commit()
    await db.refresh(row)
    return _to_response(row)


@router.get("/", response_model=InvestorProfileResponse)
async def get_investor_profile(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> InvestorProfileResponse:
    try:
        resolved = await resolve_user_id(db, user_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="profile_not_found")
    row = (
        await db.execute(
            select(InvestorProfile).where(InvestorProfile.user_id == resolved)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="profile_not_found")
    return _to_response(row)
