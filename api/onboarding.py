"""Onboarding router — P1 scaffolding.

Surfaces whether a user has reached the milestones the new guided wizard
checks before routing them to ``/onboard`` or ``/portfolio``:

* ``has_portfolio`` — at least one ``InvestorPortfolio`` with at least one
  ``PortfolioHolding`` exists for the user.
* ``has_profile`` — at least one ``InvestorProfile`` row exists. The model
  is added in P4; for P1 we return ``False`` without raising so the router
  works against the current schema.

Auth is intentionally optional: when ``user_id`` is not provided (which is
the default when Supabase auth middleware is in passthrough mode), the
endpoint reports ``has_portfolio=False, has_profile=False`` so the wizard
runs cleanly in bare-DB dev.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import InvestorPortfolio, InvestorProfile, PortfolioHolding
from services.user_resolve import resolve_user_id

router = APIRouter()


class OnboardingStateResponse(BaseModel):
    """Minimal flags the frontend router gate needs."""

    user_id: str | None
    has_portfolio: bool
    has_profile: bool

    model_config = {"from_attributes": True}


async def _user_has_holdings(db: AsyncSession, user_id: str) -> bool:
    stmt = (
        select(PortfolioHolding.id)
        .join(InvestorPortfolio, InvestorPortfolio.id == PortfolioHolding.portfolio_id)
        .where(InvestorPortfolio.user_id == user_id)
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


async def _user_has_profile(db: AsyncSession, user_id: str) -> bool:
    stmt = (
        select(InvestorProfile.id)
        .where(InvestorProfile.user_id == user_id)
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


@router.get("/state", response_model=OnboardingStateResponse)
async def get_onboarding_state(
    user_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStateResponse:
    """Return the gate flags the frontend uses to decide where to route."""
    if user_id is None:
        return OnboardingStateResponse(
            user_id=None, has_portfolio=False, has_profile=False
        )

    # Accept a Supabase auth id or an internal id. If the user has no profile
    # row at all yet, there's nothing to find — report all-false (don't create).
    try:
        resolved = await resolve_user_id(db, user_id)
    except LookupError:
        return OnboardingStateResponse(
            user_id=user_id, has_portfolio=False, has_profile=False
        )

    has_portfolio = await _user_has_holdings(db, resolved)
    has_profile = await _user_has_profile(db, resolved)
    return OnboardingStateResponse(
        user_id=user_id, has_portfolio=has_portfolio, has_profile=has_profile
    )
