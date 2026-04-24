"""Actor-layer state snapshots derived from persisted profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clamp_signed(value: float) -> float:
    return max(-1.0, min(1.0, value))


@dataclass(frozen=True, slots=True)
class ActorSignalState:
    """Structured actor signals used by the reaction and decision layers."""

    affordability_pressure: float = 0.0
    trust_in_trajectory: float = 0.0
    perceived_safety: float = 0.0
    social_proof: float = 0.0
    displacement_concern: float = 0.0
    investor_optimism: float = 0.0
    willingness_to_transact: float = 0.0
    resistance_to_development: float = 0.0


@dataclass(frozen=True, slots=True)
class HouseholdSignalSnapshot(ActorSignalState):
    """Normalized household signal state derived from persisted household fields."""

    household_id: str | None = None
    income_band: str = "unknown"
    housing_type: str = "unknown"


def household_signal_snapshot(household: Any) -> HouseholdSignalSnapshot:
    """Project a household-like object into layered actor signals.

    The domain layer uses a normalized snapshot instead of reaching directly
    into ORM field names throughout the codebase.
    """

    monthly_income = float(getattr(household, "monthly_income", 0.0) or 0.0)
    monthly_housing_cost = float(
        getattr(household, "monthly_housing_cost", 0.0) or 0.0,
    )
    policy_support = float(getattr(household, "policy_support_score", 0.0) or 0.0)
    market_sentiment = float(
        getattr(household, "housing_market_sentiment", 0.0) or 0.0,
    )
    neighborhood_satisfaction = float(
        getattr(household, "neighborhood_satisfaction", 0.5) or 0.5,
    )
    eviction_risk = float(getattr(household, "eviction_risk", 0.0) or 0.0)

    affordability_pressure = (
        _clamp_unit(monthly_housing_cost / monthly_income)
        if monthly_income > 0
        else 1.0
    )
    trust_in_trajectory = _clamp_signed((market_sentiment + policy_support) / 2.0)
    perceived_safety = _clamp_unit(neighborhood_satisfaction)
    social_proof = _clamp_unit(
        float(getattr(household, "social_connections", 0) or 0) / 12.0,
    )
    displacement_concern = _clamp_unit(
        affordability_pressure * 0.6 + max(0.0, -policy_support) * 0.4,
    )
    investor_optimism = _clamp_unit(max(0.0, market_sentiment))
    willingness_to_transact = _clamp_unit(
        max(0.0, market_sentiment + perceived_safety - affordability_pressure) / 2.0
        + 0.5
    )
    resistance_to_development = _clamp_unit(
        displacement_concern * 0.7 + eviction_risk * 0.3,
    )

    return HouseholdSignalSnapshot(
        household_id=getattr(household, "id", None),
        income_band=str(getattr(household, "income_band", "unknown")),
        housing_type=str(getattr(household, "housing_type", "unknown")),
        affordability_pressure=affordability_pressure,
        trust_in_trajectory=trust_in_trajectory,
        perceived_safety=perceived_safety,
        social_proof=social_proof,
        displacement_concern=displacement_concern,
        investor_optimism=investor_optimism,
        willingness_to_transact=willingness_to_transact,
        resistance_to_development=resistance_to_development,
    )
