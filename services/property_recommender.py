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
    if profile.budget is not None and prop.asking_price > profile.budget * 1.05:
        return False, "over_budget"
    geo = profile.geography or {}
    if geo:
        zip_filter = (geo.get("zip") or "").strip()
        if zip_filter:
            prop_zip = _extract_zip(prop)
            if prop_zip and prop_zip != zip_filter:
                return False, "geography_zip_mismatch"
    return True, None


def _extract_zip(prop: Property) -> str | None:
    """Find a 5-digit zip in the address, since Property has no zip column."""
    if not prop.address:
        return None
    for token in reversed(prop.address.replace(",", " ").split()):
        if len(token) == 5 and token.isdigit():
            return token
    return None


# ── component scorers ──────────────────────────────────────────────────


def _strategy_buy_and_hold(
    prop: Property, snapshot: MarketContextSnapshot | None
) -> tuple[float, str]:
    """Reward properties whose implied gross yield supports a buy-and-hold thesis."""
    median_rent = snapshot.median_rent if snapshot else None
    if median_rent is None or prop.asking_price <= 0:
        return 0.0, "buy_and_hold: rent benchmark unavailable"
    annual_rent = float(median_rent) * 12.0
    gross_yield = annual_rent / prop.asking_price  # ~ 0.05–0.12 typical
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
    spread = (float(median) - prop.asking_price) / float(median)
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
    gross_yield = annual_rent / prop.asking_price if prop.asking_price > 0 else 0.0
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
    if snapshot is None or snapshot.median_rent is None or prop.asking_price <= 0:
        return 0.0, "risk: data unavailable"
    proxy_cap = (float(snapshot.median_rent) * 12.0 / prop.asking_price) * 100.0
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
    if snapshot is None or snapshot.median_rent is None or prop.asking_price <= 0:
        return 0.5, "underwriting: data unavailable"
    # Crude monthly payment estimate at 75% LTV, 30y, 7% rate
    rate_m = 0.07 / 12.0
    n = 360
    loan = prop.asking_price * 0.75
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
    """Gradient: exact zip 1.0, address-substring match 0.7, else 0.3."""
    geo = profile.geography or {}
    if not geo:
        return 0.5, "geography: no preference set"
    prop_zip = _extract_zip(prop)
    if geo.get("zip") and prop_zip and prop_zip == geo["zip"]:
        return 1.0, f"exact ZIP match ({prop_zip})"
    address = (prop.address or "").lower()
    for key in ("city", "state"):
        token = (geo.get(key) or "").strip().lower()
        if token and token in address:
            return 0.7, f"{key} match ({token})"
    return 0.3, "geography: no direct match"


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
    scored.sort(key=lambda s: (-s.score, -s.property.asking_price, s.property_id))
    return scored[:top_n]


__all__ = [
    "ScoredProperty",
    "passes_hard_filters",
    "rank_properties",
    "score_property",
]
