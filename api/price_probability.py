"""Price-vs-probability curve API."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from services.price_probability import (
    compute_price_probability_curve,
    PriceProbabilityCurve,
    PriceProbabilityPoint,
)

router = APIRouter()


class PriceProbabilityRequest(BaseModel):
    satei_price_yen: int
    range_low_pct: float = -10.0
    range_high_pct: float = 20.0
    step_pct: float = 2.0
    iterations: int = Field(default=200, ge=50, le=2000)
    avg_days_on_market: int = Field(default=60, ge=14, le=365)
    demand_elasticity: float = Field(default=2.5, ge=0.5, le=5.0)


class PriceProbabilityPointResponse(BaseModel):
    asking_price_yen: int
    premium_pct: float
    p30: float
    p60: float
    p90: float
    p180: float
    expected_days: int
    expected_settlement_yen: int


class PriceProbabilityResponse(BaseModel):
    satei_price_yen: int
    points: list[PriceProbabilityPointResponse]
    iterations_per_point: int
    sweet_spot_yen: int | None = None
    sweet_spot_pct: float | None = None


@router.post("/compute", response_model=PriceProbabilityResponse)
async def compute_price_probability(
    body: PriceProbabilityRequest,
) -> PriceProbabilityResponse:
    """Compute price-vs-probability curve for asking price optimization."""
    curve = compute_price_probability_curve(
        satei_price_yen=body.satei_price_yen,
        range_low_pct=body.range_low_pct,
        range_high_pct=body.range_high_pct,
        step_pct=body.step_pct,
        iterations=body.iterations,
        avg_days_on_market=body.avg_days_on_market,
        demand_elasticity=body.demand_elasticity,
    )

    # Find sweet spot: highest price where p90 > 0.80
    sweet_spot_yen = None
    sweet_spot_pct = None
    for pt in reversed(curve.points):
        if pt.p90 >= 0.80:
            sweet_spot_yen = pt.asking_price_yen
            sweet_spot_pct = pt.premium_pct
            break

    return PriceProbabilityResponse(
        satei_price_yen=curve.satei_price_yen,
        points=[
            PriceProbabilityPointResponse(
                asking_price_yen=pt.asking_price_yen,
                premium_pct=pt.premium_pct,
                p30=pt.p30,
                p60=pt.p60,
                p90=pt.p90,
                p180=pt.p180,
                expected_days=pt.expected_days,
                expected_settlement_yen=pt.expected_settlement_yen,
            )
            for pt in curve.points
        ],
        iterations_per_point=curve.iterations_per_point,
        sweet_spot_yen=sweet_spot_yen,
        sweet_spot_pct=sweet_spot_pct,
    )
