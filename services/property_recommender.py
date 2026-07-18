"""Deterministic property recommender (onboarding wizard P4).

Implements the scoring spec at ``doc/recommendation-scoring.md`` on the
``spec/recommendation-scoring`` branch — a subset grounded in the fields that
actually exist on ``Property`` + ``MarketContextSnapshot`` today.

Design rules (must hold across every change):

1. **Deterministic** — no LLM. Same inputs always produce the same score and
   the same rationale strings.
2. **Lenient** — missing data degrades to zero contribution with a
   ``"data unavailable"`` rationale; never raises.
3. **Normalized** — each component clamps to ``[0.0, 1.0]`` before weighting,
   so the final total is always ``[0.0, 1.0]``.
4. **Pure-Python** — no I/O in this module. Caller fetches inputs.

Caller pattern::

    snapshot = await build_snapshot(db, property_id=p.id)  # optional
    scored = score_property(profile, p, snapshot=snapshot)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from db.models import InvestorProfile, Property
from domain.market.models import MarketContextSnapshot


# ── component weights ───────────────────────────────────────────────────

_STRATEGY_WEIGHTS: dict[str, dict[str, float]] = {
    "buy_and_hold": {
        "strategy": 0.30,
        "risk": 0.25,
        "signal": 0.15,
        "underwriting": 0.20,
        "geo": 0.05,
        "momentum": 0.05,
    },
    "flip": {
        "strategy": 0.40,
        "risk": 0.10,
        "signal": 0.15,
        "underwriting": 0.15,
        "geo": 0.10,
        "momentum": 0.10,
    },
    "lease": {
        "strategy": 0.30,
        "risk": 0.20,
        "signal": 0.15,
        "underwriting": 0.20,
        "geo": 0.05,
        "momentum": 0.10,
    },
}
_DEFAULT_STRATEGY = "buy_and_hold"
_JP_ZIP_RE = re.compile(r"^\d{3}-?\d{4}$")
_US_ZIP_RE = re.compile(r"^\d{5}$")


def _weights_for(strategy: str | None) -> dict[str, float]:
    return _STRATEGY_WEIGHTS.get(strategy or _DEFAULT_STRATEGY, _STRATEGY_WEIGHTS[_DEFAULT_STRATEGY])


# ── small math helpers ─────────────────────────────────────────────────


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _safe_ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den in (None, 0):
        return None
    return num / den  # type: ignore[operator]


# ── outputs ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ScoredProperty:
    property_id: str
    score: float
    components: dict[str, float]
    rationale: list[str]
    property: Property = field(repr=False, compare=False)


# ── hard filters ───────────────────────────────────────────────────────


def passes_hard_filters(
    profile: InvestorProfile, prop: Property
) -> tuple[bool, str | None]:
    """Apply non-scoring constraints. Returns (passed, reason_if_not)."""
    asking_price = _asking_price(prop)
    if profile.budget is not None and asking_price > profile.budget * 1.05:
        return False, "over_budget"

    geo = profile.geography or {}
    if geo:
        zip_filter = _normalize_zip(geo.get("zip"))
        if zip_filter:
            prop_zip = _normalize_zip(_extract_zip(prop))
            if prop_zip and prop_zip != zip_filter:
                return False, "geography_zip_mismatch"

        location = _property_location(prop)
        for reason, profile_key, prop_key in (
            ("geography_prefecture_mismatch", "prefecture", "prefecture"),
            ("geography_state_mismatch", "state", "prefecture"),
            ("geography_municipality_mismatch", "municipality", "municipality"),
            ("geography_city_mismatch", "city", "municipality"),
            ("geography_ward_mismatch", "ward", "municipality"),
            ("geography_neighborhood_mismatch", "neighborhood", "neighborhood"),
        ):
            token = str(geo.get(profile_key) or "").strip()
            if not token:
                continue
            prop_value = location.get(prop_key)
            if prop_value:
                if not _location_matches(token, prop_value):
                    return False, reason
                continue
            if not _address_contains_token(token, location.get("address")):
                return False, reason

    return True, None


def _extract_zip(prop: Property) -> str | None:
    """Find a zip/postal code from listing fields or free-form address text."""
    address_jp = dict(prop.address_jp or {})
    for candidate in (
        address_jp.get("zip"),
        address_jp.get("postal_code"),
        dict(prop.disclosures or {}).get("zip_code"),
    ):
        normalized = _normalize_zip(candidate)
        if normalized:
            return normalized

    if not prop.address:
        return None
    for token in reversed(prop.address.replace(",", " ").split()):
        normalized = _normalize_zip(token)
        if normalized:
            return normalized
    return None


def _asking_price(prop: Property) -> float:
    if prop.baibai_kakaku_yen is not None:
        return float(prop.baibai_kakaku_yen)
    return float(prop.asking_price)


def _normalize_zip(value: object | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 7 and _JP_ZIP_RE.fullmatch(str(value).strip()):
        return digits
    if len(digits) == 7 and not str(value).strip():
        return None
    if len(digits) == 7:
        return digits
    if len(digits) == 5 and _US_ZIP_RE.fullmatch(digits):
        return digits
    return None


def _normalize_text(value: object | None) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return "".join(ch for ch in text if not ch.isspace() and ch not in "-,")


def _property_location(prop: Property) -> dict[str, str]:
    shozaichi = dict(dict(prop.neighborhood_data or {}).get("jp", {}).get("shozaichi") or {})
    address_jp = dict(prop.address_jp or {})
    stations = prop.nearest_stations or dict(prop.neighborhood_data or {}).get("jp", {}).get(
        "nearest_stations",
        [],
    )

    prefecture = shozaichi.get("todoufuken") or address_jp.get("prefecture")
    municipality = shozaichi.get("shikuchouson") or address_jp.get("municipality")
    neighborhood = shozaichi.get("chome") or address_jp.get("neighborhood")
    station_names = [
        str(item.get("eki") or item.get("station") or "").strip()
        for item in stations
        if isinstance(item, dict)
    ]

    return {
        "prefecture": str(prefecture or ""),
        "municipality": str(municipality or ""),
        "neighborhood": str(neighborhood or ""),
        "stations": " ".join(name for name in station_names if name),
        "address": str(prop.address or ""),
    }


def _location_matches(token: str, prop_value: object | None) -> bool:
    wanted = _normalize_text(token)
    known = _normalize_text(prop_value)
    if not wanted:
        return True
    if not known:
        return True
    return wanted in known or known in wanted


def _address_contains_token(token: str, address: object | None) -> bool:
    wanted = _normalize_text(token)
    haystack = _normalize_text(address)
    return bool(wanted and haystack and wanted in haystack)


# ── component scorers ──────────────────────────────────────────────────


def _strategy_buy_and_hold(
    prop: Property, snapshot: MarketContextSnapshot | None
) -> tuple[float, str]:
    """Reward properties whose implied gross yield supports a buy-and-hold thesis."""
    median_rent = snapshot.median_rent if snapshot else None
    asking_price = _asking_price(prop)
    if median_rent is None or asking_price <= 0:
        return 0.0, "buy_and_hold: rent benchmark unavailable"
    annual_rent = float(median_rent) * 12.0
    gross_yield = annual_rent / asking_price  # ~ 0.05–0.12 typical
    # Map 4–10% → 0–1
    score = _clip((gross_yield - 0.04) / 0.06)
    return score, f"gross yield ~{gross_yield * 100:.1f}% (rent benchmark vs ask)"


def _strategy_flip(
    prop: Property, snapshot: MarketContextSnapshot | None
) -> tuple[float, str]:
    """Reward asking price below the median sale price — the flip spread."""
    median = snapshot.median_sale_price if snapshot else None
    if median is None or median <= 0:
        return 0.0, "flip: median sale benchmark unavailable"
    spread = (float(median) - _asking_price(prop)) / float(median)
    # Map -10% to +25% spread → 0 to 1
    score = _clip((spread + 0.10) / 0.35)
    return score, f"asking is {spread * 100:+.1f}% vs neighborhood median sale"


def _strategy_lease(
    prop: Property, snapshot: MarketContextSnapshot | None
) -> tuple[float, str]:
    """Reward rent strength + healthy inventory pressure for lease ops."""
    median_rent = snapshot.median_rent if snapshot else None
    inventory = snapshot.inventory_pressure if snapshot else None
    if median_rent is None:
        return 0.0, "lease: rent benchmark unavailable"
    # Same gross-yield base as buy_and_hold...
    annual_rent = float(median_rent) * 12.0
    asking_price = _asking_price(prop)
    gross_yield = annual_rent / asking_price if asking_price > 0 else 0.0
    yield_part = _clip((gross_yield - 0.04) / 0.06)
    # ...but discount when inventory is loose (renters have options).
    inv_part = 1.0 if inventory is None else _clip(1.0 - float(inventory))
    score = (yield_part * 0.7) + (inv_part * 0.3)
    return score, (
        f"lease appeal: yield {gross_yield * 100:.1f}%, "
        f"inventory pressure {'unknown' if inventory is None else f'{inventory:.2f}'}"
    )


_STRATEGY_FN = {
    "buy_and_hold": _strategy_buy_and_hold,
    "flip": _strategy_flip,
    "lease": _strategy_lease,
}


def _score_strategy(
    profile: InvestorProfile, prop: Property, snapshot: MarketContextSnapshot | None
) -> tuple[float, str]:
    fn = _STRATEGY_FN.get(profile.strategy or _DEFAULT_STRATEGY, _strategy_buy_and_hold)
    return fn(prop, snapshot)


def _score_risk(
    profile: InvestorProfile, prop: Property, snapshot: MarketContextSnapshot | None
) -> tuple[float, str]:
    """Proximity to target cap rate using median rent / asking proxy."""
    if profile.target_cap_rate is None:
        return 0.5, "risk: no target cap rate set"
    asking_price = _asking_price(prop)
    if snapshot is None or snapshot.median_rent is None or asking_price <= 0:
        return 0.0, "risk: data unavailable"
    proxy_cap = (float(snapshot.median_rent) * 12.0 / asking_price) * 100.0
    target = float(profile.target_cap_rate)
    if target <= 0:
        return 0.5, "risk: invalid target"
    dist = abs(proxy_cap - target) / target  # relative miss
    score = _clip(1.0 - dist)
    return score, f"projected cap rate {proxy_cap:.1f}% vs {target:.1f}% target"


def _hazard_penalty(snapshot: MarketContextSnapshot | None) -> float:
    """Worst-case hazard severity. None → no penalty."""
    if snapshot is None:
        return 0.0
    flags: dict[str, Any] = dict(snapshot.hazard_flags or {})
    if not flags:
        return 0.0
    levels = {"low": 0.1, "moderate": 0.4, "high": 0.8}
    worst = 0.0
    for value in flags.values():
        worst = max(worst, levels.get(str(value).lower(), 0.0))
    return worst


def _score_signal(snapshot: MarketContextSnapshot | None) -> tuple[float, str]:
    """Composite safety + hazard score."""
    if snapshot is None:
        return 0.5, "signal: data unavailable"
    parts: list[float] = []
    notes: list[str] = []
    if snapshot.safety_score is not None:
        safety = _clip(float(snapshot.safety_score) / 100.0)
        parts.append(safety)
        notes.append(f"safety {snapshot.safety_score:.0f}/100")
    hazard = _hazard_penalty(snapshot)
    if hazard > 0:
        parts.append(_clip(1.0 - hazard))
        notes.append(f"hazard worst {hazard:.0%}")
    if not parts:
        return 0.5, "signal: data unavailable"
    score = sum(parts) / len(parts)
    return score, "signal: " + ", ".join(notes)


def _score_underwriting(
    profile: InvestorProfile,
    prop: Property,
    snapshot: MarketContextSnapshot | None,
) -> tuple[float, str]:
    """Light proxy for DSCR-style health using rent vs assumed debt service."""
    asking_price = _asking_price(prop)
    if snapshot is None or snapshot.median_rent is None or asking_price <= 0:
        return 0.5, "underwriting: data unavailable"
    # Crude monthly payment estimate at 75% LTV, 30y, 7% rate
    rate_m = 0.07 / 12.0
    n = 360
    loan = asking_price * 0.75
    monthly_payment = loan * (rate_m * (1 + rate_m) ** n) / ((1 + rate_m) ** n - 1)
    rent = float(snapshot.median_rent)
    if monthly_payment <= 0:
        return 0.5, "underwriting: payment proxy invalid"
    dscr = rent * 0.6 / monthly_payment  # NOI proxy = 60% of gross rent
    score = _clip((dscr - 0.7) / 0.55)  # 0.7→0, 1.25→1
    return score, f"proxy DSCR ~{dscr:.2f} (healthy >= 1.25)"


def _score_geography(
    profile: InvestorProfile, prop: Property
) -> tuple[float, str]:
    """Japan-aware geography matching with graceful fallback for legacy US data."""
    geo = profile.geography or {}
    if not geo:
        return 0.5, "geography: no preference set"

    prop_zip = _normalize_zip(_extract_zip(prop))
    wanted_zip = _normalize_zip(geo.get("zip"))
    if wanted_zip and prop_zip and wanted_zip == prop_zip:
        label = "郵便番号" if len(wanted_zip) == 7 else "ZIP"
        return 1.0, f"exact {label} match ({prop_zip})"

    location = _property_location(prop)
    location_checks = [
        ("station", "stations", 0.95, "最寄り駅一致"),
        ("municipality", "municipality", 0.92, "市区町村一致"),
        ("ward", "municipality", 0.92, "行政区一致"),
        ("neighborhood", "neighborhood", 0.88, "町名一致"),
        ("prefecture", "prefecture", 0.82, "都道府県一致"),
        ("city", "municipality", 0.72, "city match"),
        ("state", "prefecture", 0.72, "state match"),
    ]
    for geo_key, loc_key, score, label in location_checks:
        token = str(geo.get(geo_key) or "").strip()
        if token and _location_matches(token, location.get(loc_key)):
            return score, f"{label} ({token})"

    address = location["address"]
    for key in ("municipality", "ward", "neighborhood", "city", "state"):
        token = str(geo.get(key) or "").strip()
        if token and _normalize_text(token) in _normalize_text(address):
            return 0.65, f"address match ({token})"
    return 0.2, "geography: no direct match"


def _score_momentum(snapshot: MarketContextSnapshot | None) -> tuple[float, str]:
    """Inventory_pressure as a coarse momentum proxy.

    Lower inventory pressure → softer market → middling momentum score.
    """
    if snapshot is None or snapshot.inventory_pressure is None:
        return 0.5, "momentum: data unavailable"
    inv = float(snapshot.inventory_pressure)
    # Centered at 0.5 — extremes (0 or 1) score lower.
    distance = abs(inv - 0.5)
    score = _clip(1.0 - distance * 2)
    return score, f"inventory pressure {inv:.2f} (balanced market preferred)"


# ── orchestration ──────────────────────────────────────────────────────


def score_property(
    profile: InvestorProfile,
    prop: Property,
    snapshot: MarketContextSnapshot | None = None,
) -> ScoredProperty:
    """Compute weighted score + rationale for one property."""
    weights = _weights_for(profile.strategy)
    components: dict[str, tuple[float, str]] = {
        "strategy": _score_strategy(profile, prop, snapshot),
        "risk": _score_risk(profile, prop, snapshot),
        "signal": _score_signal(snapshot),
        "underwriting": _score_underwriting(profile, prop, snapshot),
        "geo": _score_geography(profile, prop),
        "momentum": _score_momentum(snapshot),
    }
    total = sum(weights[k] * components[k][0] for k in weights)
    return ScoredProperty(
        property_id=prop.id,
        score=round(_clip(total), 4),
        components={k: round(v[0], 4) for k, v in components.items()},
        rationale=[v[1] for v in components.values()],
        property=prop,
    )


def rank_properties(
    profile: InvestorProfile,
    candidates: list[Property],
    snapshots: dict[str, MarketContextSnapshot] | None = None,
    *,
    top_n: int = 10,
) -> list[ScoredProperty]:
    """Filter + score + sort. Stable tie-break on (-asking_price, property_id)."""
    snapshots = snapshots or {}
    scored: list[ScoredProperty] = []
    for prop in candidates:
        passed, _reason = passes_hard_filters(profile, prop)
        if not passed:
            continue
        scored.append(score_property(profile, prop, snapshots.get(prop.id)))
    scored.sort(key=lambda s: (-s.score, -_asking_price(s.property), s.property_id))
    return scored[:top_n]


__all__ = [
    "ScoredProperty",
    "passes_hard_filters",
    "rank_properties",
    "score_property",
]
