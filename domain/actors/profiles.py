"""Actor-layer state snapshots derived from persisted profiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Iterable

logger = logging.getLogger(__name__)


class ActorType(str, Enum):
    """Phase C cohort taxonomy. Use ``infer_actor_type`` rather than hard-coding."""

    BUYER = "buyer"
    SELLER = "seller"
    RENTER = "renter"
    LANDLORD = "landlord"
    BROKER = "broker"
    INVESTOR = "investor"
    CITY = "city"
    BUSINESS = "business"
    HOUSEHOLD = "household"
    UNKNOWN = "unknown"


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


# ---------------------------------------------------------------------------
# Phase C: actor & cohort memory
# ---------------------------------------------------------------------------


_ROLE_TO_ACTOR_TYPE: dict[str, ActorType] = {
    "buyer": ActorType.BUYER,
    "seller": ActorType.SELLER,
    "renter": ActorType.RENTER,
    "tenant": ActorType.RENTER,
    "landlord": ActorType.LANDLORD,
    "owner": ActorType.LANDLORD,
    "broker": ActorType.BROKER,
    "agent": ActorType.BROKER,
    "investor": ActorType.INVESTOR,
    "city": ActorType.CITY,
    "official": ActorType.CITY,
    "business": ActorType.BUSINESS,
    "household": ActorType.HOUSEHOLD,
    "both": ActorType.BUYER,  # legacy: "both" buyer+seller users default to buyer signals
}


def infer_actor_type(entity: Any) -> ActorType:
    """Map a UserProfile / HouseholdProfile / dict to an :class:`ActorType`.

    Reads ``actor_type`` / ``role`` / ``housing_type`` in that order. Unknown
    roles fall back to ``ActorType.UNKNOWN`` with a warning — Phase C stays
    lenient (no raise) so emerging actor kinds don't block adoption.
    """
    raw = (
        getattr(entity, "actor_type", None)
        or (entity.get("actor_type") if isinstance(entity, dict) else None)
        or getattr(entity, "role", None)
        or (entity.get("role") if isinstance(entity, dict) else None)
        or getattr(entity, "housing_type", None)
        or (entity.get("housing_type") if isinstance(entity, dict) else None)
    )
    if raw is None:
        return ActorType.UNKNOWN

    key = str(raw).strip().lower()
    actor_type = _ROLE_TO_ACTOR_TYPE.get(key)
    if actor_type is None:
        logger.warning("Unknown actor role %r — defaulting to ActorType.UNKNOWN", raw)
        return ActorType.UNKNOWN
    return actor_type


def user_profile_signals(user_profile: Any) -> ActorSignalState:
    """Project a ``UserProfile``-like entity into :class:`ActorSignalState`.

    Uses ``budget_min``/``budget_max``, ``risk_tolerance``, ``timeline_days``,
    and ``role`` to derive the same eight pressures the household projection
    produces. All inputs are read defensively via ``getattr`` so the helper
    works with ORM rows, plain dicts, and Pydantic models.
    """

    def _read(attr: str, default: Any = None) -> Any:
        if isinstance(user_profile, dict):
            return user_profile.get(attr, default)
        return getattr(user_profile, attr, default)

    budget_min = float(_read("budget_min", 0.0) or 0.0)
    budget_max = float(_read("budget_max", 0.0) or 0.0)
    timeline_days = int(_read("timeline_days", 90) or 90)
    risk_tolerance_raw = str(_read("risk_tolerance", "moderate") or "moderate").lower()

    # Tighter budget spread + shorter timeline → higher affordability pressure.
    spread = max(budget_max - budget_min, 0.0)
    affordability_pressure = (
        _clamp_unit(1.0 - (spread / budget_max)) if budget_max > 0 else 0.5
    )
    if timeline_days <= 30:
        affordability_pressure = _clamp_unit(affordability_pressure + 0.2)

    risk_to_optimism = {
        "conservative": 0.2,
        "moderate": 0.5,
        "aggressive": 0.8,
    }
    investor_optimism = risk_to_optimism.get(risk_tolerance_raw, 0.5)

    actor_type = infer_actor_type(user_profile)
    if actor_type is ActorType.SELLER:
        willingness_to_transact = _clamp_unit(0.6 + (1.0 - affordability_pressure) * 0.3)
    elif actor_type is ActorType.BUYER:
        willingness_to_transact = _clamp_unit(0.5 + investor_optimism * 0.4)
    else:
        willingness_to_transact = 0.5

    return ActorSignalState(
        affordability_pressure=affordability_pressure,
        trust_in_trajectory=_clamp_signed(investor_optimism * 2.0 - 1.0),
        perceived_safety=0.5,
        social_proof=0.5,
        displacement_concern=affordability_pressure * 0.5,
        investor_optimism=investor_optimism,
        willingness_to_transact=willingness_to_transact,
        resistance_to_development=_clamp_unit(1.0 - investor_optimism),
    )


@dataclass(frozen=True, slots=True)
class CohortSignalState(ActorSignalState):
    """Cohort-aggregated actor signals — Phase C cohort memory primitive."""

    cohort_size: int = 0
    cohort_label: str = ""
    actor_type: ActorType = ActorType.UNKNOWN


def cohort_signals(
    snapshots: Iterable[ActorSignalState],
    *,
    actor_type: ActorType = ActorType.UNKNOWN,
    label: str = "",
) -> CohortSignalState:
    """Average a list of actor snapshots into a single :class:`CohortSignalState`.

    Empty input returns a zeroed cohort (size 0). Mixing :class:`ActorSignalState`
    with :class:`HouseholdSignalSnapshot` is fine — only the eight base
    pressure fields participate in the average.
    """
    snapshots_list = list(snapshots)
    if not snapshots_list:
        return CohortSignalState(cohort_size=0, cohort_label=label, actor_type=actor_type)

    averages: dict[str, float] = {}
    for field_def in fields(ActorSignalState):
        values = [float(getattr(snapshot, field_def.name)) for snapshot in snapshots_list]
        averages[field_def.name] = sum(values) / len(values)

    return CohortSignalState(
        **averages,
        cohort_size=len(snapshots_list),
        cohort_label=label,
        actor_type=actor_type,
    )
