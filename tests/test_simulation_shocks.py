"""Tests for shock-to-reaction-event translators."""

from domain.simulation.models import PolicyShock
from domain.simulation.shocks import translate_shock


def test_rent_decline_shock():
    shock = PolicyShock(round_num=2, shock_type="rent_decline", magnitude=-0.05)
    events = translate_shock(shock)
    variables = {e.variable for e in events}
    assert "affordability_pressure" in variables
    assert "investor_optimism" in variables


def test_shield_expiry_shock():
    shock = PolicyShock(round_num=8, shock_type="shield_expiry", magnitude=0)
    events = translate_shock(shock)
    assert any(e.variable == "investor_optimism" for e in events)


def test_custom_shock():
    shock = PolicyShock(
        round_num=1,
        shock_type="custom",
        magnitude=0.1,
        metadata={"variable": "perceived_safety", "delta": -0.2},
    )
    events = translate_shock(shock)
    assert len(events) == 1
    assert events[0].variable == "perceived_safety"
    assert events[0].delta == -0.2


def test_unknown_shock_returns_empty():
    shock = PolicyShock(round_num=1, shock_type="unknown_type", magnitude=0)
    events = translate_shock(shock)
    assert events == ()
