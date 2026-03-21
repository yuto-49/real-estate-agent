"""Negotiation state machine tests."""

import pytest
from agent.negotiation import NegotiationState, transition


def test_basic_offer_flow():
    state = transition(NegotiationState.IDLE, "place_offer")
    assert state == NegotiationState.OFFER_PENDING


def test_accept_offer():
    state = transition(NegotiationState.OFFER_PENDING, "accept")
    assert state == NegotiationState.ACCEPTED


def test_counter_offer():
    state = transition(NegotiationState.OFFER_PENDING, "counter")
    assert state == NegotiationState.COUNTER_PENDING


def test_buyer_accepts_counter():
    state = transition(NegotiationState.COUNTER_PENDING, "accept")
    assert state == NegotiationState.ACCEPTED


def test_buyer_counters_back():
    state = transition(NegotiationState.COUNTER_PENDING, "counter")
    assert state == NegotiationState.OFFER_PENDING


def test_auto_escalation():
    state = transition(NegotiationState.OFFER_PENDING, "counter", round_count=11)
    assert state == NegotiationState.ESCALATED


def test_full_close_pipeline():
    state = NegotiationState.ACCEPTED
    state = transition(state, "generate_contract")
    assert state == NegotiationState.CONTRACT_PHASE
    state = transition(state, "schedule_inspection")
    assert state == NegotiationState.INSPECTION
    state = transition(state, "clear")
    assert state == NegotiationState.CLOSING
    state = transition(state, "funds_transferred")
    assert state == NegotiationState.CLOSED


def test_invalid_transition():
    with pytest.raises(ValueError):
        transition(NegotiationState.CLOSED, "place_offer")
