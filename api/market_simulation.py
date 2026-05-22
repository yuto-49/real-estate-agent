"""Market-wide investor simulation API."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError

from api.schemas import (
    MarketSimulationHandoffRequest,
    MarketSimulationHandoffResponse,
    MarketSimulationPersonaRequest,
    MarketSimulationPersonaResponse,
    MarketSimulationReplayResponse,
    MarketSimulationResultResponse,
    MarketSimulationStartRequest,
    MarketSimulationStartResponse,
    MarketSimulationStatusResponse,
)
from api.simulation import _run_simulation
from db.database import async_session
from db.models import MarketSimulationInvestor, Property
from services.market_investor_simulator import (
    build_market_simulation_replay,
    build_market_simulation_result,
    execute_market_simulation,
    get_market_simulation_status,
    initialize_market_simulation_run,
    preview_market_personas,
)
from services.negotiation_simulator import NegotiationSimulator
from services.runtime_schema import ensure_market_simulation_schema

router = APIRouter()


async def _run_market_simulation(run_id: str) -> None:
    await execute_market_simulation(run_id)


@router.post("/personas", response_model=MarketSimulationPersonaResponse)
async def generate_market_personas(
    req: MarketSimulationPersonaRequest,
) -> MarketSimulationPersonaResponse:
    async with async_session() as db:
        try:
            payload = await preview_market_personas(db, req)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MarketSimulationPersonaResponse(**payload)


@router.post("/start", status_code=202, response_model=MarketSimulationStartResponse)
async def start_market_simulation(
    req: MarketSimulationStartRequest,
    background_tasks: BackgroundTasks,
) -> MarketSimulationStartResponse:
    async with async_session() as db:
        try:
            run = await initialize_market_simulation_run(db, req)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ProgrammingError, OperationalError) as exc:
            await db.rollback()
            await ensure_market_simulation_schema()
            try:
                run = await initialize_market_simulation_run(db, req)
            except ValueError as value_exc:
                raise HTTPException(status_code=404, detail=str(value_exc)) from value_exc
            except (ProgrammingError, OperationalError) as retry_exc:
                raise HTTPException(
                    status_code=500,
                    detail="Market simulation schema is out of date. Restart the API server and run `alembic upgrade head`.",
                ) from retry_exc

    background_tasks.add_task(_run_market_simulation, run.id)
    return MarketSimulationStartResponse(
        run_id=run.id,
        status="pending",
        message="Market simulation started. Poll /status/{run_id} for progress.",
    )


@router.get("/status/{run_id}", response_model=MarketSimulationStatusResponse)
async def market_simulation_status(run_id: str) -> MarketSimulationStatusResponse:
    async with async_session() as db:
        run = await get_market_simulation_status(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Market simulation run not found")

    progress = 0
    if run.total_ticks:
        progress = int((run.current_tick / run.total_ticks) * 100)
        if run.status == "completed":
            progress = 100

    return MarketSimulationStatusResponse(
        run_id=run.id,
        status=run.status,
        current_tick=run.current_tick,
        total_ticks=run.total_ticks,
        progress=progress,
        investor_count=run.investor_count,
        property_count=run.property_count,
        run_label=run.run_label,
        error_message=run.error_message,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


@router.get("/result/{run_id}", response_model=MarketSimulationResultResponse)
async def market_simulation_result(run_id: str) -> MarketSimulationResultResponse:
    async with async_session() as db:
        run = await get_market_simulation_status(db, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Market simulation run not found")
        if run.status not in {"completed", "failed"}:
            raise HTTPException(status_code=409, detail="Market simulation still running")
        payload = await build_market_simulation_result(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Market simulation run not found")
    return MarketSimulationResultResponse(**payload)


@router.get("/replay/{run_id}", response_model=MarketSimulationReplayResponse)
async def market_simulation_replay(run_id: str) -> MarketSimulationReplayResponse:
    async with async_session() as db:
        payload = await build_market_simulation_replay(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Market simulation run not found")
    return MarketSimulationReplayResponse(**payload)


@router.post(
    "/handoff-to-negotiation",
    status_code=202,
    response_model=MarketSimulationHandoffResponse,
)
async def handoff_to_negotiation(
    req: MarketSimulationHandoffRequest,
    background_tasks: BackgroundTasks,
) -> MarketSimulationHandoffResponse:
    async with async_session() as db:
        run = await get_market_simulation_status(db, req.run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Market simulation run not found")

        investor_result = await db.execute(
            select(MarketSimulationInvestor).where(
                MarketSimulationInvestor.id == req.investor_id,
                MarketSimulationInvestor.run_id == req.run_id,
            )
        )
        investor = investor_result.scalar_one_or_none()
        if investor is None:
            raise HTTPException(status_code=404, detail="Investor not found for this run")

        property_result = await db.execute(select(Property).where(Property.id == req.property_id))
        property_row = property_result.scalar_one_or_none()
        if property_row is None:
            raise HTTPException(status_code=404, detail="Property not found")

        replay = await build_market_simulation_replay(db, req.run_id)
        if replay is None:
            raise HTTPException(status_code=404, detail="Market simulation replay not found")

    matching_decisions = [
        decision
        for tick in replay["ticks"]
        for decision in tick["decisions"]
        if decision["investor_id"] == req.investor_id and decision["property_id"] == req.property_id
    ]
    latest_decision = matching_decisions[-1] if matching_decisions else None

    latest_state = None
    for tick in replay["ticks"]:
        for property_state in tick["property_states"]:
            if property_state["property_id"] == req.property_id:
                latest_state = property_state

    seeded_config = {
        "property_id": property_row.id,
        "buyer_user_id": "",
        "seller_user_id": property_row.seller_id or "",
        "asking_price": float(property_row.asking_price or 0.0),
        "initial_offer": float((latest_state or {}).get("top_bid") or float(property_row.asking_price or 0.0) * 0.93),
        "seller_minimum": float((latest_state or {}).get("reservation_threshold") or float(property_row.asking_price or 0.0) * 0.94),
        "buyer_maximum": float(investor.cash_remaining or investor.budget or float(property_row.asking_price or 0.0) * 1.08),
        "strategy": "aggressive" if investor.archetype == "momentum" else "conservative" if investor.archetype == "contrarian" else "balanced",
        "max_rounds": req.max_rounds,
        "market_investor_id": investor.id,
    }

    simulator = NegotiationSimulator(config=seeded_config)
    background_tasks.add_task(_run_simulation, simulator)

    return MarketSimulationHandoffResponse(
        simulation_id=simulator.sim_id,
        status="pending",
        investor_id=investor.id,
        property_id=property_row.id,
        seeded_config={
            **seeded_config,
            "latest_market_action": latest_decision["chosen_action"] if latest_decision else None,
        },
        message="Negotiation simulation handoff started. Use the returned simulation_id with the existing replay flow.",
    )
