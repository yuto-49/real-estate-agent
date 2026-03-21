"""WebSocket event serialization tests."""

from api.ws_events import (
    WSEventType,
    NegotiationStateChangeEvent,
    OfferReceivedEvent,
    AgentResponseEvent,
    TimeoutWarningEvent,
    ConnectionAckEvent,
)
from datetime import datetime


def test_negotiation_state_change_serialization():
    event = NegotiationStateChangeEvent(
        negotiation_id="neg-123",
        old_status="idle",
        new_status="offer_pending",
        round_count=0,
    )
    data = event.model_dump(mode="json")
    assert data["type"] == "negotiation.state_change"
    assert data["negotiation_id"] == "neg-123"
    assert data["old_status"] == "idle"
    assert data["new_status"] == "offer_pending"


def test_offer_received_serialization():
    event = OfferReceivedEvent(
        offer_id="off-123",
        property_id="prop-456",
        offer_price=350000,
        buyer_id="user-789",
    )
    data = event.model_dump(mode="json")
    assert data["type"] == "offer.received"
    assert data["offer_price"] == 350000


def test_agent_response_serialization():
    event = AgentResponseEvent(
        agent_type="buyer",
        response="I found 3 matching properties",
        tool_calls=[{"tool": "search_properties", "result_count": 3}],
    )
    data = event.model_dump(mode="json")
    assert data["agent_type"] == "buyer"
    assert len(data["tool_calls"]) == 1


def test_timeout_warning_serialization():
    event = TimeoutWarningEvent(
        negotiation_id="neg-123",
        deadline_at=datetime(2026, 3, 19, 12, 0, 0),
        hours_remaining=8.5,
    )
    data = event.model_dump(mode="json")
    assert data["type"] == "timeout.warning"
    assert data["hours_remaining"] == 8.5


def test_connection_ack():
    event = ConnectionAckEvent(
        negotiation_id="neg-123",
        current_status="offer_pending",
    )
    data = event.model_dump(mode="json")
    assert data["type"] == "connection.ack"
