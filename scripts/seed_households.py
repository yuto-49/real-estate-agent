"""Seed synthetic households with social graph edges for social simulation.

Generates 100 households across multiple zip codes with income-correlated
opinion fields and builds a social graph based on proximity, income, language,
and demographic similarity.

Usage:
    python scripts/seed_households.py [--count 100] [--seed 42]
"""

import argparse
import asyncio
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import async_session, engine, Base
from db.models import HouseholdProfile, HouseholdSocialEdge

# ── Configuration ──

ZIP_CODES = ["60601", "60602", "60614", "60615", "60622", "60640", "60647", "60651"]

INCOME_BANDS = {
    "low":      {"range": (18_000, 35_000), "weight": 0.25},
    "moderate":  {"range": (35_000, 60_000), "weight": 0.30},
    "middle":    {"range": (60_000, 100_000), "weight": 0.30},
    "upper":     {"range": (100_000, 180_000), "weight": 0.15},
}

LANGUAGES = [
    ("english", 0.60), ("spanish", 0.20), ("polish", 0.08),
    ("mandarin", 0.05), ("tagalog", 0.04), ("arabic", 0.03),
]

AGE_BRACKETS = ["18-29", "30-45", "46-64", "65+"]
AGE_WEIGHTS = [0.20, 0.35, 0.30, 0.15]

HOUSING_TYPES = ["renter", "owner", "voucher"]
HOUSING_WEIGHTS_BY_INCOME = {
    "low":      [0.60, 0.10, 0.30],
    "moderate":  [0.50, 0.30, 0.20],
    "middle":    [0.25, 0.65, 0.10],
    "upper":     [0.10, 0.85, 0.05],
}

COMM_STYLES = ["vocal", "passive", "analytical", "emotional"]
INFLUENCE_RANGES = {
    "vocal": (0.7, 1.0),
    "analytical": (0.5, 0.8),
    "emotional": (0.4, 0.7),
    "passive": (0.1, 0.3),
}

FIRST_NAMES = [
    "Maria", "James", "Wei", "Fatima", "Carlos", "Priya", "Ahmed", "Elena",
    "David", "Yuki", "Omar", "Sarah", "Andrzej", "Lucia", "Chen", "Rosa",
    "Michael", "Aisha", "Jorge", "Thanh", "Olga", "Marcus", "Mei", "Hassan",
    "Anna", "Roberto", "Kenji", "Amara", "Ivan", "Guadalupe", "Thomas", "Nadia",
    "Peter", "Linh", "Samuel", "Zara", "Diego", "Hana", "Victor", "Rina",
]

LAST_NAMES = [
    "Garcia", "Chen", "Williams", "Patel", "Kim", "Nguyen", "Kowalski", "Smith",
    "Rodriguez", "Ali", "Johnson", "Tanaka", "Martinez", "Lee", "Brown", "Singh",
    "Lopez", "Wang", "Davis", "Okafor", "Miller", "Hassan", "Wilson", "Yamamoto",
    "Moore", "Rossi", "Taylor", "Muller", "Anderson", "Santos",
]


def _pick_weighted(items: list[str], weights: list[float], rng: random.Random) -> str:
    return rng.choices(items, weights=weights, k=1)[0]


def _pick_income_band(rng: random.Random) -> str:
    bands = list(INCOME_BANDS.keys())
    weights = [INCOME_BANDS[b]["weight"] for b in bands]
    return _pick_weighted(bands, weights, rng)


def _pick_language(rng: random.Random) -> str:
    langs, weights = zip(*LANGUAGES)
    return _pick_weighted(list(langs), list(weights), rng)


