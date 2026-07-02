"""Pure scoring logic for a buyer agent. No I/O."""

from __future__ import annotations

import math

from domain.buyer_sim.models import BuyerProfile, PropertyFeatures


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km between two (lat, lon) points."""
    r = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


# Weights for combining factors into final score
_WEIGHTS: dict[str, float] = {
    "budget_fit": 0.30,
    "hazard_safety": 0.15,
    "commute_fit": 0.20,
    "construction_match": 0.10,
    "seismic": 0.05,
    "yield_fit": 0.10,
    "social_proof": 0.10,
}


def score_property(
    buyer: BuyerProfile,
    prop: PropertyFeatures,
    gnn_embedding: tuple[float, ...] | None = None,
) -> tuple[float, dict[str, float]]:
    """Score a property for a buyer.

    Returns:
        (score [0,1], factor_breakdown dict)
    """
    factors: dict[str, float] = {}
    raw = prop.raw_features

    # Budget fit: 1.0 if asking <= budget, decays exponentially above
    budget_ratio = prop.asking_price_yen / max(buyer.budget_yen, 1)
    factors["budget_fit"] = max(0.0, 1.0 - max(0.0, budget_ratio - 1.0) * 5.0)

    # Hazard avoidance: penalize based on hazard_sensitivity x hazard scores
    hazard_score = (
        float(raw.get("hazard_flood", 0))
        + float(raw.get("hazard_liquefaction", 0))
        + float(raw.get("hazard_landslide", 0))
    ) / 30.0
    factors["hazard_safety"] = max(0.0, 1.0 - buyer.hazard_sensitivity * hazard_score)

    # Commute distance (haversine km -> score)
    dist_km = haversine(
        buyer.commute_target_lat,
        buyer.commute_target_lng,
        prop.latitude,
        prop.longitude,
    )
    # Rough: 1 km ~ 2 min by train. If > max_commute, score drops
    estimated_minutes = dist_km * 2.0
    max_commute = max(buyer.max_commute_minutes, 1)
    factors["commute_fit"] = max(
        0.0,
        1.0 - max(0.0, estimated_minutes - max_commute) / max_commute,
    )

    # Construction preference match
    construction_type = str(raw.get("construction_type", ""))
    factors["construction_match"] = (
        1.0 if construction_type in buyer.construction_pref else 0.6
    )

    # Yield target (investors only)
    if buyer.yield_target and buyer.life_stage == "investor":
        cap_rate = float(raw.get("cap_rate", 0.04))
        factors["yield_fit"] = min(1.0, cap_rate / buyer.yield_target)
    # Non-investors get a neutral default (handled by weighted sum default below)

    # Seismic safety bonus
    factors["seismic"] = (
        1.0 if raw.get("seismic_code") == "shin_taishin" else 0.7
    )

    # GNN social proof (if embedding available)
    if gnn_embedding and len(gnn_embedding) > 0:
        factors["social_proof"] = min(
            1.0, sum(gnn_embedding) / len(gnn_embedding)
        )

    # Weighted combination — missing factors default to 0.5 (neutral)
    total = sum(factors.get(k, 0.5) * w for k, w in _WEIGHTS.items())
    total = max(0.0, min(1.0, total))

    return total, factors


def compute_bid(
    buyer: BuyerProfile,
    score: float,
    asking_price_yen: int,
) -> int:
    """Compute bid amount based on score and budget.

    High score -> bid near asking price.
    Low score -> bid well below asking price.
    Never exceeds the buyer's budget.
    """
    # bid_ratio in [0.7, 1.05] of asking price
    bid_ratio = 0.7 + 0.35 * score
    bid = int(asking_price_yen * bid_ratio)
    return min(bid, buyer.budget_yen)
