"""Negotiation API endpoints — start, state, message, event replay."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import NegotiationCreate, NegotiationResponse
from db.database import get_db
from agent.negotiation_engine import NegotiationEngine
from agent.orchestrator import AgentOrchestrator
from services.event_store import EventStore

router = APIRouter()


@router.post("/", response_model=NegotiationResponse, status_code=201)
async def start_negotiation(data: NegotiationCreate, db: AsyncSession = Depends(get_db)):
    """Start a new negotiation session."""
    orchestrator = AgentOrchestrator(db=db)
    neg = await orchestrator.start_negotiation(
        data.property_id, data.buyer_id, data.seller_id
    )
    return NegotiationResponse.model_validate(neg)


@router.get("/{negotiation_id}")
async def get_negotiation(negotiation_id: str, db: AsyncSession = Depends(get_db)):
    """Get full negotiation state including event history."""
    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)
    state = await engine.get_negotiation_state(negotiation_id)
    if not state:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return state


@router.post("/{negotiation_id}/offer")
async def submit_offer(
    negotiation_id: str,
    offer_price: float,
    from_role: str,
    message: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Submit an offer or counter-offer in a negotiation."""
    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)
    result = await engine.process_offer(
        negotiation_id=negotiation_id,
        offer_price=offer_price,
        from_role=from_role,
        message=message,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@router.post("/{negotiation_id}/accept")
async def accept_negotiation(
    negotiation_id: str,
    from_role: str,
    final_price: float,
    db: AsyncSession = Depends(get_db),
):
    """Accept the current offer and finalize the deal."""
    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)
    result = await engine.accept_offer(
        negotiation_id=negotiation_id,
        from_role=from_role,
        final_price=final_price,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@router.get("/{negotiation_id}/events")
async def get_negotiation_events(negotiation_id: str, db: AsyncSession = Depends(get_db)):
    """Get event replay for a negotiation."""
    event_store = EventStore(db)
    events = await event_store.replay_aggregate("negotiation", negotiation_id)
    return {"negotiation_id": negotiation_id, "events": events}
