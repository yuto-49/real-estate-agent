"""Phase C: actor & cohort memory tests."""

from __future__ import annotations

import logging

import pytest

from domain.actors import (
    ActorSignalState,
    ActorType,
    CohortSignalState,
    cohort_signals,
    household_signal_snapshot,
    infer_actor_type,
    user_profile_signals,
)


class _FakeUser:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeHousehold:
    def __init__(self, **kwargs):
        defaults = {
            "id": "h1",
            "income_band": "moderate",
            "housing_type": "renter",
            "monthly_income": 5000.0,
            "monthly_housing_cost": 1500.0,
            "policy_support_score": 0.0,
            "housing_market_sentiment": 0.2,
            "neighborhood_satisfaction": 0.6,
            "eviction_risk": 0.0,
            "social_connections": 4,
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


def test_infer_actor_type_from_role():
    assert infer_actor_type(_FakeUser(role="buyer")) is ActorType.BUYER
    assert infer_actor_type(_FakeUser(role="seller")) is ActorType.SELLER
    assert infer_actor_type(_FakeUser(role="broker")) is ActorType.BROKER
    assert infer_actor_type(_FakeUser(role="agent")) is ActorType.BROKER
    assert infer_actor_type(_FakeUser(role="investor")) is ActorType.INVESTOR


def test_infer_actor_type_from_dict():
    assert infer_actor_type({"role": "renter"}) is ActorType.RENTER
    assert infer_actor_type({"actor_type": "city"}) is ActorType.CITY


def test_infer_actor_type_falls_back_to_housing_type():
    assert infer_actor_type(_FakeUser(housing_type="renter")) is ActorType.RENTER


def test_infer_actor_type_unknown_returns_unknown(caplog):
    with caplog.at_level(logging.WARNING, logger="domain.actors.profiles"):
        actor_type = infer_actor_type(_FakeUser(role="alien-overlord"))
    assert actor_type is ActorType.UNKNOWN
    assert any("Unknown actor role" in r.message for r in caplog.records)


def test_infer_actor_type_no_role_field():
    assert infer_actor_type(_FakeUser()) is ActorType.UNKNOWN


def test_user_profile_signals_buyer_is_optimistic_when_aggressive():
    snapshot = user_profile_signals(
        _FakeUser(
            role="buyer",
            budget_min=400_000,
            budget_max=600_000,
            risk_tolerance="aggressive",
            timeline_days=60,
        )
    )
    assert isinstance(snapshot, ActorSignalState)
    assert snapshot.investor_optimism == 0.8
    assert snapshot.willingness_to_transact > 0.5
    assert snapshot.resistance_to_development < 0.5


def test_user_profile_signals_short_timeline_pressures_affordability():
    snapshot = user_profile_signals(
        _FakeUser(
            role="buyer",
            budget_min=400_000,
            budget_max=410_000,
            risk_tolerance="conservative",
            timeline_days=14,
        )
    )
    assert snapshot.affordability_pressure > 0.7


def test_user_profile_signals_handles_dict_input():
    snapshot = user_profile_signals(
        {
            "role": "seller",
            "budget_min": 0,
            "budget_max": 0,
            "risk_tolerance": "moderate",
            "timeline_days": 90,
        }
    )
    assert isinstance(snapshot, ActorSignalState)
    assert snapshot.willingness_to_transact > 0.5  # seller bias


def test_cohort_signals_averages_inputs():
    snapshot_a = ActorSignalState(
        affordability_pressure=0.2,
        investor_optimism=0.4,
        willingness_to_transact=0.6,
    )
    snapshot_b = ActorSignalState(
        affordability_pressure=0.6,
        investor_optimism=0.8,
        willingness_to_transact=0.4,
    )

    cohort = cohort_signals([snapshot_a, snapshot_b], actor_type=ActorType.BUYER, label="sf-buyers")

    assert isinstance(cohort, CohortSignalState)
    assert cohort.cohort_size == 2
    assert cohort.cohort_label == "sf-buyers"
    assert cohort.actor_type is ActorType.BUYER
    assert cohort.affordability_pressure == pytest.approx(0.4)
    assert cohort.investor_optimism == pytest.approx(0.6)
    assert cohort.willingness_to_transact == pytest.approx(0.5)


def test_cohort_signals_empty_returns_zero_cohort():
    cohort = cohort_signals([], label="empty")
    assert cohort.cohort_size == 0
    assert cohort.affordability_pressure == 0.0
    assert cohort.actor_type is ActorType.UNKNOWN


def test_cohort_signals_mixes_household_and_user_snapshots():
    user_snapshot = user_profile_signals(
        _FakeUser(role="buyer", budget_min=300_000, budget_max=400_000, risk_tolerance="moderate")
    )
    household_snapshot = household_signal_snapshot(_FakeHousehold())
    cohort = cohort_signals([user_snapshot, household_snapshot], label="mixed")
    assert cohort.cohort_size == 2
    assert 0.0 <= cohort.affordability_pressure <= 1.0
