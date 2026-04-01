"""Social Simulation API — start, monitor, and retrieve social behavior simulations."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func

from api.schemas import (
    SocialSimStartRequest,
    SocialSimStatusResponse,
    SocialSimResultResponse,
    SocialSimActionResponse,
    SocialSimTimelineEntry,
    SocialSimTimelineResponse,
    SocialSimGenerateReportRequest,
)
from db.database import async_session
from db.models import SocialSimulationAction, SocialSimulationRun
from services.social_simulator import start_social_simulation, get_social_sim
from services.social_report_bridge import generate_report_from_social_sim

router = APIRouter()


@router.post("/start", status_code=202)
async def start_social_sim(req: SocialSimStartRequest):
    """Start a new social behavior simulation. Returns immediately with run ID."""
    run_id = await start_social_simulation(
        trigger_user_id=req.user_id,
        zip_code=req.zip_code,
        income_band=req.income_band,
        max_rounds=req.max_rounds,
        topics=req.topics,
    )
    return {
        "run_id": run_id,
        "status": "preparing",
        "message": "Social simulation started. Poll /status for progress.",
    }


@router.get("/{run_id}/status")
async def social_sim_status(run_id: str) -> SocialSimStatusResponse:
    """Get current status of a social simulation."""
    # Check in-memory first for running sims
    mem = get_social_sim(run_id)
    if mem:
        return SocialSimStatusResponse(
            id=mem["id"],
            status=mem["status"],
            current_round=mem.get("current_round", 0),
            total_rounds=mem.get("total_rounds", 10),
            action_count=mem.get("action_count", 0),
        )

    # Fall back to DB
    async with async_session() as db:
        result = await db.execute(
            select(SocialSimulationRun).where(SocialSimulationRun.id == run_id)
        )
        run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Social simulation not found")

    # Count actions
    async with async_session() as db:
        count_result = await db.execute(
            select(func.count()).where(SocialSimulationAction.run_id == run_id)
        )
        action_count = count_result.scalar() or 0

    return SocialSimStatusResponse(
        id=run.id,
        status=run.status,
        current_round=run.current_round,
        total_rounds=run.total_rounds,
        action_count=action_count,
        created_at=run.created_at,
    )


@router.get("/{run_id}/result")
async def social_sim_result(run_id: str) -> SocialSimResultResponse:
    """Get full results of a completed social simulation."""
    async with async_session() as db:
        result = await db.execute(
            select(SocialSimulationRun).where(SocialSimulationRun.id == run_id)
        )
        run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Social simulation not found")

    if run.status not in ("completed", "failed"):
        raise HTTPException(status_code=409, detail="Simulation still running")

    return SocialSimResultResponse.model_validate(run)


@router.get("/{run_id}/actions")
async def social_sim_actions(
    run_id: str,
    round_num: int | None = None,
    topic: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[SocialSimActionResponse]:
    """Get paginated action log for a social simulation."""
    async with async_session() as db:
        query = (
            select(SocialSimulationAction)
            .where(SocialSimulationAction.run_id == run_id)
            .order_by(SocialSimulationAction.round_num, SocialSimulationAction.created_at)
        )
        if round_num is not None:
            query = query.where(SocialSimulationAction.round_num == round_num)
        if topic:
            query = query.where(SocialSimulationAction.topic == topic)

        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        actions = result.scalars().all()

    return [SocialSimActionResponse.model_validate(a) for a in actions]


@router.get("/{run_id}/timeline")
async def social_sim_timeline(run_id: str) -> SocialSimTimelineResponse:
    """Get round-by-round opinion trajectory for each topic."""
    async with async_session() as db:
        # Aggregate actions by round and topic
        result = await db.execute(
            select(
                SocialSimulationAction.round_num,
                SocialSimulationAction.topic,
                func.avg(SocialSimulationAction.sentiment_value).label("avg_sentiment"),
                func.count().label("action_count"),
            )
            .where(SocialSimulationAction.run_id == run_id)
            .group_by(SocialSimulationAction.round_num, SocialSimulationAction.topic)
            .order_by(SocialSimulationAction.round_num)
        )
        rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="No timeline data found")

    timeline = []
    for row in rows:
        avg = row.avg_sentiment or 0
        stance = "supportive" if avg > 0.2 else "opposed" if avg < -0.2 else "neutral"
        timeline.append(SocialSimTimelineEntry(
            round_num=row.round_num,
            topic=row.topic,
            avg_sentiment=round(avg, 4),
            action_count=row.action_count,
            dominant_stance=stance,
        ))

    return SocialSimTimelineResponse(run_id=run_id, timeline=timeline)


@router.post("/{run_id}/generate-report")
async def generate_report(run_id: str, req: SocialSimGenerateReportRequest):
    """Generate a MiroFish-compatible report from a completed social simulation.

    The returned report_id can be used with POST /api/simulation/start-from-report
    to run a negotiation simulation seeded by social intelligence.
    """
    report_id = await generate_report_from_social_sim(
        run_id=run_id,
        property_id=req.property_id,
        household_id=req.household_id,
    )

    if not report_id:
        raise HTTPException(
            status_code=409,
            detail="Simulation not completed or household not found",
        )

    return {
        "report_id": report_id,
        "message": "Report generated. Use this report_id with /api/simulation/start-from-report.",
    }
