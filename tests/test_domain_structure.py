"""Focused smoke coverage for the new domain packages."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from domain.actors import household_signal_snapshot
from domain.decisions import (
    NegotiationAction,
    NegotiationState,
    NegotiationTimer,
    negotiation_event,
    transition,
)
from domain.market import MarketShock, market_event
from domain.outcomes import MarketOutcomeSnapshot, merge_outcome_snapshot
from domain.reactions import (
    ALLOWED_REACTION_TOPICS,
    build_initial_opinions,
    communication_style_multiplier,
    validate_topics,
)


def make_household() -> SimpleNamespace:
    return SimpleNamespace(
        id="household-1",
        name="Layered Household",
        zip_code="60601",
        income_band="middle",
        housing_type="renter",
        household_size=3,
        num_children=1,
        monthly_housing_cost=2100,
        monthly_income=5000,
        eviction_risk=0.25,
        housing_market_sentiment=0.4,
        policy_support_score=-0.1,
        neighborhood_satisfaction=0.7,
        communication_style="vocal",
        social_connections=6,
    )


def test_decision_domain_negotiation_flow():
    assert negotiation_event(NegotiationAction.PLACE_OFFER) == "negotiation.place_offer"
    assert transition(NegotiationState.IDLE, NegotiationAction.PLACE_OFFER) == NegotiationState.OFFER_PENDING
    assert transition(NegotiationState.COUNTER_PENDING, "counter") == NegotiationState.OFFER_PENDING
    assert NegotiationTimer.get_timeout_hours(NegotiationState.INSPECTION) == 240


def test_actor_and_reaction_domain_helpers():
    household = make_household()

    snapshot = household_signal_snapshot(household)
    assert 0.0 <= snapshot.affordability_pressure <= 1.0
    assert -1.0 <= snapshot.trust_in_trajectory <= 1.0
    assert 0.0 <= snapshot.resistance_to_development <= 1.0

    opinions = build_initial_opinions(household)
    assert set(opinions) == ALLOWED_REACTION_TOPICS
    assert communication_style_multiplier("vocal") == 1.5
    assert validate_topics(["market_prices"]) == ["market_prices"]

    with pytest.raises(ValueError):
        validate_topics(["market_prices", "unsupported_topic"])


def test_market_and_outcome_domain_primitives():
    shock = MarketShock(
        event_type=market_event("transit_opened"),
        subject_id="station-1",
        narrative="New station opening improves access.",
    )
    assert shock.event_type == "market.transit_opened"

    snapshot = MarketOutcomeSnapshot(listing_id="listing-1", offer_volume=2)
    updated = merge_outcome_snapshot(snapshot, offer_volume=3, neighborhood_sentiment=0.25)

    assert snapshot.offer_volume == 2
    assert updated.offer_volume == 3
    assert updated.neighborhood_sentiment == 0.25
