"""Domain helpers for social reaction modeling."""

from __future__ import annotations

from typing import Any


SOCIAL_REACTION_TOPICS = [
    "market_prices",
    "eviction_policy",
    "voucher_program",
    "neighborhood_safety",
]

ALLOWED_REACTION_TOPICS = frozenset(SOCIAL_REACTION_TOPICS)

TOPIC_DESCRIPTIONS = {
    "market_prices": "local housing prices, affordability, and market trends",
    "eviction_policy": (
        "tenant protections, eviction moratoriums, and landlord-tenant relations"
    ),
    "voucher_program": (
        "Section 8 / housing choice vouchers and subsidized housing programs"
    ),
    "neighborhood_safety": (
        "crime, community investment, policing, and neighborhood quality"
    ),
}


def _clamp_signed(value: float) -> float:
    return max(-1.0, min(1.0, value))


def validate_topics(topics: list[str] | None) -> list[str]:
    """Return the requested topic list or raise when an unknown topic appears."""
    if not topics:
        return list(SOCIAL_REACTION_TOPICS)

    invalid_topics = sorted(set(topics) - ALLOWED_REACTION_TOPICS)
    if invalid_topics:
        invalid_text = ", ".join(invalid_topics)
        raise ValueError(f"Unsupported social reaction topics: {invalid_text}")
    return list(topics)


def communication_style_multiplier(style: Any) -> float:
    """Weight participation based on communication style."""
    style_value = getattr(style, "value", style)
    if style_value == "vocal":
        return 1.5
    if style_value == "passive":
        return 0.5
    if style_value == "analytical":
        return 1.1
    if style_value == "emotional":
        return 1.2
    return 1.0


def build_initial_opinions(household: Any) -> dict[str, float]:
    """Project persisted household fields into reaction-topic opinions.

    These seeds intentionally stay close to the persisted profile values so the
    simulator preserves its historical baseline behavior. Richer actor-signal
    adjustments can happen during reaction updates without changing the initial
    contract relied on by the current test suite and report pipeline.
    """
    market_sentiment = float(
        getattr(household, "housing_market_sentiment", 0.0) or 0.0,
    )
    policy_support = float(getattr(household, "policy_support_score", 0.0) or 0.0)
    neighborhood_satisfaction = float(
        getattr(household, "neighborhood_satisfaction", 0.5) or 0.5,
    )

    return {
        "market_prices": _clamp_signed(market_sentiment),
        "eviction_policy": _clamp_signed(policy_support),
        "voucher_program": _clamp_signed(policy_support),
        "neighborhood_safety": _clamp_signed((neighborhood_satisfaction * 2.0) - 1.0),
    }
