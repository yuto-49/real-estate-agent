"""Pure feature extraction for buyer simulation. No I/O."""

from __future__ import annotations

import math
from typing import Any

from domain.buyer_sim.models import PropertyFeatures

FEATURE_KEYS: list[str] = [
    "menseki_m2",
    "built_year",
    "walk_minutes",
    "construction_wood",
    "construction_light_steel",
    "construction_steel",
    "construction_rc",
    "construction_src",
    "seismic_shin",
    "asset_one_room",
    "asset_aparuto",
    "asset_family",
    "asking_price_norm",
    "kanrihi_norm",
    "occupancy_rate",
    "hazard_flood",
    "hazard_liquefaction",
    "hazard_landslide",
    "median_sale_price_norm",
    "land_price_norm",
    "re_buildable",
]

_CONSTRUCTION_TYPES = ("wood", "light_steel", "steel", "rc", "src")
_ASSET_TIERS = ("one_room", "aparuto", "family")

DEFAULT_NORMALIZATION: dict[str, tuple[float, float]] = {
    "menseki_m2": (10.0, 200.0),
    "built_year": (1960.0, 2026.0),
    "walk_minutes": (1.0, 30.0),
    "asking_price_norm": (0.0, 500_000_000.0),
    "kanrihi_norm": (0.0, 50_000.0),
    "hazard_flood": (0.0, 10.0),
    "hazard_liquefaction": (0.0, 10.0),
    "hazard_landslide": (0.0, 10.0),
    "median_sale_price_norm": (0.0, 500_000_000.0),
    "land_price_norm": (0.0, 2_000_000.0),
}


def _normalize_minmax(value: float, min_val: float, max_val: float) -> float:
    """Normalize a value to [0,1] using min/max bounds."""
    if max_val <= min_val:
        return 0.0
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def _normalize_log(value: float, max_val: float) -> float:
    """Normalize using log scaling: log(1+x) / log(1+max)."""
    if max_val <= 0:
        return 0.0
    denom = math.log1p(max_val)
    if denom == 0:
        return 0.0
    return max(0.0, min(1.0, math.log1p(max(0, value)) / denom))


def _one_hot_construction(construction_type: str) -> dict[str, float]:
    """One-hot encode construction type into feature dict entries."""
    result: dict[str, float] = {}
    ct_lower = construction_type.lower() if construction_type else ""
    for ct in _CONSTRUCTION_TYPES:
        key = f"construction_{ct}"
        result[key] = 1.0 if ct_lower == ct else 0.0
    return result


def _one_hot_asset_tier(asset_tier: str) -> dict[str, float]:
    """One-hot encode asset tier into feature dict entries."""
    result: dict[str, float] = {}
    at_lower = asset_tier.lower() if asset_tier else ""
    for at in _ASSET_TIERS:
        key = f"asset_{at}"
        result[key] = 1.0 if at_lower == at else 0.0
    return result


