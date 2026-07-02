"""Generate realistic Tokyo buyer profiles. Deterministic given a seed."""

from __future__ import annotations

import random

from domain.buyer_sim.models import BuyerProfile

# Tokyo commute targets (major business districts)
COMMUTE_TARGETS: tuple[tuple[float, float, str], ...] = (
    (35.6812, 139.7671, "Marunouchi"),  # Tokyo Station
    (35.6595, 139.7004, "Shibuya"),
    (35.6938, 139.7034, "Shinjuku"),
    (35.6654, 139.7707, "Ginza"),
    (35.6284, 139.7387, "Shinagawa"),
    (35.7295, 139.7109, "Ikebukuro"),
    (35.6580, 139.7514, "Roppongi"),
)

LIFE_STAGE_DISTRIBUTION: dict[str, float] = {
    "first_time": 0.35,  # young couples/singles, budget 30-60M
    "upgrade": 0.25,  # families upgrading, budget 50-100M
    "investor": 0.25,  # yield-seeking, budget 20-200M
    "retiree": 0.15,  # downsizing, budget 30-80M
}

_LIFE_STAGES = list(LIFE_STAGE_DISTRIBUTION.keys())
_LIFE_STAGE_WEIGHTS = list(LIFE_STAGE_DISTRIBUTION.values())

# Construction preferences by life stage
_CONSTRUCTION_PREFS: dict[str, tuple[tuple[str, ...], ...]] = {
    "first_time": (
        ("rc", "src"),
        ("rc",),
        ("rc", "src", "steel"),
    ),
    "upgrade": (
        ("rc", "src"),
        ("rc", "src", "steel"),
        ("src",),
    ),
    "investor": (
        ("rc", "src"),
        ("rc", "src", "steel", "light_steel"),
        ("wood", "light_steel"),
        ("rc",),
    ),
    "retiree": (
        ("rc", "src"),
        ("src",),
        ("rc",),
    ),
}


def _pick_life_stage(rng: random.Random) -> str:
    """Pick a life stage according to the distribution."""
    r = rng.random()
    cumulative = 0.0
    for stage, weight in LIFE_STAGE_DISTRIBUTION.items():
        cumulative += weight
        if r < cumulative:
            return stage
    return _LIFE_STAGES[-1]


def _generate_first_time(agent_id: int, rng: random.Random) -> BuyerProfile:
    """Generate a first-time buyer profile (young couples/singles)."""
    target = rng.choice(COMMUTE_TARGETS)
    return BuyerProfile(
        agent_id=agent_id,
        budget_yen=rng.randint(30_000_000, 60_000_000),
        risk_tolerance=round(rng.uniform(0.3, 0.6), 2),
        life_stage="first_time",
        construction_pref=rng.choice(_CONSTRUCTION_PREFS["first_time"]),
        commute_target_lat=target[0],
        commute_target_lng=target[1],
        max_commute_minutes=rng.randint(25, 40),
        hazard_sensitivity=round(rng.uniform(0.6, 0.9), 2),
        yield_target=None,
    )


def _generate_upgrade(agent_id: int, rng: random.Random) -> BuyerProfile:
    """Generate an upgrade buyer profile (families upgrading)."""
    target = rng.choice(COMMUTE_TARGETS)
    return BuyerProfile(
        agent_id=agent_id,
        budget_yen=rng.randint(50_000_000, 100_000_000),
        risk_tolerance=round(rng.uniform(0.3, 0.5), 2),
        life_stage="upgrade",
        construction_pref=rng.choice(_CONSTRUCTION_PREFS["upgrade"]),
        commute_target_lat=target[0],
        commute_target_lng=target[1],
        max_commute_minutes=rng.randint(30, 50),
        hazard_sensitivity=round(rng.uniform(0.5, 0.8), 2),
        yield_target=None,
    )


def _generate_investor(agent_id: int, rng: random.Random) -> BuyerProfile:
    """Generate an investor buyer profile (yield-seeking)."""
    target = rng.choice(COMMUTE_TARGETS)
    return BuyerProfile(
        agent_id=agent_id,
        budget_yen=rng.randint(20_000_000, 200_000_000),
        risk_tolerance=round(rng.uniform(0.5, 0.9), 2),
        life_stage="investor",
        construction_pref=rng.choice(_CONSTRUCTION_PREFS["investor"]),
        commute_target_lat=target[0],
        commute_target_lng=target[1],
        max_commute_minutes=rng.randint(40, 90),
        hazard_sensitivity=round(rng.uniform(0.2, 0.5), 2),
        yield_target=round(rng.uniform(0.04, 0.07), 3),
    )


def _generate_retiree(agent_id: int, rng: random.Random) -> BuyerProfile:
    """Generate a retiree buyer profile (downsizing)."""
    target = rng.choice(COMMUTE_TARGETS)
    return BuyerProfile(
        agent_id=agent_id,
        budget_yen=rng.randint(30_000_000, 80_000_000),
        risk_tolerance=round(rng.uniform(0.1, 0.3), 2),
        life_stage="retiree",
        construction_pref=rng.choice(_CONSTRUCTION_PREFS["retiree"]),
        commute_target_lat=target[0],
        commute_target_lng=target[1],
        max_commute_minutes=rng.randint(15, 30),
        hazard_sensitivity=round(rng.uniform(0.7, 0.95), 2),
        yield_target=None,
    )


_GENERATORS = {
    "first_time": _generate_first_time,
    "upgrade": _generate_upgrade,
    "investor": _generate_investor,
    "retiree": _generate_retiree,
}


def generate_buyers(n: int, seed: int | None = None) -> tuple[BuyerProfile, ...]:
    """Generate n realistic Tokyo buyer profiles.

    Deterministic when seed is provided.
    """
    rng = random.Random(seed)
    buyers: list[BuyerProfile] = []

    for i in range(n):
        life_stage = _pick_life_stage(rng)
        generator = _GENERATORS[life_stage]
        buyers.append(generator(agent_id=i, rng=rng))

    return tuple(buyers)
