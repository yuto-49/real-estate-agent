"""Tests for the investor trace step."""

from domain.reactions.models import ReactionEvent, ReactionVector
from domain.simulation.investor_step import update_investor
from domain.simulation.models import InvestorTrace, PropertyState


def test_noi_decline_shifts_recommendation():
    prev = InvestorTrace(ReactionVector(), "HOLD", 0.8, "stable")
    prev_prop = PropertyState(0.95, 85000, 15000, 840000, 1.4, 0.065, 13000000)
    new_prop = PropertyState(0.80, 85000, 15000, 600000, 1.0, 0.046, 13000000)
    events = (ReactionEvent(topic="market", variable="investor_optimism", delta=-0.3),)
    updated = update_investor(prev, prev_prop, new_prop, events)
    assert updated.reaction.investor_optimism < 0


def test_stable_conditions_hold():
    prev = InvestorTrace(ReactionVector(investor_optimism=0.5), "HOLD", 0.8, "stable")
    prop = PropertyState(0.95, 85000, 15000, 840000, 1.4, 0.065, 13000000)
    updated = update_investor(prev, prop, prop, ())
    assert updated.recommendation == "HOLD"