def generate_household(rng: random.Random) -> HouseholdProfile:
    """Generate one synthetic household with income-correlated opinions."""
    income_band = _pick_income_band(rng)
    income_range = INCOME_BANDS[income_band]["range"]
    monthly_income = rng.randint(income_range[0], income_range[1]) / 12

    age_bracket = _pick_weighted(AGE_BRACKETS, AGE_WEIGHTS, rng)
    housing_type = _pick_weighted(
        HOUSING_TYPES, HOUSING_WEIGHTS_BY_INCOME[income_band], rng
    )
    has_voucher = 1 if housing_type == "voucher" else 0

    # Housing cost as fraction of income (30% target, higher for low income)
    cost_burden = rng.uniform(0.25, 0.55) if income_band == "low" else rng.uniform(0.20, 0.35)
    monthly_housing_cost = round(monthly_income * cost_burden, 2)

    # Eviction risk: inversely correlated with income, higher for renters/voucher
    base_eviction = {"low": 0.3, "moderate": 0.15, "middle": 0.05, "upper": 0.02}[income_band]
    if housing_type == "owner":
        base_eviction *= 0.1
    eviction_risk = round(min(1.0, base_eviction + rng.uniform(-0.05, 0.10)), 3)

    household_size = rng.choices([1, 2, 3, 4, 5, 6], weights=[0.15, 0.25, 0.25, 0.20, 0.10, 0.05])[0]
    num_children = max(0, household_size - rng.randint(1, 2)) if household_size > 1 else 0

    comm_style = rng.choice(COMM_STYLES)
    inf_lo, inf_hi = INFLUENCE_RANGES[comm_style]

    # Income-correlated opinion initialization
    # Low income → bearish on market, supportive of policy, lower satisfaction
    income_factor = {"low": -0.4, "moderate": -0.1, "middle": 0.15, "upper": 0.35}[income_band]
    policy_factor = {"low": 0.5, "moderate": 0.3, "middle": 0.0, "upper": -0.3}[income_band]

    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)

    return HouseholdProfile(
        name=f"{first} {last} Household",
        zip_code=rng.choice(ZIP_CODES),
        income_band=income_band,
        household_size=household_size,
        num_children=num_children,
        primary_language=_pick_language(rng),
        age_bracket=age_bracket,
        housing_type=housing_type,
        has_housing_voucher=has_voucher,
        monthly_housing_cost=monthly_housing_cost,
        monthly_income=round(monthly_income, 2),
        eviction_risk=eviction_risk,
        housing_market_sentiment=round(max(-1, min(1, income_factor + rng.uniform(-0.3, 0.3))), 3),
        policy_support_score=round(max(-1, min(1, policy_factor + rng.uniform(-0.2, 0.2))), 3),
        neighborhood_satisfaction=round(max(0, min(1, 0.5 + income_factor * 0.5 + rng.uniform(-0.2, 0.2))), 3),
        influence_weight=round(rng.uniform(inf_lo, inf_hi), 3),
        communication_style=comm_style,
        opinion_stability=round(rng.uniform(0.2, 0.8), 3),
        persona_data={
            "negotiation_tendency": rng.choice(["cooperative", "competitive", "avoidant", "accommodating"]),
            "information_seeking": rng.choice(["active", "passive", "selective"]),
            "trust_level": round(rng.uniform(0.2, 0.9), 2),
        },
    )


