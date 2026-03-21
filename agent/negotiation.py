"""Negotiation state machine — implements the state transitions from Section 4.1."""

from enum import Enum


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


# Valid transitions: (current_state, action) -> next_state
TRANSITIONS = {
    (NegotiationState.IDLE, "place_offer"): NegotiationState.OFFER_PENDING,
    (NegotiationState.OFFER_PENDING, "accept"): NegotiationState.ACCEPTED,
    (NegotiationState.OFFER_PENDING, "reject"): NegotiationState.REJECTED,
    (NegotiationState.OFFER_PENDING, "counter"): NegotiationState.COUNTER_PENDING,
    (NegotiationState.COUNTER_PENDING, "accept"): NegotiationState.ACCEPTED,
    (NegotiationState.COUNTER_PENDING, "counter"): NegotiationState.OFFER_PENDING,
    (NegotiationState.COUNTER_PENDING, "withdraw"): NegotiationState.WITHDRAWN,
    (NegotiationState.ACCEPTED, "generate_contract"): NegotiationState.CONTRACT_PHASE,
    (NegotiationState.CONTRACT_PHASE, "schedule_inspection"): NegotiationState.INSPECTION,
    (NegotiationState.INSPECTION, "clear"): NegotiationState.CLOSING,
    (NegotiationState.CLOSING, "funds_transferred"): NegotiationState.CLOSED,
}

# Statutory timeout hours per state
TIMEOUT_HOURS = {
    NegotiationState.OFFER_PENDING: 48,
    NegotiationState.COUNTER_PENDING: 48,
    NegotiationState.CONTRACT_PHASE: 72,
    NegotiationState.INSPECTION: 240,  # 10 days
    NegotiationState.CLOSING: 720,  # 30 days
}


class NegotiationTimer:
    """Calculates deadlines based on state-specific timeout rules."""

    @staticmethod
    def get_timeout_hours(state: NegotiationState) -> int | None:
        return TIMEOUT_HOURS.get(state)

    @staticmethod
    def get_deadline(state: NegotiationState, entered_at) -> object | None:
        from datetime import timedelta
        hours = TIMEOUT_HOURS.get(state)
        if hours is None:
            return None
        return entered_at + timedelta(hours=hours)


def transition(current: NegotiationState, action: str, round_count: int = 0) -> NegotiationState:
    """Attempt a state transition. Raises ValueError on invalid transition."""
    # Auto-escalation check
    if round_count > 10:
        return NegotiationState.ESCALATED

    key = (current, action)
    if key not in TRANSITIONS:
        raise ValueError(f"Invalid transition: {current.value} + {action}")
    return TRANSITIONS[key]
