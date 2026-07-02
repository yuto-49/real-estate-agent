"""Satei (査定) API — comparable-based property valuation for brokerages."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from services.satei_engine import compute_satei, save_satei_session, SateiResult, AdjustedComp

router = APIRouter()


class SateiComputeRequest(BaseModel):
    city_code: str | None = None
    zip_code: str | None = None
    address: str | None = None
    menseki_m2: float | None = None
    built_year: int | None = None
    construction_type: str | None = None
    walk_minutes: int | None = None
    property_id: str | None = None
    user_id: str | None = None
    overrides: dict[str, dict[str, float]] | None = None


class AdjustmentDetailResponse(BaseModel):
    factor_name: str
    comp_value: float | int | str | None = None
    subject_value: float | int | str | None = None
    adjustment_pct: float


class AdjustedCompResponse(BaseModel):
    comp_id: str
    address_hint: str | None = None
    raw_price_yen: int
    adjusted_price_yen: int
    menseki_m2: float | None = None
    built_year: int | None = None
    construction_type: str | None = None
    walk_minutes: int | None = None
    transaction_year: int | None = None
    transaction_quarter: int | None = None
    adjustments: list[AdjustmentDetailResponse] = []
    total_adjustment_pct: float = 0.0


class SateiResponse(BaseModel):
    session_id: str | None = None
    satei_price_yen: int
    confidence_low_yen: int
    confidence_high_yen: int
    comp_count: int
    comps: list[AdjustedCompResponse] = []
    method: str = "hedonic_comparable"


@router.post("/compute", response_model=SateiResponse)
async def compute_satei_endpoint(
    body: SateiComputeRequest,
    db: AsyncSession = Depends(get_db),
) -> SateiResponse:
    """Compute satei price from comparable transactions with hedonic adjustments."""
    result = await compute_satei(
        db,
        city_code=body.city_code,
        zip_code=body.zip_code,
        menseki_m2=body.menseki_m2,
        built_year=body.built_year,
        construction_type=body.construction_type,
        walk_minutes=body.walk_minutes,
        overrides=body.overrides,
    )

    session_id = None
    if result.comp_count > 0:
        session_id = await save_satei_session(
            db,
            result,
            user_id=body.user_id,
            property_id=body.property_id,
            address=body.address,
            menseki_m2=body.menseki_m2,
            built_year=body.built_year,
            construction_type=body.construction_type,
            walk_minutes=body.walk_minutes,
        )
        await db.commit()

    return SateiResponse(
        session_id=session_id,
        satei_price_yen=result.satei_price_yen,
        confidence_low_yen=result.confidence_low_yen,
        confidence_high_yen=result.confidence_high_yen,
        comp_count=result.comp_count,
        comps=[
            AdjustedCompResponse(
                comp_id=c.comp_id,
                address_hint=c.address_hint,
                raw_price_yen=c.raw_price_yen,
                adjusted_price_yen=c.adjusted_price_yen,
                menseki_m2=c.menseki_m2,
                built_year=c.built_year,
                construction_type=c.construction_type,
                walk_minutes=c.walk_minutes,
                transaction_year=c.transaction_year,
                transaction_quarter=c.transaction_quarter,
                adjustments=[
                    AdjustmentDetailResponse(
                        factor_name=a.factor_name,
                        comp_value=a.comp_value,
                        subject_value=a.subject_value,
                        adjustment_pct=a.adjustment_pct,
                    )
                    for a in c.adjustments
                ],
                total_adjustment_pct=c.total_adjustment_pct,
            )
            for c in result.comps
        ],
        method=result.method,
    )


class SateiSessionSummary(BaseModel):
    id: str
    address: str | None = None
    satei_price_yen: int | None = None
    comp_count: int | None = None
    created_at: str | None = None


@router.get("/user/{user_id}", response_model=list[SateiSessionSummary])
async def list_satei_sessions(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[SateiSessionSummary]:
    """List saved satei sessions for a user."""
    from db.models import SateiSession as SateiSessionModel
    stmt = select(SateiSessionModel).where(
        SateiSessionModel.user_id == user_id
    ).order_by(SateiSessionModel.created_at.desc()).limit(50)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        SateiSessionSummary(
            id=r.id,
            address=r.address,
            satei_price_yen=r.satei_price_yen,
            comp_count=r.comp_count,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]


@router.get("/{session_id}", response_model=SateiResponse)
async def get_satei_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> SateiResponse:
    """Retrieve a saved satei session."""
    from db.models import SateiSession
    session = await db.get(SateiSession, session_id)
    if session is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Satei session not found")

    return SateiResponse(
        session_id=session.id,
        satei_price_yen=session.satei_price_yen or 0,
        confidence_low_yen=session.confidence_low_yen or 0,
        confidence_high_yen=session.confidence_high_yen or 0,
        comp_count=session.comp_count or 0,
        comps=[],  # Full comps require re-query; grid is in session.adjustment_grid
        method="hedonic_comparable",
    )


@router.patch("/{session_id}/adjustments", response_model=SateiResponse)
async def update_adjustments(
    session_id: str,
    overrides: dict[str, dict[str, float]],
    db: AsyncSession = Depends(get_db),
) -> SateiResponse:
    """Broker updates individual comp adjustments, server recomputes satei price."""
    from db.models import SateiSession
    session = await db.get(SateiSession, session_id)
    if session is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Satei session not found")

    result = await compute_satei(
        db,
        city_code=None,
        zip_code=None,
        menseki_m2=session.menseki_m2,
        built_year=session.built_year,
        construction_type=session.construction_type,
        walk_minutes=session.walk_minutes,
        overrides=overrides,
    )

    session.satei_price_yen = result.satei_price_yen
    session.confidence_low_yen = result.confidence_low_yen
    session.confidence_high_yen = result.confidence_high_yen
    session.updated_at = __import__("datetime").datetime.utcnow()
    await db.commit()

    return SateiResponse(
        session_id=session.id,
        satei_price_yen=result.satei_price_yen,
        confidence_low_yen=result.confidence_low_yen,
        confidence_high_yen=result.confidence_high_yen,
        comp_count=result.comp_count,
        method="hedonic_comparable",
    )