def build_social_graph(
    households: list[HouseholdProfile],
    rng: random.Random,
    max_edges_per_household: int = 10,
) -> list[HouseholdSocialEdge]:
    """Build social graph edges between households.

    Rules:
    - neighbor: same zip_code → weight 0.6-0.9
    - income_peer: same income_band → weight 0.3-0.6
    - language_peer: same non-English language → weight 0.5-0.8
    - demographic: similar household_size (±1) → weight 0.2-0.4
    """
    edges: list[HouseholdSocialEdge] = []
    edge_counts: dict[str, int] = {h.id: 0 for h in households}
    seen_pairs: set[tuple[str, str]] = set()

    # Index households by attributes for efficient matching
    by_zip: dict[str, list[HouseholdProfile]] = {}
    by_income: dict[str, list[HouseholdProfile]] = {}
    by_lang: dict[str, list[HouseholdProfile]] = {}

    for h in households:
        by_zip.setdefault(h.zip_code, []).append(h)
        by_income.setdefault(h.income_band, []).append(h)
        if h.primary_language != "english":
            by_lang.setdefault(h.primary_language, []).append(h)

    def _add_edge(
        source: HouseholdProfile,
        target: HouseholdProfile,
        edge_type: str,
        weight_range: tuple[float, float],
    ) -> None:
        pair = tuple(sorted([source.id, target.id]))
        if pair in seen_pairs:
            return
        if edge_counts[source.id] >= max_edges_per_household:
            return
        if edge_counts[target.id] >= max_edges_per_household:
            return

        seen_pairs.add(pair)
        weight = round(rng.uniform(*weight_range), 3)
        edges.append(HouseholdSocialEdge(
            source_id=source.id, target_id=target.id,
            edge_weight=weight, edge_type=edge_type,
        ))
        edge_counts[source.id] += 1
        edge_counts[target.id] += 1

    # Neighbor edges (same zip)
    for zip_code, group in by_zip.items():
        for i, h1 in enumerate(group):
            candidates = [h2 for h2 in group[i + 1:] if edge_counts[h2.id] < max_edges_per_household]
            selected = rng.sample(candidates, min(3, len(candidates)))
            for h2 in selected:
                _add_edge(h1, h2, "neighbor", (0.6, 0.9))

    # Income peer edges
    for band, group in by_income.items():
        for i, h1 in enumerate(group):
            candidates = [h2 for h2 in group[i + 1:] if edge_counts[h2.id] < max_edges_per_household]
            selected = rng.sample(candidates, min(2, len(candidates)))
            for h2 in selected:
                _add_edge(h1, h2, "income_peer", (0.3, 0.6))

    # Language peer edges (non-English)
    for lang, group in by_lang.items():
        for i, h1 in enumerate(group):
            candidates = [h2 for h2 in group[i + 1:] if edge_counts[h2.id] < max_edges_per_household]
            selected = rng.sample(candidates, min(2, len(candidates)))
            for h2 in selected:
                _add_edge(h1, h2, "language_peer", (0.5, 0.8))

    # Demographic edges (similar household size ±1)
    for i, h1 in enumerate(households):
        if edge_counts[h1.id] >= max_edges_per_household:
            continue
        candidates = [
            h2 for h2 in households[i + 1:]
            if abs(h1.household_size - h2.household_size) <= 1
            and edge_counts[h2.id] < max_edges_per_household
        ]
        selected = rng.sample(candidates, min(2, len(candidates)))
        for h2 in selected:
            _add_edge(h1, h2, "demographic", (0.2, 0.4))

    return edges


async def seed(count: int = 100, seed_val: int = 42) -> None:
    rng = random.Random(seed_val)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Generate households
        households: list[HouseholdProfile] = []
        for _ in range(count):
            h = generate_household(rng)
            households.append(h)
            db.add(h)

        await db.flush()  # get IDs

        # Build and save social graph
        edges = build_social_graph(households, rng)
        for edge in edges:
            db.add(edge)

        # Update social_connections counts
        edge_counts: dict[str, int] = {}
        for edge in edges:
            edge_counts[edge.source_id] = edge_counts.get(edge.source_id, 0) + 1
            edge_counts[edge.target_id] = edge_counts.get(edge.target_id, 0) + 1

        for h in households:
            h.social_connections = edge_counts.get(h.id, 0)

        await db.commit()

        # Print summary
        income_dist = {}
        for h in households:
            income_dist[h.income_band] = income_dist.get(h.income_band, 0) + 1

        edge_types: dict[str, int] = {}
        for e in edges:
            edge_types[e.edge_type] = edge_types.get(e.edge_type, 0) + 1

        print(f"Seeded {count} households and {len(edges)} social edges.")
        print(f"  Income distribution: {income_dist}")
        print(f"  Edge types: {edge_types}")
        print(f"  Avg edges per household: {len(edges) * 2 / count:.1f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed households with social graph")
    parser.add_argument("--count", type=int, default=100, help="Number of households")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    asyncio.run(seed(args.count, args.seed))
