"""Intelligence report API — enqueue, status, and retrieval."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import ReportRequest, ReportResponse, ReportStatusResponse
from db.database import async_session, get_db
from db.models import MiroFishReport, MiroFishSeed, UserProfile
from intelligence.mirofish_client import (
    CircuitBreakerOpen,
    MiroFishClient,
    MiroFishReportData,
    create_mirofish_client,
)
from intelligence.seed_assembly import SeedAssemblyService
from services.logging import get_logger
from services.maps import MapsService
from services.market_data import MarketDataService

router = APIRouter()
logger = get_logger(__name__)


WORKFLOW_STEPS = [
    ("queued", "Queued", 0),
    ("loading_profile", "Loading Investor Profile", 10),
    ("fetching_market", "Fetching Market Data", 25),
    ("enriching_listings", "Enriching Listings with Neighborhood Data", 40),
    ("assembling_seed", "Assembling Seed Document", 55),
    ("running_simulation", "Running MiroFish Simulation", 70),
    ("parsing_results", "Parsing Simulation Results", 85),
    ("completed", "Report Complete", 100),
    ("failed", "Report Failed", 0),
]


def _step_info(step_key: str) -> tuple[str, int]:
    for key, label, progress in WORKFLOW_STEPS:
        if key == step_key:
            return label, progress
    return step_key, 0


def _normalize_report(data: MiroFishReportData) -> dict:
    if data.raw_json:
        return data.raw_json
    return {
        "market_outlook": data.market_outlook,
        "timing_recommendation": data.timing_recommendation,
        "strategy_comparison": data.strategy_comparison,
        "risk_assessment": data.risk_assessment,
        "property_recommendations": data.property_recommendations,
        "decision_anchors": data.decision_anchors,
    }


async def _update_report_state(
    report_id: str,
    *,
    status: str | None = None,
    step_key: str | None = None,
    error: str | None = None,
    seed_hash: str | None = None,
    report_json: dict | None = None,
) -> None:
    async with async_session() as db:
        result = await db.execute(select(MiroFishReport).where(MiroFishReport.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            return

        config = dict(report.simulation_config or {})
        if step_key:
            step_label, progress = _step_info(step_key)
            config.update(
                {
                    "current_step": step_label,
                    "step_key": step_key,
                    "progress": progress,
                }
            )
        if error:
            config["error"] = error
        report.simulation_config = config

        if status:
            report.status = status
        if seed_hash is not None:
            report.seed_hash = seed_hash
        if report_json is not None:
            report.report_json = report_json

        await db.commit()


class _SeedDBAccessor:
    async def get_user_profile(self, user_id: str):
        async with async_session() as db:
            result = await db.execute(select(UserProfile).where(UserProfile.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                raise ValueError(f"User {user_id} not found")
            return user


async def _run_report_workflow(
    report_id: str,
    user_id: str,
    question: str,
    ticks: int,
    location_overrides: dict | None = None,
):
    """Execute real seed assembly and MiroFish simulation with progress updates."""
    maps = MapsService()
    market = MarketDataService()
    mirofish = create_mirofish_client()
    seed_service = SeedAssemblyService(maps=maps, market=market, db=_SeedDBAccessor())

    try:
        await _update_report_state(report_id, status="running", step_key="loading_profile")
        async with async_session() as db:
            result = await db.execute(select(UserProfile).where(UserProfile.id == user_id))
            if not result.scalar_one_or_none():
                raise ValueError(f"User {user_id} not found")

        await _update_report_state(report_id, status="running", step_key="fetching_market")
        await _update_report_state(report_id, status="running", step_key="enriching_listings")
        await _update_report_state(report_id, status="running", step_key="assembling_seed")

        seed_text = await seed_service.build_seed(user_id, location_overrides=location_overrides)
        seed_hash = seed_service.seed_hash(seed_text)

        async with async_session() as db:
            db.add(MiroFishSeed(user_id=user_id, seed_text=seed_text))
            result = await db.execute(select(MiroFishReport).where(MiroFishReport.id == report_id))
            report = result.scalar_one_or_none()
            if report:
                report.seed_hash = seed_hash
            await db.commit()

        await _update_report_state(
            report_id,
            status="running",
            step_key="running_simulation",
            seed_hash=seed_hash,
        )

        if not await mirofish.health_check():
            base_url = getattr(mirofish, "base_url", "mock")
            raise RuntimeError(f"MiroFish service unreachable at {base_url}")

        report_data = await mirofish.run_simulation(seed_text, question, ticks)

        await _update_report_state(report_id, status="running", step_key="parsing_results")

        await _update_report_state(
            report_id,
            status="completed",
            step_key="completed",
            report_json=_normalize_report(report_data),
        )
        logger.info("report.completed", report_id=report_id, user_id=user_id)

    except CircuitBreakerOpen as exc:
        logger.warning("report.circuit_open", report_id=report_id, error=str(exc))
        await _update_report_state(
            report_id,
            status="failed",
            step_key="failed",
            error=str(exc),
        )
    except Exception as exc:
        logger.error("report.failed", report_id=report_id, error=str(exc))
        await _update_report_state(
            report_id,
            status="failed",
            step_key="failed",
            error=str(exc),
        )
    finally:
        await mirofish.close()
        await maps.close()


@router.post("/generate", response_model=ReportStatusResponse, status_code=202)
async def generate_report(
    data: ReportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Enqueue a MiroFish simulation for a user. Returns report ID for polling."""
    user = await db.execute(select(UserProfile).where(UserProfile.id == data.user_id))
    if not user.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Build location overrides from search context
    location_overrides: dict | None = None
    override_fields = {
        "zip_code": data.zip_code,
        "latitude": data.latitude,
        "longitude": data.longitude,
        "min_price": data.min_price,
        "max_price": data.max_price,
    }
    if data.property_type:
        override_fields["property_types"] = [data.property_type]
    # Only create overrides dict if at least one field is set
    filtered = {k: v for k, v in override_fields.items() if v is not None}
    if filtered:
        location_overrides = filtered

    sim_config: dict = {
        "question": data.question,
        "ticks": data.ticks,
        "progress": 0,
        "current_step": "Queued",
        "step_key": "queued",
    }
    if location_overrides:
        sim_config["location_overrides"] = location_overrides

    report = MiroFishReport(
        user_id=data.user_id,
        simulation_config=sim_config,
        status="pending",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    background_tasks.add_task(
        _run_report_workflow,
        report.id,
        data.user_id,
        data.question,
        data.ticks,
        location_overrides,
    )

    logger.info("report.enqueued", report_id=report.id, user_id=data.user_id)

    return ReportStatusResponse(
        id=report.id,
        user_id=report.user_id,
        status=report.status,
        progress=0,
        current_step="Queued",
        step_key="queued",
        created_at=report.created_at,
    )


@router.get("/status/{report_id}", response_model=ReportStatusResponse)
async def report_status(report_id: str, db: AsyncSession = Depends(get_db)):
    """Check the status of a report generation job."""
    result = await db.execute(select(MiroFishReport).where(MiroFishReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    config = report.simulation_config or {}
    return ReportStatusResponse(
        id=report.id,
        user_id=report.user_id,
        status=report.status,
        progress=config.get("progress", 0),
        current_step=config.get("current_step", ""),
        step_key=config.get("step_key", ""),
        created_at=report.created_at,
    )


@router.get("/user/{user_id}", response_model=list[ReportStatusResponse])
async def list_user_reports(user_id: str, db: AsyncSession = Depends(get_db)):
    """List all intelligence reports for a user, newest first."""
    result = await db.execute(
        select(MiroFishReport)
        .where(MiroFishReport.user_id == user_id)
        .order_by(MiroFishReport.created_at.desc())
    )
    reports = list(result.scalars().all())
    return [
        ReportStatusResponse(
            id=r.id,
            user_id=r.user_id,
            status=r.status,
            progress=(r.simulation_config or {}).get("progress", 0),
            current_step=(r.simulation_config or {}).get("current_step", ""),
            step_key=(r.simulation_config or {}).get("step_key", ""),
            created_at=r.created_at,
        )
        for r in reports
    ]


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve a completed intelligence report."""
    result = await db.execute(select(MiroFishReport).where(MiroFishReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse.model_validate(report)
