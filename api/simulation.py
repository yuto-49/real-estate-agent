"""Simulation API — start, monitor, retrieve, and persist negotiation simulations."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.schemas import (
    NegotiationSimRequest,
    NegotiationSimStatusResponse,
    NegotiationSimResultResponse,
    SimulationResultResponse,
    SimulationResultListResponse,
)
from services.negotiation_simulator import NegotiationSimulator, get_simulation, list_simulations
from sqlalchemy import select
from db.models import MiroFishReport, SimulationResult

router = APIRouter()


async def _fetch_report_data(report_id: str) -> dict | None:
    """Fetch completed report data from DB for injection into simulation."""
    from db.database import async_session

    async with async_session() as db:
        result = await db.execute(
            select(MiroFishReport).where(
                MiroFishReport.id == report_id,
                MiroFishReport.status == "completed",
            )
        )
        report = result.scalar_one_or_none()
        if report and report.report_json:
            return report.report_json
    return None


async def persist_simulation_result(
    user_id: str,
    property_id: str,
    config: dict,
    result: dict,
    batch_id: str | None = None,
    scenario_name: str | None = None,
) -> SimulationResult:
    """Save a completed simulation result to the database."""
    from db.database import async_session

    row = SimulationResult(
        user_id=user_id,
        property_id=property_id,
        batch_id=batch_id,
        scenario_name=scenario_name,
        outcome=result.get("outcome", "unknown"),
        final_price=result.get("final_price"),
        asking_price=config.get("asking_price", 0),
        initial_offer=config.get("initial_offer", 0),
        rounds_completed=result.get("current_round", 0),
        max_rounds=config.get("max_rounds", 10),
        strategy=config.get("strategy", "balanced"),
        summary=result.get("summary", {}),
        price_path=result.get("price_path", []),
    )

    async with async_session() as db:
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def _run_simulation(simulator: NegotiationSimulator) -> None:
    """Background task to run the simulation and persist results."""
    result = await simulator.run()
    # Persist to DB if we have a buyer_user_id
    buyer_user_id = simulator.config.get("buyer_user_id")
    if buyer_user_id:
        await persist_simulation_result(
            user_id=buyer_user_id,
            property_id=simulator.config.get("property_id", ""),
            config=simulator.config,
            result=result,
        )


@router.post("/start", status_code=202)
async def start_simulation(
    req: NegotiationSimRequest,
    background_tasks: BackgroundTasks,
):
    """Start a new negotiation simulation. Returns immediately with simulation ID."""
    config = {
        "property_id": req.property_id,
        "buyer_user_id": req.buyer_user_id,
        "seller_user_id": req.seller_user_id,
        "initial_offer": req.initial_offer,
        "asking_price": req.asking_price,
        "seller_minimum": req.seller_minimum,
        "buyer_maximum": req.buyer_maximum,
        "strategy": req.strategy,
        "max_rounds": req.max_rounds,
    }

    # Optionally load MiroFish report data
    report_data = None
    if req.report_id:
        report_data = await _fetch_report_data(req.report_id)

    # If we have report data, let it influence the config
    if report_data:
        overrides = NegotiationSimulator.derive_config_from_report(report_data, req.asking_price)
        # Only apply overrides for fields the user didn't explicitly set
        # (strategy and initial_offer are the main ones derived from report)
        if "strategy" in overrides and req.strategy == "balanced":
            config["strategy"] = overrides["strategy"]
        if "initial_offer" in overrides:
            # Use report-derived offer if user's offer matches default percentage
            config["initial_offer"] = overrides["initial_offer"]

    simulator = NegotiationSimulator(config=config, report_data=report_data)

    background_tasks.add_task(_run_simulation, simulator)

    return {
        "id": simulator.sim_id,
        "status": "pending",
        "message": "Simulation started. Poll /status/{id} for progress.",
    }


@router.post("/start-from-report", status_code=202)
async def start_simulation_from_report(
    report_id: str,
    property_id: str,
    asking_price: float,
    seller_minimum: float,
    buyer_user_id: str,
    seller_user_id: str = "",
    max_rounds: int = 15,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Start a simulation fully seeded by a MiroFish intelligence report.

    The report's decision_anchors, strategy_comparison, market_outlook, and
    risk_assessment are used to automatically derive:
    - Initial offer price
    - Buyer maximum budget
    - Negotiation strategy (aggressive/balanced/conservative)
    - Scenario constraints (urgency, risk tolerance)

    This implements the MiroFish seed-doc → negotiation bridge.
    """
    report_data = await _fetch_report_data(report_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found or not completed")

    # Derive full config from report
    overrides = NegotiationSimulator.derive_config_from_report(report_data, asking_price)

    config = {
        "property_id": property_id,
        "buyer_user_id": buyer_user_id,
        "seller_user_id": seller_user_id,
        "asking_price": asking_price,
        "seller_minimum": seller_minimum,
        "buyer_maximum": overrides.get("buyer_maximum", asking_price * 1.05),
        "initial_offer": overrides.get("initial_offer", asking_price * 0.93),
        "strategy": overrides.get("strategy", "balanced"),
        "max_rounds": min(overrides.get("max_rounds", max_rounds), max_rounds),
    }

    scenario_constraints = overrides.get("scenario_constraints")

    simulator = NegotiationSimulator(
        config=config,
        report_data=report_data,
        scenario_constraints=scenario_constraints,
    )

    background_tasks.add_task(_run_simulation, simulator)

    return {
        "id": simulator.sim_id,
        "status": "pending",
        "derived_config": {
            "strategy": config["strategy"],
            "initial_offer": config["initial_offer"],
            "buyer_maximum": config["buyer_maximum"],
            "max_rounds": config["max_rounds"],
        },
        "message": "Report-seeded simulation started. Poll /status/{id} for progress.",
    }


@router.get("/status/{sim_id}")
async def simulation_status(sim_id: str) -> NegotiationSimStatusResponse:
    """Get current status of a running/completed simulation."""
    sim = get_simulation(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return NegotiationSimStatusResponse(
        id=sim["id"],
        status=sim["status"],
        current_round=sim["current_round"],
        max_rounds=sim["max_rounds"],
        progress=sim["progress"],
        transcript=sim["transcript"],
        created_at=sim.get("created_at"),
    )


@router.get("/result/{sim_id}")
async def simulation_result(sim_id: str) -> NegotiationSimResultResponse:
    """Get full results of a completed simulation."""
    sim = get_simulation(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    if sim["status"] not in ("completed", "failed"):
        raise HTTPException(status_code=409, detail="Simulation still running")

    return NegotiationSimResultResponse(
        id=sim["id"],
        status=sim["status"],
        outcome=sim.get("outcome", "unknown"),
        final_price=sim.get("final_price"),
        rounds_completed=sim.get("current_round", 0),
        transcript=sim["transcript"],
        summary=sim.get("summary", {}),
        created_at=sim.get("created_at"),
    )


@router.get("/list")
async def list_all_simulations(property_id: str | None = None, status: str | None = None):
    """List simulations, optionally filtered by property_id and/or status."""
    sims = list_simulations()
    if property_id:
        sims = [s for s in sims if s.get("config", {}).get("property_id") == property_id]
    if status:
        sims = [s for s in sims if s.get("status") == status]
    return [
        {
            "id": s["id"],
            "property_id": s.get("config", {}).get("property_id"),
            "status": s["status"],
            "outcome": s.get("outcome", ""),
            "final_price": s.get("final_price"),
            "rounds_completed": s.get("current_round", 0),
            "max_rounds": s.get("max_rounds", 0),
            "created_at": s.get("created_at"),
        }
        for s in sims
    ]


# ── Persisted simulation results (DB-backed) ──

@router.get("/results")
async def get_saved_results(user_id: str | None = None) -> SimulationResultListResponse:
    """Return saved simulation results from the database, optionally filtered by user."""
    from db.database import async_session

    async with async_session() as db:
        query = select(SimulationResult).order_by(SimulationResult.created_at.desc())
        if user_id:
            query = query.where(SimulationResult.user_id == user_id)
        result = await db.execute(query)
        rows = result.scalars().all()

    items = [SimulationResultResponse.model_validate(r) for r in rows]
    return SimulationResultListResponse(results=items, count=len(items))


@router.get("/results/{result_id}")
async def get_saved_result(result_id: str) -> SimulationResultResponse:
    """Return a single saved simulation result."""
    from db.database import async_session

    async with async_session() as db:
        result = await db.execute(
            select(SimulationResult).where(SimulationResult.id == result_id)
        )
        row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Simulation result not found")
    return SimulationResultResponse.model_validate(row)
