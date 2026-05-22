"""Unit tests for the deterministic property recommender — Phase P4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from db.models import InvestorProfile, Property, PropertyStatus
from domain.market.models import MarketContextSnapshot
from services.property_recommender import (
    passes_hard_filters,
    rank_properties,
    score_property,
)


def _profile(**overrides: Any) -> InvestorProfile:
    defaults: dict[str, Any] = {
        "id": "p1",
        "user_id": "u1",
        "budget": 500_000,
        "strategy": "buy_and_hold",
        "target_cap_rate": 7.0,
        "target_coc": 8.0,
        "geography": {"zip": "60601"},
        "notes": None,
    }
    defaults.update(overrides)
    p = InvestorProfile()
    for k, v in defaults.items():
        setattr(p, k, v)
    return p


def _property(**overrides: Any) -> Property:
    defaults: dict[str, Any] = {
        "id": "prop-1",
        "address": "123 Main St 60601",
        "asking_price": 350_000.0,
        "property_type": "sfr",
        "bedrooms": 3,
        "bathrooms": 2.0,
        "sqft": 1400,
        "status": PropertyStatus.ACTIVE,
        "neighborhood_data": {},
    }
    defaults.update(overrides)
    p = Property()
    for k, v in defaults.items():
        setattr(p, k, v)
    return p


def _snapshot(**overrides: Any) -> MarketContextSnapshot:
    defaults: dict[str, Any] = {
        "property_id": "prop-1",
        "zip_code": "60601",
        "safety_score": 70.0,
        "median_rent": 2_400.0,
        "median_sale_price": 400_000.0,
        "inventory_pressure": 0.5,
        "hazard_flags": {},
    }
    defaults.update(overrides)
    return MarketContextSnapshot(**defaults)


def test_score_is_deterministic_for_identical_inputs():
    profile = _profile()
    prop = _property()
    snap = _snapshot()
    s1 = score_property(profile, prop, snap)
    s2 = score_property(profile, prop, snap)
    assert s1.score == s2.score
    assert s1.components == s2.components
    assert s1.rationale == s2.rationale


def test_score_in_unit_range():
    profile = _profile()
    prop = _property()
    snap = _snapshot()
    result = score_property(profile, prop, snap)
    assert 0.0 <= result.score <= 1.0
    for comp_score in result.components.values():
        assert 0.0 <= comp_score <= 1.0


def test_missing_snapshot_degrades_gracefully():
    profile = _profile()
    prop = _property()
    result = score_property(profile, prop, snapshot=None)
    # No raise, score still in range, rationale strings non-empty
    assert 0.0 <= result.score <= 1.0
    assert all(isinstance(line, str) and line for line in result.rationale)
    # Strategy + risk + underwriting all see no snapshot → low-data outputs
    assert "unavailable" in " ".join(result.rationale)


def test_hard_filter_rejects_over_budget():
    profile = _profile(budget=200_000)
    prop = _property(asking_price=400_000)
    passed, reason = passes_hard_filters(profile, prop)
    assert passed is False
    assert reason == "over_budget"


def test_hard_filter_allows_within_5pct_slack():
    profile = _profile(budget=400_000)
    prop = _property(asking_price=410_000)  # 2.5% over
    passed, _ = passes_hard_filters(profile, prop)
    assert passed is True


def test_hard_filter_rejects_zip_mismatch():
    profile = _profile(geography={"zip": "60601"})
    prop = _property(address="789 Lakeview Dr 60615")
    passed, reason = passes_hard_filters(profile, prop)
    assert passed is False
    assert reason == "geography_zip_mismatch"


def test_flip_strategy_rewards_below_median_asking():
    """A flip-strategy investor should rank a discounted property higher
    than the same property priced at the neighborhood median."""
    profile_flip = _profile(strategy="flip")
    discounted = _property(asking_price=300_000)  # 25% below 400k median
    at_median = _property(id="prop-2", asking_price=400_000)
    snap = _snapshot()

    s_disc = score_property(profile_flip, discounted, snap)
    s_med = score_property(profile_flip, at_median, snap)

    assert s_disc.components["strategy"] > s_med.components["strategy"]


def test_geography_exact_zip_beats_no_match():
    profile = _profile(geography={"zip": "60601"})
    prop_match = _property(address="55 Pier Pl 60601")
    prop_other = _property(id="prop-2", address="55 Pier Pl 99999")
    # Disable hard zip filter for this test by clearing zip preference for one
    s_match = score_property(profile, prop_match, _snapshot())
    s_other = score_property(_profile(geography={}), prop_other, _snapshot())
    assert s_match.components["geo"] > s_other.components["geo"]


def test_rank_filters_and_orders():
    profile = _profile(budget=500_000)
    props = [
        _property(id="cheap", asking_price=200_000, address="A 60601"),
        _property(id="overpriced", asking_price=600_000, address="B 60601"),
        _property(id="mid", asking_price=400_000, address="C 60601"),
    ]
    snapshots = {p.id: _snapshot(property_id=p.id) for p in props}
    ranked = rank_properties(profile, props, snapshots=snapshots, top_n=10)
    # Overpriced is dropped by the hard filter
    ids = [r.property_id for r in ranked]
    assert "overpriced" not in ids
    # Output is sorted descending by score
    for i in range(len(ranked) - 1):
        assert ranked[i].score >= ranked[i + 1].score


def test_rank_respects_top_n():
    profile = _profile()
    props = [_property(id=f"p{i}", address=f"{i} St 60601") for i in range(20)]
    ranked = rank_properties(profile, props, snapshots={}, top_n=5)
    assert len(ranked) == 5


def test_strategy_weights_change_ordering():
    """Same property gets different scores under flip vs buy_and_hold weights."""
    prop = _property(asking_price=300_000)
    snap = _snapshot()
    s_hold = score_property(_profile(strategy="buy_and_hold"), prop, snap)
    s_flip = score_property(_profile(strategy="flip"), prop, snap)
    # Different weightings → different totals (almost always, given different components)
    assert s_hold.score != s_flip.score


def test_unknown_strategy_falls_back_to_buy_and_hold():
    profile = _profile(strategy="unknown_strategy_xyz")
    prop = _property()
    snap = _snapshot()
    fallback = score_property(profile, prop, snap)
    canonical = score_property(_profile(strategy="buy_and_hold"), prop, snap)
    assert pytest.approx(fallback.score) == canonical.score
