"""Agent message API — routes user messages to AI agents."""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from agent.orchestrator import AgentOrchestrator
from db.database import get_db
from services.maps import MapsService
from services.market_data import MarketDataService
from services.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class AgentMessageRequest(BaseModel):
    user_id: str
    role: str  # buyer, seller, broker
    message: str
    report_id: str | None = None  # Optional: attach a specific intelligence report


class AgentMessageResponse(BaseModel):
    response: str
    tool_calls: list = []
    error: str | None = None


@router.post("/message", response_model=AgentMessageResponse)
async def send_agent_message(
    data: AgentMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a natural-language message to an AI agent (buyer/seller/broker)."""
    if data.role not in ("buyer", "seller", "broker", "assistant"):
        raise HTTPException(status_code=400, detail=f"Invalid role: {data.role}")

    maps = MapsService()
    market_data = MarketDataService()
    orchestrator = AgentOrchestrator(
        db=db, maps=maps, market_data=market_data,
    )

    logger.info(
        "agent.message_received",
        user_id=data.user_id,
        role=data.role,
        message_preview=data.message[:100],
    )

    result = await orchestrator.route_message(
        user_id=data.user_id,
        role=data.role,
        message=data.message,
        report_id=data.report_id,
    )

    if "error" in result:
        return AgentMessageResponse(response="", error=result["error"])

    return AgentMessageResponse(
        response=result.get("response", ""),
        tool_calls=result.get("tool_calls", []),
    )
