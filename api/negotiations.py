"""Negotiation API endpoints — start, state, message, event replay."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    NegotiationAcceptRequest,
    NegotiationCreate,
    NegotiationEventsResponse,
    NegotiationMutationResponse,
    NegotiationOfferRequest,
    NegotiationResponse,
    NegotiationSessionResponse,
    NegotiationTransitionRequest,
)
from db.database import get_db
from agent.negotiation_engine import NegotiationEngine
from agent.orchestrator import AgentOrchestrator
from services.event_store import EventStore

router = APIRouter()


def _raise_negotiation_error(result: dict) -> None:
    """Map engine errors into cleaner HTTP semantics."""
    detail = result["error"]
    if detail == "Negotiation not found":
        raise HTTPException(status_code=404, detail=detail)
    if result.get("expired"):
        raise HTTPException(status_code=409, detail=detail)
    raise HTTPException(status_code=422, detail=detail)


@router.post("/", response_model=NegotiationResponse, status_code=201)
async def start_negotiation(data: NegotiationCreate, db: AsyncSession = Depends(get_db)):
    """Start a new negotiation session."""
    orchestrator = AgentOrchestrator(db=db)
    neg = await orchestrator.start_negotiation(
        data.property_id, data.buyer_id, data.seller_id
    )
    return NegotiationResponse.model_validate(neg)


@router.get("/{negotiation_id}", response_model=NegotiationSessionResponse)
async def get_negotiation(negotiation_id: str, db: AsyncSession = Depends(get_db)):
    """Get full negotiation state including event history."""
    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)
    state = await engine.get_negotiation_state(negotiation_id)
    if not state:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return state


@router.post("/{negotiation_id}/offer", response_model=NegotiationMutationResponse)
async def submit_offer(
    negotiation_id: str,
    data: NegotiationOfferRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit an offer or counter-offer in a negotiation."""
    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)
    result = await engine.process_offer(
        negotiation_id=negotiation_id,
        offer_price=data.offer_price,
        from_role=data.from_role,
        message=data.message,
        correlation_id=data.correlation_id,
    )
    if "error" in result:
        _raise_negotiation_error(result)
    return result


@router.post("/{negotiation_id}/accept", response_model=NegotiationMutationResponse)
async def accept_negotiation(
    negotiation_id: str,
    data: NegotiationAcceptRequest,
    db: AsyncSession = Depends(get_db),
):
    """Accept the current offer and finalize the deal."""
    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)
    result = await engine.accept_offer(
        negotiation_id=negotiation_id,
        from_role=data.from_role,
        final_price=data.final_price,
        correlation_id=data.correlation_id,
    )
    if "error" in result:
        _raise_negotiation_error(result)
    return result


@router.post(
    "/{negotiation_id}/transition",
    response_model=NegotiationMutationResponse,
)
async def transition_negotiation(
    negotiation_id: str,
    data: NegotiationTransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Advance a negotiation lifecycle transition via a typed JSON body."""
    event_store = EventStore(db)
    engine = NegotiationEngine(db=db, event_store=event_store)
    result = await engine.transition_negotiation(
        negotiation_id=negotiation_id,
        action=data.action,
        from_role=data.from_role,
        message=data.message,
        correlation_id=data.correlation_id,
    )
    if "error" in result:
        _raise_negotiation_error(result)
    return result


@router.get("/{negotiation_id}/events", response_model=NegotiationEventsResponse)
async def get_negotiation_events(negotiation_id: str, db: AsyncSession = Depends(get_db)):
    """Get event replay for a negotiation."""
    event_store = EventStore(db)
    events = await event_store.replay_aggregate("negotiation", negotiation_id)
    return {"negotiation_id": negotiation_id, "events": events}
