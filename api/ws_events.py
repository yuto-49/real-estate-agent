"""Typed WebSocket event definitions."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class WSEventType(str, Enum):
    NEGOTIATION_STATE_CHANGE = "negotiation.state_change"
    OFFER_RECEIVED = "offer.received"
    COUNTER_OFFER = "counter_offer"
    AGENT_RESPONSE = "agent.response"
    TIMEOUT_WARNING = "timeout.warning"
    TIMEOUT_EXPIRED = "timeout.expired"
    SYSTEM_ERROR = "system.error"
    CONNECTION_ACK = "connection.ack"


class WSEvent(BaseModel):
    type: WSEventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str | None = None


class NegotiationStateChangeEvent(WSEvent):
    type: WSEventType = WSEventType.NEGOTIATION_STATE_CHANGE
    negotiation_id: str
    old_status: str
    new_status: str
    round_count: int = 0


class OfferReceivedEvent(WSEvent):
    type: WSEventType = WSEventType.OFFER_RECEIVED
    offer_id: str
    property_id: str
    offer_price: float
    buyer_id: str


class CounterOfferEvent(WSEvent):
    type: WSEventType = WSEventType.COUNTER_OFFER
    negotiation_id: str
    counter_price: float
    from_role: str  # buyer or seller
    message: str = ""


class AgentResponseEvent(WSEvent):
    type: WSEventType = WSEventType.AGENT_RESPONSE
    agent_type: str
    response: str
    tool_calls: list[dict] = Field(default_factory=list)


class TimeoutWarningEvent(WSEvent):
    type: WSEventType = WSEventType.TIMEOUT_WARNING
    negotiation_id: str
    deadline_at: datetime
    hours_remaining: float


class TimeoutExpiredEvent(WSEvent):
    type: WSEventType = WSEventType.TIMEOUT_EXPIRED
    negotiation_id: str
    previous_status: str


class SystemErrorEvent(WSEvent):
    type: WSEventType = WSEventType.SYSTEM_ERROR
    error: str
    detail: str = ""


class ConnectionAckEvent(WSEvent):
    type: WSEventType = WSEventType.CONNECTION_ACK
    negotiation_id: str
    current_status: str
