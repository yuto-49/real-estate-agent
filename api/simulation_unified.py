"""Unified simulation API router.

POST /run           — launch a simulation run for a holding
GET  /{run_id}/replay — retrieve round-by-round replay data
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from domain.simulation.loop import run_simulation
from domain.simulation.models import PolicyShock, SimConfig
from services.sim_orchestrator import (
    build_sim_seed_from_holding,
)

router = APIRouter()

# In-memory result cache (same pattern as strategy_runner)
_results: dict[str, dict[str, Any]] = {}


# ── Request / Response schemas ────────────────────────────────────────


class ShockInput(BaseModel):
    round_num: int
    shock_type: str
    magnitude: float = 0.0
    label: str = ""


class SimRunRequest(BaseModel):
    holding_id: str
    portfolio_id: str = ""
    max_rounds: int = Field(default=20, ge=1, le=100)
    shocks: list[ShockInput] = Field(default_factory=list)
    convergence_threshold: float = 0.02


class SimRunResponse(BaseModel):
    run_id: str
    status: str
    recommendation: str | None = None
    converged: bool = False
    converged_at_round: int | None = None
    final_noi: float | None = None
    final_dscr: float | None = None
    final_cap_rate: float | None = None
    final_occupancy: float | None = None
    rounds_count: int = 0


class ReplayRound(BaseModel):
    round_num: int
    noi: float
    occupancy: float
    dscr: float
    cap_rate: float
    recommendation: str
    shocks: list[str]
    churn_avg: float


class ReplayResponse(BaseModel):
    run_id: str
    rounds: list[ReplayRound]
    converged: bool
    converged_at_round: int | None = None


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/run", response_model=SimRunResponse)
async def run_unified_simulation(
    req: SimRunRequest,
    db: AsyncSession = Depends(get_db),
) -> SimRunResponse:
    """Run the unified simulation for a single holding."""
    seed = await build_sim_seed_from_holding(db, req.holding_id)
    if seed is None:
        raise HTTPException(status_code=404, detail="Holding not found")

    shocks = tuple(
        PolicyShock(
            round_num=s.round_num,
            shock_type=s.shock_type,
            magnitude=s.magnitude,
            label=s.label,
        )
        for s in req.shocks
    )
    config = SimConfig(
        max_rounds=req.max_rounds,
        convergence_threshold=req.convergence_threshold,
        shocks=shocks,
    )

    result = run_simulation(config, seed)

    import uuid

    run_id = str(uuid.uuid4())
    _results[run_id] = {
        "result": result,
        "holding_id": req.holding_id,
        "portfolio_id": req.portfolio_id,
    }

    final = result.final_property
    return SimRunResponse(
        run_id=run_id,
        status="completed",
        recommendation=result.final_investor.recommendation,
        converged=result.converged,
        converged_at_round=result.converged_at_round,
        final_noi=final.annual_noi,
        final_dscr=final.dscr,
        final_cap_rate=final.cap_rate,
        final_occupancy=final.occupancy_rate,
        rounds_count=len(result.rounds),
    )


@router.get("/{run_id}/replay", response_model=ReplayResponse)
async def get_simulation_replay(run_id: str) -> ReplayResponse:
    """Retrieve round-by-round replay data for a completed simulation."""
    entry = _results.get(run_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Simulation run not found")

    result = entry["result"]
    rounds: list[ReplayRound] = []
    for rnd in result.rounds:
        cohort_churn = (
            sum(c.churn_probability for c in rnd.cohorts) / len(rnd.cohorts)
            if rnd.cohorts
            else 0.0
        )
        rounds.append(
            ReplayRound(
                round_num=rnd.round_num,
                noi=rnd.property_state.annual_noi,
                occupancy=rnd.property_state.occupancy_rate,
                dscr=rnd.property_state.dscr,
                cap_rate=rnd.property_state.cap_rate,
                recommendation=rnd.investor_trace.recommendation,
                shocks=[s.label or s.shock_type for s in rnd.shocks_applied],
                churn_avg=round(cohort_churn, 4),
            )
        )

    return ReplayResponse(
        run_id=run_id,
        rounds=rounds,
        converged=result.converged,
        converged_at_round=result.converged_at_round,
    )
