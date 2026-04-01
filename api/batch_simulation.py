"""Batch simulation API — personas, multi-scenario runs, and comparison results."""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from services.persona_generator import generate_personas
from services.batch_simulator import BatchSimulator, get_batch
from services.scenario_variants import list_variants
from services.logging import get_logger
from api.simulation import _fetch_report_data, persist_simulation_result

logger = get_logger(__name__)

router = APIRouter()


# ── Request / Response models ──

class PersonaRequest(BaseModel):
    buyer_profile: dict | None = None
    property_context: dict | None = None


class BatchStartRequest(BaseModel):
    property_id: str
    asking_price: float
    initial_offer: float
    seller_minimum: float
    buyer_maximum: float
    max_rounds: int | None = Field(default=None, ge=5, le=100)
    buyer_user_id: str = ""
    seller_user_id: str = ""
    strategy: str = "balanced"
    scenario_names: list[str] = []
    report_id: str | None = None
    persona_data: dict | None = None


# ── Endpoints ──

@router.get("/scenarios")
async def get_scenarios():
    """List all available scenario variants."""
    return {"scenarios": list_variants()}


@router.post("/personas")
async def create_personas(req: PersonaRequest):
    """Generate buyer + seller personas from profile data."""
    personas = await generate_personas(
        buyer_profile=req.buyer_profile,
        property_context=req.property_context,
    )
    return {
        "buyer": personas["buyer"].to_dict(),
        "seller": personas["seller"].to_dict(),
    }


@router.post("/batch/start", status_code=202)
async def start_batch(
    req: BatchStartRequest,
    background_tasks: BackgroundTasks,
):
    """Start a batch of scenario simulations. Returns immediately with batch_id."""
    base_config = {
        "property_id": req.property_id,
        "asking_price": req.asking_price,
        "initial_offer": req.initial_offer,
        "seller_minimum": req.seller_minimum,
        "buyer_maximum": req.buyer_maximum,
        "max_rounds": req.max_rounds,
        "buyer_user_id": req.buyer_user_id,
        "seller_user_id": req.seller_user_id,
        "strategy": req.strategy,
    }

    report_data = None
    if req.report_id:
        report_data = await _fetch_report_data(req.report_id)

    batch = BatchSimulator(
        base_config=base_config,
        scenario_names=req.scenario_names,
        report_data=report_data,
        persona_data=req.persona_data,
    )

    async def _run_and_persist():
        try:
            result = await batch.run_all()
            # Persist each scenario outcome to DB
            buyer_user_id = req.buyer_user_id
            if buyer_user_id:
                for outcome in result.get("outcomes", []):
                    try:
                        await persist_simulation_result(
                            user_id=buyer_user_id,
                            property_id=req.property_id,
                            config={
                                "asking_price": req.asking_price,
                                "initial_offer": req.initial_offer,
                                "max_rounds": outcome.get("max_rounds", outcome.get("rounds_completed", 10)),
                                "strategy": req.strategy,
                            },
                            result={
                                "outcome": outcome.get("outcome", "unknown"),
                                "final_price": outcome.get("final_price"),
                                "current_round": outcome.get("rounds_completed", 0),
                                "summary": {"final_spread": outcome.get("final_spread", 0)},
                                "price_path": outcome.get("price_path", []),
                                "transcript": outcome.get("transcript", []),
                            },
                            batch_id=batch.batch_id,
                            scenario_name=outcome.get("scenario"),
                        )
                    except Exception as persist_err:
                        logger.error(
                            "batch.persist_outcome_failed",
                            batch_id=batch.batch_id,
                            scenario=outcome.get("scenario"),
                            error=str(persist_err),
                        )
        except Exception as e:
            logger.error(
                "batch.run_failed",
                batch_id=batch.batch_id,
                error=str(e),
                exc_info=True,
            )

    background_tasks.add_task(_run_and_persist)

    return {
        "batch_id": batch.batch_id,
        "status": "pending",
        "total_scenarios": len(batch.scenarios),
        "message": "Batch simulation started. Poll /batch/status/{batch_id} for progress.",
    }


@router.get("/batch/status/{batch_id}")
async def batch_status(batch_id: str):
    """Get current status of all scenarios in a batch."""
    data = get_batch(batch_id)
    if not data:
        raise HTTPException(status_code=404, detail="Batch not found")
    return data


@router.get("/batch/result/{batch_id}")
async def batch_result(batch_id: str):
    """Get comparison results of a completed batch."""
    data = get_batch(batch_id)
    if not data:
        raise HTTPException(status_code=404, detail="Batch not found")

    if data["status"] not in ("completed",):
        raise HTTPException(status_code=409, detail="Batch still running")

    # Rebuild full result from the BatchSimulator
    # The batch store only keeps status — we need to look up the BatchSimulator
    from services.batch_simulator import _batches as _store
    # Since the batch is completed, the _to_result_dict was already stored
    # But our store only has status_dict. We need to get the BatchSimulator.
    # For simplicity, store result alongside status when batch completes.
    # Let's check if 'outcomes' key exists (set by run_all completing).
    if "outcomes" in data:
        return data
    # Fallback: return status with note
    return {**data, "outcomes": [], "comparison": {}}
