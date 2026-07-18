"""Unit tests for the actor → reaction bridge (``domain/reactions/derive.py``).

The bridge is pure-Python, deterministic, side-effect free, and lenient:
missing inputs degrade to fewer events / a zeroed vector, never a raise. It
folds actor signals and market-observable signals through the real
``ReactionEngine`` rather than hand-building a ``ReactionVector``.
"""

from __future__ import annotations

from domain.actors import ActorSignalState
from domain.market.models import MarketContextSnapshot
from domain.reactions.derive import (
    actor_reaction_events,
    build_reaction_vector,
    market_reaction_events,
)
from domain.reactions.models import REACTION_VARIABLES, ReactionVector


def test_actor_events_skip_neutral_and_map_signed():
    # 0.5 unit signals map to a 0.0 signed delta → skipped; trust passes through.
    actor = ActorSignalState(
        investor_optimism=1.0,  # 2*1-1 = +1.0
        perceived_safety=0.5,  # 2*0.5-1 = 0.0 → skipped
        trust_in_trajectory=-0.4,  # already signed → passthrough
    )
    events = actor_reaction_events(actor)
    by_var = {e.variable: e.delta for e in events}

    assert "perceived_safety" not in by_var  # neutral skipped
    assert by_var["investor_optimism"] == 1.0
    assert by_var["trust_in_trajectory"] == -0.4
    # every emitted variable is a known reaction variable
    assert set(by_var).issubset(set(REACTION_VARIABLES))


def test_actor_events_empty_for_zeroed_state():
    assert actor_reaction_events(ActorSignalState()) == []


def test_market_events_match_observable_signals():
    market = MarketContextSnapshot(
        zip_code="60615",
        inventory_pressure=0.2,  # slack = 1 - 2*0.2 = 0.6
        safety_score=7.5,  # 7.5/5 - 1 = 0.5
        median_rent=2_000.0,
    )
    events = market_reaction_events(market, monthly_rent=2_400.0)
    by_var = {e.variable: round(e.delta, 4) for e in events}

    assert by_var["investor_optimism"] == 0.6
    assert by_var["willingness_to_transact"] == 0.6
    assert by_var["perceived_safety"] == 0.5
    assert by_var["displacement_concern"] == -0.5
    # rent gap = (2400 - 2000) / 2000 = 0.2
    assert by_var["affordability_pressure"] == 0.2


def test_market_events_lenient_on_missing_fields():
    # Empty snapshot + no rent → no market events, no raise.
    assert market_reaction_events(MarketContextSnapshot(), monthly_rent=None) == []


def test_build_vector_folds_actor_and_market():
    actor = ActorSignalState(willingness_to_transact=1.0)  # +1 signed delta
    market = MarketContextSnapshot(inventory_pressure=0.2)  # willingness slack 0.6
    vector = build_reaction_vector(actor, market, monthly_rent=None)

    assert isinstance(vector, ReactionVector)
    # 0.6 (market) + 1.0 (actor) folded then clamped to the signed ceiling.
    assert vector.willingness_to_transact == 1.0
    assert vector.investor_optimism == 0.6  # market only


def test_build_vector_actor_none_is_market_only():
    market = MarketContextSnapshot(safety_score=7.5)
    vector = build_reaction_vector(None, market, monthly_rent=None)
    assert vector.perceived_safety == 0.5
    assert vector.willingness_to_transact == 0.0


def test_build_vector_no_signal_is_zeroed():
    vector = build_reaction_vector(None, MarketContextSnapshot(), monthly_rent=None)
    assert vector == ReactionVector()


def test_build_vector_is_deterministic():
    actor = ActorSignalState(investor_optimism=0.8, displacement_concern=0.3)
    market = MarketContextSnapshot(inventory_pressure=0.4, safety_score=6.0)
    a = build_reaction_vector(actor, market, monthly_rent=1_800.0)
    b = build_reaction_vector(actor, market, monthly_rent=1_800.0)
    assert a == b
