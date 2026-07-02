"""Buyer simulation API — GNN-powered buyer agent simulation for Tokyo properties."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from services.buyer_simulation import run_buyer_simulation

router = APIRouter(tags=["buyer-simulation"])


class BuyerSimRequest(BaseModel):
    property_id: str
    n_buyers: int = Field(default=50, ge=10, le=200)
    max_rounds: int = Field(default=15, ge=5, le=30)
    seed: int | None = None


class SegmentResponse(BaseModel):
    life_stage: str
    count: int
    avg_bid_yen: int
    median_bid_yen: int
    win_rate: float


class BidBucketResponse(BaseModel):
    low_yen: int
    high_yen: int
    count: int


class BuyerSimResponse(BaseModel):
    property_id: str
    gnn_valuation_yen: int
    gnn_confidence_low_yen: int
    gnn_confidence_high_yen: int
    satei_price_yen: int | None = None
    price_probability_sweet_spot_yen: int | None = None
    buyer_segments: list[SegmentResponse]
    bid_histogram: list[BidBucketResponse]
    median_bid_yen: int
    mean_bid_yen: int
    hazard_impact_pct: float
    rounds_to_converge: int
    narrative_jp: str


@router.post("/run", response_model=BuyerSimResponse)
async def run_simulation(
    req: BuyerSimRequest,
    db: AsyncSession = Depends(get_db),
) -> BuyerSimResponse:
    """Run a GNN-powered buyer simulation and return valuation report."""
    try:
        report = await run_buyer_simulation(
            db,
            req.property_id,
            req.n_buyers,
            req.max_rounds,
            req.seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    segments = [
        SegmentResponse(**asdict(seg)) for seg in report.buyer_segments
    ]
    histogram = [
        BidBucketResponse(**asdict(bucket)) for bucket in report.bid_histogram
    ]

    return BuyerSimResponse(
        property_id=report.property_id,
        gnn_valuation_yen=report.gnn_valuation_yen,
        gnn_confidence_low_yen=report.gnn_confidence_low_yen,
        gnn_confidence_high_yen=report.gnn_confidence_high_yen,
        satei_price_yen=report.satei_price_yen,
        price_probability_sweet_spot_yen=report.price_probability_sweet_spot_yen,
        buyer_segments=segments,
        bid_histogram=histogram,
        median_bid_yen=report.median_bid_yen,
        mean_bid_yen=report.mean_bid_yen,
        hazard_impact_pct=report.hazard_impact_pct,
        rounds_to_converge=report.rounds_to_converge,
        narrative_jp=report.narrative_jp,
    )
