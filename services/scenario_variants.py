"""Scenario variant definitions for batch negotiation simulation.

Inspired by MiroFish's ScenarioSpecGenerator — each variant describes
a distinct market condition with constraints that alter agent behaviour.
"""

from dataclasses import dataclass, field


@dataclass
class ScenarioVariant:
    """One scenario configuration for a batch simulation run."""

    name: str
    description: str
    constraints: dict = field(default_factory=dict)
    max_rounds: int = 15


SCENARIO_VARIANTS: list[ScenarioVariant] = [
    ScenarioVariant(
        name="market_favors_buyer",
        description="Low demand, property on market 90+ days — seller feels urgency",
        constraints={
            "seller_urgency": "high",
            "competing_offers": 0,
            "initial_offer_discount_pct": 12,
            "days_on_market": 95,
        },
        max_rounds=15,
    ),
    ScenarioVariant(
        name="market_favors_seller",
        description="Hot market with multiple competing offers — buyer must act fast",
        constraints={
            "buyer_urgency": "high",
            "competing_offers": 3,
            "max_discount_pct": 3,
            "days_on_market": 5,
        },
        max_rounds=12,
    ),
    ScenarioVariant(
        name="balanced_market",
        description="Normal market conditions — neither party has clear leverage",
        constraints={
            "competing_offers": 1,
            "max_discount_pct": 8,
            "days_on_market": 30,
        },
        max_rounds=15,
    ),
    ScenarioVariant(
        name="aggressive_buyer",
        description="Buyer pushes hard with a low initial offer and aggressive counters",
        constraints={
            "initial_offer_discount_pct": 15,
            "buyer_style": "aggressive",
            "max_counter_increment_pct": 2.0,
        },
        max_rounds=20,
    ),
    ScenarioVariant(
        name="conservative_approach",
        description="Small increments, patient negotiation with many rounds",
        constraints={
            "max_counter_increment_pct": 1.5,
            "min_rounds_before_accept": 5,
            "buyer_style": "conservative",
            "seller_style": "conservative",
        },
        max_rounds=25,
    ),
    ScenarioVariant(
        name="time_pressure",
        description="Both sides want a quick close — hard deadline looming",
        constraints={
            "soft_turn_limit": 5,
            "deadline_urgency": "high",
            "buyer_urgency": "high",
            "seller_urgency": "high",
        },
        max_rounds=8,
    ),
]


def get_variant(name: str) -> ScenarioVariant | None:
    """Look up a scenario variant by name."""
    for v in SCENARIO_VARIANTS:
        if v.name == name:
            return v
    return None


def list_variants() -> list[dict]:
    """Return all variants as plain dicts (for API responses)."""
    return [
        {
            "name": v.name,
            "description": v.description,
            "constraints": v.constraints,
            "max_rounds": v.max_rounds,
        }
        for v in SCENARIO_VARIANTS
    ]