def extract_features(
    property_data: dict[str, Any],
    signals: dict[str, float],
    normalization: dict[str, tuple[float, float]],
) -> PropertyFeatures:
    """Extract and normalize property features into a PropertyFeatures instance.

    Args:
        property_data: Raw property data dict (from DB row or API).
            Expected keys: property_id, latitude, longitude, menseki_m2,
            built_year, walk_minutes, construction_type, asset_tier,
            seismic_code, asking_price_yen, kanrihi, occupancy_rate,
            hazard_flood, hazard_liquefaction, hazard_landslide, re_buildable.
        signals: Market signal values keyed by signal name.
            Expected keys: median_sale_price, land_price.
        normalization: Min/max bounds per feature key as (min, max) tuples.
            Keys should match FEATURE_KEYS for numeric features.
            For log-scaled features (asking_price_norm, land_price_norm,
            median_sale_price_norm), the max value is used for log scaling.

    Returns:
        PropertyFeatures with normalized feature_vector and raw_features.
    """
    raw: dict[str, Any] = {}
    features: dict[str, float] = {}

    # --- Numeric features with min/max normalization ---
    menseki = float(property_data.get("menseki_m2", 0))
    raw["menseki_m2"] = menseki
    mn, mx = normalization.get("menseki_m2", (0.0, 200.0))
    features["menseki_m2"] = _normalize_minmax(menseki, mn, mx)

    built_year = float(property_data.get("built_year", 1990))
    raw["built_year"] = built_year
    mn, mx = normalization.get("built_year", (1960.0, 2025.0))
    features["built_year"] = _normalize_minmax(built_year, mn, mx)

    walk_minutes = float(property_data.get("walk_minutes", 10))
    raw["walk_minutes"] = walk_minutes
    mn, mx = normalization.get("walk_minutes", (1.0, 30.0))
    features["walk_minutes"] = _normalize_minmax(walk_minutes, mn, mx)

    # --- One-hot: construction type ---
    construction_type = str(property_data.get("construction_type", ""))
    raw["construction_type"] = construction_type
    ct_encoded = _one_hot_construction(construction_type)
    features.update(ct_encoded)

    # --- Binary: seismic code ---
    seismic_code = str(property_data.get("seismic_code", ""))
    raw["seismic_code"] = seismic_code
    features["seismic_shin"] = 1.0 if seismic_code == "shin_taishin" else 0.0

    # --- One-hot: asset tier ---
    asset_tier = str(property_data.get("asset_tier", ""))
    raw["asset_tier"] = asset_tier
    at_encoded = _one_hot_asset_tier(asset_tier)
    features.update(at_encoded)

    # --- Log-scaled price features ---
    asking_price = float(property_data.get("asking_price_yen", 0))
    raw["asking_price_yen"] = asking_price
    _, price_max = normalization.get("asking_price_norm", (0.0, 500_000_000.0))
    features["asking_price_norm"] = _normalize_log(asking_price, price_max)

    kanrihi = float(property_data.get("kanrihi", 0))
    raw["kanrihi"] = kanrihi
    mn, mx = normalization.get("kanrihi_norm", (0.0, 50_000.0))
    features["kanrihi_norm"] = _normalize_minmax(kanrihi, mn, mx)

    occupancy_rate = float(property_data.get("occupancy_rate", 1.0))
    raw["occupancy_rate"] = occupancy_rate
    features["occupancy_rate"] = max(0.0, min(1.0, occupancy_rate))

    # --- Hazard features (default 0 if missing) ---
    hazard_flood = float(property_data.get("hazard_flood", 0))
    raw["hazard_flood"] = hazard_flood
    mn, mx = normalization.get("hazard_flood", (0.0, 10.0))
    features["hazard_flood"] = _normalize_minmax(hazard_flood, mn, mx)

    hazard_liquefaction = float(property_data.get("hazard_liquefaction", 0))
    raw["hazard_liquefaction"] = hazard_liquefaction
    mn, mx = normalization.get("hazard_liquefaction", (0.0, 10.0))
    features["hazard_liquefaction"] = _normalize_minmax(hazard_liquefaction, mn, mx)

    hazard_landslide = float(property_data.get("hazard_landslide", 0))
    raw["hazard_landslide"] = hazard_landslide
    mn, mx = normalization.get("hazard_landslide", (0.0, 10.0))
    features["hazard_landslide"] = _normalize_minmax(hazard_landslide, mn, mx)

    # --- Market signal features (log-scaled) ---
    median_sale_price = float(signals.get("median_sale_price", 0))
    raw["median_sale_price"] = median_sale_price
    _, msp_max = normalization.get("median_sale_price_norm", (0.0, 500_000_000.0))
    features["median_sale_price_norm"] = _normalize_log(median_sale_price, msp_max)

    land_price = float(signals.get("land_price", 0))
    raw["land_price"] = land_price
    _, lp_max = normalization.get("land_price_norm", (0.0, 2_000_000.0))
    features["land_price_norm"] = _normalize_log(land_price, lp_max)

    # --- Binary: re-buildable ---
    re_buildable = bool(property_data.get("re_buildable", True))
    raw["re_buildable"] = re_buildable
    features["re_buildable"] = 1.0 if re_buildable else 0.0

    # --- Carry over additional raw features for scoring ---
    if "cap_rate" in property_data:
        raw["cap_rate"] = float(property_data["cap_rate"])

    # Build ordered feature vector matching FEATURE_KEYS
    feature_vector = tuple(features.get(k, 0.0) for k in FEATURE_KEYS)

    return PropertyFeatures(
        property_id=str(property_data.get("property_id", "")),
        latitude=float(property_data.get("latitude", 0.0)),
        longitude=float(property_data.get("longitude", 0.0)),
        feature_vector=feature_vector,
        asking_price_yen=int(asking_price),
        raw_features=raw,
    )
