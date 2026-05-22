"""GET /api/decisions/holding/{id} — Phase P4.

Thin HTTP wrapper over ``services.holding_decision``. The logic lives in
the service module so the portfolio summary aggregator (Phase S2) can
reuse it without re-deriving snapshots or rebuilding the policy runtime.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import HoldingDecisionResponse
from db.database import get_db
from db.models import HoldingFinancials, PortfolioHolding
from services.holding_decision import compute_holding_decision

router = APIRouter()


@router.get("/holding/{holding_id}", response_model=HoldingDecisionResponse)
async def holding_decision(
    holding_id: str, db: AsyncSession = Depends(get_db)
) -> HoldingDecisionResponse:
    """Recommend an investor action for a single holding."""
    holding = (
        await db.execute(
            select(PortfolioHolding).where(PortfolioHolding.id == holding_id)
        )
    ).scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=404, detail="holding_not_found")

    fin = (
        await db.execute(
            select(HoldingFinancials).where(
                HoldingFinancials.holding_id == holding_id
            )
        )
    ).scalar_one_or_none()

    return await compute_holding_decision(db, holding, fin)
