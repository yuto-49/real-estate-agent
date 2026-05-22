"""Strategy run API — Phases S5/S6/S7.

Single entry point that the frontend uses to:

* extract a ``StrategyProfile`` from free text (LLM-seeded, user reviews)
* start a strategy run for a portfolio (background job)
* poll status
* fetch the completed ``UnifiedReport``

Background work runs in-process via FastAPI ``BackgroundTasks`` and writes
results to the module-level store in ``services/strategy_runner.py`` — the
same pattern as ``api/batch_simulation.py``.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    StrategyExtractResponse,
    StrategyInput,
    StrategyProfile,
    StrategyRunRecord,
    StrategyRunRequest,
    StrategyRunStartResponse,
)
from db.database import get_db
from services.pubsub import EventBus
from services.redis import get_redis
from services.strategy_profile import extract_strategy_profile
from services.strategy_runner import (
    execute_strategy_run,
    get_strategy_run,
    list_strategy_runs,
    start_strategy_run,
)


async def _build_event_sink() -> EventBus | None:
    """Construct an EventBus over the shared Redis client, or None on error."""
    try:
        redis_client = await get_redis()
        return EventBus(redis_client)
    except Exception:
        return None

router = APIRouter()


@router.post("/extract", response_model=StrategyExtractResponse)
async def extract_profile(payload: StrategyInput) -> StrategyExtractResponse:
    """Convert free text into a reviewable ``StrategyProfile``."""
    profile = await extract_strategy_profile(payload.text)
    return StrategyExtractResponse(profile=profile)


@router.post(
    "/run", response_model=StrategyRunStartResponse, status_code=202
)
async def run_strategy(
    payload: StrategyRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> StrategyRunStartResponse:
    """Start a strategy run — returns immediately, poll /status/{run_id}."""
    profile: StrategyProfile = (
        payload.profile
        if payload.profile is not None
        else await extract_strategy_profile(payload.text)
    )

    record = await start_strategy_run(payload.portfolio_id, profile)

    async def _execute() -> None:
        sink = await _build_event_sink()
        await execute_strategy_run(
            db, record.run_id, payload.portfolio_id, profile, event_sink=sink
        )

    background_tasks.add_task(_execute)

    return StrategyRunStartResponse(
        run_id=record.run_id,
        portfolio_id=record.portfolio_id,
        status=record.status,
        profile=profile,
    )


@router.get("/recent", response_model=list[StrategyRunRecord])
async def recent_runs(
    user_id: str,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
) -> list[StrategyRunRecord]:
    """Return the most recent strategy runs across all portfolios for a user.

    Used by the Overview tab to surface the latest simulation. Filters by
    looking up the user's portfolios then matching on ``portfolio_id``.
    """
    from sqlalchemy import select

    from db.models import InvestorPortfolio
    from services.user_resolve import resolve_user_id

    try:
        resolved = await resolve_user_id(db, user_id)
    except LookupError:
        return []

    portfolio_ids = {
        row
        for row in (
            await db.execute(
                select(InvestorPortfolio.id).where(
                    InvestorPortfolio.user_id == resolved
                )
            )
        ).scalars()
    }
    if not portfolio_ids:
        return []

    runs = await list_strategy_runs()
    matching = [r for r in runs if r.portfolio_id in portfolio_ids]
    matching.sort(key=lambda r: r.started_at, reverse=True)
    return matching[: max(1, min(limit, 50))]


@router.get("/{run_id}/status", response_model=StrategyRunRecord)
async def run_status(run_id: str) -> StrategyRunRecord:
    record = await get_strategy_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    return record


@router.get("/{run_id}/result", response_model=StrategyRunRecord)
async def run_result(run_id: str) -> StrategyRunRecord:
    record = await get_strategy_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    if record.status not in ("completed", "failed"):
        raise HTTPException(status_code=409, detail="run_not_finished")
    return record
