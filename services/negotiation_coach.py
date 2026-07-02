"""Negotiation strategy coach — broker-facing coaching wrapper.

Wraps the existing simulation/reaction domain layer to provide
scenario-based negotiation rehearsal for brokers.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClientProfile:
    role: str                     # "seller" | "buyer"
    reservation_price_yen: int    # walk-away price
    batna_yen: int | None = None  # best alternative
    motivation: str = "standard"  # "urgent", "standard", "patient"
    experience_level: str = "intermediate"  # "novice", "intermediate", "expert"


@dataclass(frozen=True)
class CounterpartyProfile:
    role: str                     # opposite of client
    archetype: str = "balanced"   # "aggressive", "balanced", "conservative", "motivated"
    estimated_budget_yen: int | None = None
    motivation: str = "standard"


@dataclass(frozen=True)
class ScenarioResult:
    scenario_label: str
    opening_price_yen: int
    rounds: int
    settlement_price_yen: int | None
    settled: bool
    concession_path: tuple[int, ...] = ()  # price at each round
    zopa_low_yen: int | None = None
    zopa_high_yen: int | None = None


@dataclass(frozen=True)
class CoachingResult:
    property_address: str | None
    client_role: str
    recommended_opening_yen: int
    concession_ladder: tuple[int, ...]
    walk_away_yen: int
    zopa_analysis: str
    scenarios: tuple[ScenarioResult, ...] = ()
    coaching_notes: tuple[str, ...] = ()
    generated_at: datetime = field(default_factory=datetime.utcnow)


def run_coaching_session(
    *,
    asking_price_yen: int,
    client: ClientProfile,
    counterparty: CounterpartyProfile | None = None,
    property_address: str | None = None,
    num_scenarios: int = 3,
    max_rounds: int = 8,
    seed: int | None = None,
) -> CoachingResult:
    """Run negotiation coaching scenarios.

    Generates multiple scenarios varying counterparty behavior
    and produces coaching recommendations.
    """
    if counterparty is None:
        counter_role = "buyer" if client.role == "seller" else "seller"
        counterparty = CounterpartyProfile(role=counter_role)

    rng = random.Random(seed)

    scenarios: list[ScenarioResult] = []
    scenario_labels = ["Conservative buyer", "Balanced buyer", "Aggressive buyer"]
    aggression_levels = [0.3, 0.5, 0.8]

    if client.role == "buyer":
        scenario_labels = ["Conservative seller", "Balanced seller", "Aggressive seller"]

    for i in range(min(num_scenarios, len(scenario_labels))):
        label = scenario_labels[i]
        aggression = aggression_levels[i]
        scenario = _simulate_scenario(
            asking_price_yen=asking_price_yen,
            client=client,
            aggression=aggression,
            max_rounds=max_rounds,
            rng=rng,
        )
        scenarios.append(ScenarioResult(
            scenario_label=label,
            opening_price_yen=scenario["opening"],
            rounds=scenario["rounds"],
            settlement_price_yen=scenario["settlement"],
            settled=scenario["settled"],
            concession_path=tuple(scenario["path"]),
            zopa_low_yen=scenario["zopa_low"],
            zopa_high_yen=scenario["zopa_high"],
        ))

    # Derive coaching recommendations
    settled_scenarios = [s for s in scenarios if s.settled]
    if settled_scenarios:
        settlements = [s.settlement_price_yen for s in settled_scenarios if s.settlement_price_yen]
        avg_settlement = int(sum(settlements) / len(settlements)) if settlements else asking_price_yen
    else:
        avg_settlement = asking_price_yen

    # Concession ladder: 3-5 steps from opening to reservation
    spread = abs(asking_price_yen - client.reservation_price_yen)
    steps = min(5, max(3, max_rounds // 2))
    step_size = spread // steps if steps > 0 else 0
    if client.role == "seller":
        ladder = tuple(asking_price_yen - (i * step_size) for i in range(steps + 1))
    else:
        ladder = tuple(asking_price_yen + (i * step_size) for i in range(steps + 1))

    # ZOPA analysis
    all_zopa_lows = [s.zopa_low_yen for s in scenarios if s.zopa_low_yen]
    all_zopa_highs = [s.zopa_high_yen for s in scenarios if s.zopa_high_yen]

    if all_zopa_lows and all_zopa_highs:
        zopa_text = (
            f"ZOPA estimated between \u00a5{min(all_zopa_lows):,} and \u00a5{max(all_zopa_highs):,}. "
            f"Settlement most likely near \u00a5{avg_settlement:,}."
        )
    else:
        zopa_text = "ZOPA could not be reliably estimated. Consider adjusting reservation price."

    # Coaching notes
    notes: list[str] = []
    if client.motivation == "urgent":
        notes.append("Client is motivated \u2014 consider larger early concessions to close quickly.")
    if any(not s.settled for s in scenarios):
        notes.append("Some scenarios did not reach settlement \u2014 reservation price may be too aggressive.")
    if spread < asking_price_yen * 0.03:
        notes.append("Narrow spread between asking and reservation \u2014 limited negotiation room.")

    return CoachingResult(
        property_address=property_address,
        client_role=client.role,
        recommended_opening_yen=asking_price_yen,
        concession_ladder=ladder,
        walk_away_yen=client.reservation_price_yen,
        zopa_analysis=zopa_text,
        scenarios=tuple(scenarios),
        coaching_notes=tuple(notes),
    )


def _simulate_scenario(
    *,
    asking_price_yen: int,
    client: ClientProfile,
    aggression: float,
    max_rounds: int,
    rng: random.Random,
) -> dict:
    """Simulate a single negotiation scenario."""
    is_seller = client.role == "seller"
    reservation = client.reservation_price_yen

    # Counterparty's hidden reservation (unknown to broker)
    if is_seller:
        # Buyer's max willingness to pay
        counter_max = int(asking_price_yen * rng.uniform(0.85, 1.05))
        counter_opening = int(counter_max * (1 - aggression * 0.15))
        current_offer = counter_opening
        current_ask = asking_price_yen
    else:
        # Seller's minimum acceptable
        counter_min = int(asking_price_yen * rng.uniform(0.90, 1.10))
        counter_opening = int(counter_min * (1 + aggression * 0.15))
        current_offer = asking_price_yen
        current_ask = counter_opening

    path = [current_offer if is_seller else current_ask]
    settled = False
    settlement = None
    rounds = 0

    for r in range(max_rounds):
        rounds = r + 1
        spread_pct = abs(current_ask - current_offer) / max(current_ask, 1)

        # Check ZOPA overlap
        if is_seller:
            if current_offer >= reservation:
                settled = True
                settlement = (current_offer + current_ask) // 2
                break
        else:
            if current_ask <= reservation:
                settled = True
                settlement = (current_offer + current_ask) // 2
                break

        # Concession: each side moves toward center
        noise = rng.uniform(0.8, 1.2)
        concession_rate = 0.15 * noise * (1 - aggression * 0.3)

        if is_seller:
            current_ask = int(current_ask - abs(current_ask - current_offer) * concession_rate * 0.5)
            current_offer = int(current_offer + abs(current_ask - current_offer) * concession_rate)
        else:
            current_offer = int(current_offer + abs(current_ask - current_offer) * concession_rate * 0.5)
            current_ask = int(current_ask - abs(current_ask - current_offer) * concession_rate)

        path.append(current_offer if is_seller else current_ask)

    # ZOPA bounds
    zopa_low = min(reservation, counter_opening) if is_seller else min(asking_price_yen, reservation)
    zopa_high = max(asking_price_yen, counter_opening if is_seller else reservation)

    return {
        "opening": counter_opening if is_seller else asking_price_yen,
        "rounds": rounds,
        "settlement": settlement,
        "settled": settled,
        "path": path,
        "zopa_low": zopa_low,
        "zopa_high": zopa_high,
    }
