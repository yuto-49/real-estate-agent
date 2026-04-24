"""Decision-layer negotiation state machine."""

from __future__ import annotations

from datetime import timedelta
from enum import Enum
from typing import Any


NEGOTIATION_EVENT_NAMESPACE = "negotiation"


class NegotiationState(str, Enum):
    IDLE = "idle"
    OFFER_PENDING = "offer_pending"
    COUNTER_PENDING = "counter_pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    ESCALATED = "escalated"
    CONTRACT_PHASE = "contract_phase"
    INSPECTION = "inspection"
    CLOSING = "closing"
    CLOSED = "closed"


class NegotiationAction(str, Enum):
    PLACE_OFFER = "place_offer"
    ACCEPT = "accept"
    REJECT = "reject"
    COUNTER = "counter"
    WITHDRAW = "withdraw"
    GENERATE_CONTRACT = "generate_contract"
    SCHEDULE_INSPECTION = "schedule_inspection"
    CLEAR = "clear"
    FUNDS_TRANSFERRED = "funds_transferred"


NEGOTIATION_TRANSITIONS = {
    (NegotiationState.IDLE, NegotiationAction.PLACE_OFFER): NegotiationState.OFFER_PENDING,
    (NegotiationState.OFFER_PENDING, NegotiationAction.ACCEPT): NegotiationState.ACCEPTED,
    (NegotiationState.OFFER_PENDING, NegotiationAction.REJECT): NegotiationState.REJECTED,
    (NegotiationState.OFFER_PENDING, NegotiationAction.COUNTER): NegotiationState.COUNTER_PENDING,
    (NegotiationState.COUNTER_PENDING, NegotiationAction.ACCEPT): NegotiationState.ACCEPTED,
    (NegotiationState.COUNTER_PENDING, NegotiationAction.COUNTER): NegotiationState.OFFER_PENDING,
    (NegotiationState.COUNTER_PENDING, NegotiationAction.WITHDRAW): NegotiationState.WITHDRAWN,
    (NegotiationState.ACCEPTED, NegotiationAction.GENERATE_CONTRACT): NegotiationState.CONTRACT_PHASE,
    (NegotiationState.CONTRACT_PHASE, NegotiationAction.SCHEDULE_INSPECTION): NegotiationState.INSPECTION,
    (NegotiationState.INSPECTION, NegotiationAction.CLEAR): NegotiationState.CLOSING,
    (NegotiationState.CLOSING, NegotiationAction.FUNDS_TRANSFERRED): NegotiationState.CLOSED,
}

NEGOTIATION_TIMEOUT_HOURS = {
    NegotiationState.OFFER_PENDING: 48,
    NegotiationState.COUNTER_PENDING: 48,
    NegotiationState.CONTRACT_PHASE: 72,
    NegotiationState.INSPECTION: 240,
    NegotiationState.CLOSING: 720,
}


def negotiation_event(action: str | NegotiationAction) -> str:
    """Build the canonical negotiation event name."""
    return f"{NEGOTIATION_EVENT_NAMESPACE}.{normalize_action(action).value}"


def normalize_state(state: str | NegotiationState) -> NegotiationState:
    """Normalize string inputs into a domain state enum."""
    if isinstance(state, NegotiationState):
        return state
    return NegotiationState(state)


def normalize_action(action: str | NegotiationAction) -> NegotiationAction:
    """Normalize string inputs into a domain action enum."""
    if isinstance(action, NegotiationAction):
        return action
    return NegotiationAction(action)


def resolve_offer_action(current_status: str | NegotiationState) -> NegotiationAction:
    """Return whether the next pricing move is an opening offer or a counter."""
    normalized_state = normalize_state(current_status)
    if normalized_state == NegotiationState.IDLE:
        return NegotiationAction.PLACE_OFFER
    return NegotiationAction.COUNTER


class NegotiationTimer:
    """Calculates deadlines based on state-specific timeout rules."""

    @staticmethod
    def get_timeout_hours(state: NegotiationState) -> int | None:
        return NEGOTIATION_TIMEOUT_HOURS.get(state)

    @staticmethod
    def get_deadline(state: NegotiationState, entered_at) -> object | None:
        hours = NEGOTIATION_TIMEOUT_HOURS.get(state)
        if hours is None:
            return None
        return entered_at + timedelta(hours=hours)


def transition(
    current: NegotiationState,
    action: str | NegotiationAction,
    round_count: int = 0,
) -> NegotiationState:
    """Attempt a state transition. Raises ValueError on invalid transition."""
    if round_count > 10:
        return NegotiationState.ESCALATED

    normalized_action = normalize_action(action)
    key = (current, normalized_action)
    if key not in NEGOTIATION_TRANSITIONS:
        raise ValueError(f"Invalid transition: {current.value} + {normalized_action.value}")
    return NEGOTIATION_TRANSITIONS[key]


def build_negotiation_analysis(
    *,
    round_count: int,
    offer_prices: list[float],
    history_limit: int = 10,
    zopa_threshold_rounds: int = 5,
    zopa_spread_percent: float = 3.0,
    broker_mediation_spread: float = 10.0,
) -> dict[str, Any]:
    """Build negotiation analysis from the current offer price path."""
    if len(offer_prices) < 2:
        return {"status": "insufficient_data"}

    max_price = max(offer_prices)
    min_price = min(offer_prices)
    spread = abs(max_price - min_price) / max_price * 100 if max_price else 0.0

    analysis: dict[str, Any] = {
        "round": round_count,
        "spread_percent": round(spread, 1),
        "offer_history": offer_prices[:history_limit],
    }

    if round_count >= zopa_threshold_rounds:
        if spread <= zopa_spread_percent:
            trailing_prices = offer_prices[-2:] if len(offer_prices) >= 2 else offer_prices
            midpoint = sum(trailing_prices) / len(trailing_prices)
            analysis["zopa_detected"] = True
            analysis["suggested_price"] = round(midpoint)
            analysis["recommendation"] = "suggest_split"
        else:
            analysis["zopa_detected"] = False

    if round_count >= zopa_threshold_rounds and spread > broker_mediation_spread:
        analysis["broker_mediation_recommended"] = True
        analysis["recommendation"] = "escalate_to_broker"

    return analysis
