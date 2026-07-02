"""Tier 1 MVP integration tests — satei, price probability, negotiation coach.

Tests all three features with 5 diverse Tokyo property datasets:
1. One-room Shinjuku studio (small, high walk premium)
2. Aparuto Itabashi wood (depreciation play, older)
3. Family mansion Setagaya RC (mid-range family)
4. Old Adachi building (cheap, old, risky)
5. Luxury Minato tower (high-end, RC, station-close)
"""

from __future__ import annotations

import pytest

from services.satei_engine import (
    SateiResult,
    _compute_adjustments,
)
from services.price_probability import (
    PriceProbabilityCurve,
    compute_price_probability_curve,
)
from services.negotiation_coach import (
    ClientProfile,
    CounterpartyProfile,
    CoachingResult,
    run_coaching_session,
)


# ── Test Datasets ────────────────────────────────────────────────────────

DATASETS = {
    "oneroom_shinjuku": {
        "label": "One-room Shinjuku studio",
        "satei_price": 28_000_000,
        "menseki_m2": 22.0,
        "built_year": 2015,
        "construction_type": "RC",
        "walk_minutes": 4,
        "city_code": "13104",
    },
    "aparuto_itabashi": {
        "label": "Aparuto Itabashi wood 8-unit",
        "satei_price": 45_000_000,
        "menseki_m2": 120.0,
        "built_year": 1998,
        "construction_type": "木造",
        "walk_minutes": 8,
        "city_code": "13119",
    },
    "family_setagaya": {
        "label": "Family mansion Setagaya RC 3LDK",
        "satei_price": 62_000_000,
        "menseki_m2": 72.0,
        "built_year": 2008,
        "construction_type": "RC",
        "walk_minutes": 10,
        "city_code": "13112",
    },
    "old_adachi": {
        "label": "Old Adachi building",
        "satei_price": 15_000_000,
        "menseki_m2": 55.0,
        "built_year": 1985,
        "construction_type": "軽量鉄骨",
        "walk_minutes": 14,
        "city_code": "13121",
    },
    "luxury_minato": {
        "label": "Luxury Minato tower",
        "satei_price": 150_000_000,
        "menseki_m2": 95.0,
        "built_year": 2020,
        "construction_type": "SRC",
        "walk_minutes": 2,
        "city_code": "13103",
    },
}


# ── Price Probability Tests ──────────────────────────────────────────────


class TestPriceProbabilityCurve:
    """Test the Monte Carlo price-vs-probability engine with all 5 datasets."""

    @pytest.mark.parametrize("key", DATASETS.keys())
    def test_curve_produces_points(self, key: str) -> None:
        ds = DATASETS[key]
        curve = compute_price_probability_curve(
            satei_price_yen=ds["satei_price"],
            iterations=50,
            seed=42,
        )
        assert isinstance(curve, PriceProbabilityCurve)
        assert len(curve.points) > 0
        assert curve.satei_price_yen == ds["satei_price"]

    @pytest.mark.parametrize("key", DATASETS.keys())
    def test_probabilities_decrease_with_higher_price(self, key: str) -> None:
        ds = DATASETS[key]
        curve = compute_price_probability_curve(
            satei_price_yen=ds["satei_price"],
            iterations=100,
            seed=42,
        )
        assert curve.points[0].p90 >= curve.points[-1].p90

    @pytest.mark.parametrize("key", DATASETS.keys())
    def test_p30_leq_p60_leq_p90_leq_p180(self, key: str) -> None:
        ds = DATASETS[key]
        curve = compute_price_probability_curve(
            satei_price_yen=ds["satei_price"],
            iterations=100,
            seed=42,
        )
        for pt in curve.points:
            assert pt.p30 <= pt.p60 + 0.01
            assert pt.p60 <= pt.p90 + 0.01
            assert pt.p90 <= pt.p180 + 0.01

    @pytest.mark.parametrize("key", DATASETS.keys())
    def test_expected_days_increases_with_premium(self, key: str) -> None:
        ds = DATASETS[key]
        curve = compute_price_probability_curve(
            satei_price_yen=ds["satei_price"],
            iterations=100,
            seed=42,
        )
        assert curve.points[-1].expected_days >= curve.points[0].expected_days

    def test_below_market_sells_fast(self) -> None:
        curve = compute_price_probability_curve(
            satei_price_yen=50_000_000,
            range_low_pct=-10.0,
            range_high_pct=0.0,
            step_pct=5.0,
            iterations=200,
            seed=42,
        )
        # -10% discount → median ~42 days in Tokyo; most close within 60 days
        assert curve.points[0].p30 > 0
        assert curve.points[0].p60 > 0.9

    def test_high_premium_struggles(self) -> None:
        curve = compute_price_probability_curve(
            satei_price_yen=50_000_000,
            range_low_pct=15.0,
            range_high_pct=20.0,
            step_pct=5.0,
            iterations=200,
            seed=42,
        )
        assert curve.points[-1].p30 < 0.2


# ── Negotiation Coach Tests ──────────────────────────────────────────────


class TestNegotiationCoach:
    """Test the coaching engine with all 5 datasets."""

    @pytest.mark.parametrize("key", DATASETS.keys())
    def test_coaching_produces_result(self, key: str) -> None:
        ds = DATASETS[key]
        result = run_coaching_session(
            asking_price_yen=ds["satei_price"],
            client=ClientProfile(
                role="seller",
                reservation_price_yen=int(ds["satei_price"] * 0.90),
            ),
            property_address=ds["label"],
            seed=42,
        )
        assert isinstance(result, CoachingResult)
        assert result.client_role == "seller"
        assert len(result.scenarios) == 3
        assert result.walk_away_yen == int(ds["satei_price"] * 0.90)

    @pytest.mark.parametrize("key", DATASETS.keys())
    def test_concession_ladder_descends_for_seller(self, key: str) -> None:
        ds = DATASETS[key]
        result = run_coaching_session(
            asking_price_yen=ds["satei_price"],
            client=ClientProfile(
                role="seller",
                reservation_price_yen=int(ds["satei_price"] * 0.85),
            ),
            seed=42,
        )
        ladder = result.concession_ladder
        assert len(ladder) >= 3
        assert ladder[0] >= ladder[-1]

    @pytest.mark.parametrize("key", DATASETS.keys())
    def test_buyer_coaching(self, key: str) -> None:
        ds = DATASETS[key]
        result = run_coaching_session(
            asking_price_yen=ds["satei_price"],
            client=ClientProfile(
                role="buyer",
                reservation_price_yen=int(ds["satei_price"] * 1.05),
            ),
            seed=42,
        )
        assert result.client_role == "buyer"
        ladder = result.concession_ladder
        assert ladder[0] <= ladder[-1]

    def test_urgent_client_gets_coaching_note(self) -> None:
        result = run_coaching_session(
            asking_price_yen=50_000_000,
            client=ClientProfile(
                role="seller",
                reservation_price_yen=45_000_000,
                motivation="urgent",
            ),
            seed=42,
        )
        assert any("motivated" in n.lower() or "concession" in n.lower()
                    for n in result.coaching_notes)

    def test_narrow_spread_warning(self) -> None:
        result = run_coaching_session(
            asking_price_yen=50_000_000,
            client=ClientProfile(
                role="seller",
                reservation_price_yen=49_500_000,
            ),
            seed=42,
        )
        assert any("narrow" in n.lower() or "limited" in n.lower()
                    for n in result.coaching_notes)

    def test_zopa_analysis_present(self) -> None:
        result = run_coaching_session(
            asking_price_yen=60_000_000,
            client=ClientProfile(
                role="seller",
                reservation_price_yen=54_000_000,
            ),
            seed=42,
        )
        assert len(result.zopa_analysis) > 0


# ── Satei Adjustment Unit Tests (no DB) ──────────────────────────────────


class TestSateiAdjustments:
    """Test the hedonic adjustment computation (pure function, no DB)."""

    def test_newer_comp_adjusts_negative(self) -> None:
        from unittest.mock import MagicMock
        comp = MagicMock()
        comp.built_year = 2020
        comp.menseki_m2 = 60.0
        comp.walk_minutes = 5
        comp.construction_type = "RC"

        details, total = _compute_adjustments(
            comp, 60.0, 2010, "RC", 5, {},
        )
        age_adj = next(d for d in details if d.factor_name == "age")
        assert age_adj.adjustment_pct < 0

    def test_farther_walk_adjusts_negative(self) -> None:
        from unittest.mock import MagicMock
        comp = MagicMock()
        comp.built_year = 2010
        comp.menseki_m2 = 60.0
        comp.walk_minutes = 12
        comp.construction_type = "RC"

        details, total = _compute_adjustments(
            comp, 60.0, 2010, "RC", 5, {},
        )
        walk_adj = next(d for d in details if d.factor_name == "walk")
        assert walk_adj.adjustment_pct < 0

    def test_overrides_replace_computed(self) -> None:
        from unittest.mock import MagicMock
        comp = MagicMock()
        comp.built_year = 2020
        comp.menseki_m2 = 60.0
        comp.walk_minutes = 5
        comp.construction_type = "RC"

        details, total = _compute_adjustments(
            comp, 60.0, 2010, "RC", 5, {"age": 10.0},
        )
        age_adj = next(d for d in details if d.factor_name == "age")
        assert age_adj.adjustment_pct == 10.0

    def test_construction_type_premium(self) -> None:
        from unittest.mock import MagicMock
        comp = MagicMock()
        comp.built_year = 2010
        comp.menseki_m2 = 60.0
        comp.walk_minutes = 5
        comp.construction_type = "SRC"

        details, total = _compute_adjustments(
            comp, 60.0, 2010, "木造", 5, {},
        )
        const_adj = next(d for d in details if d.factor_name == "construction")
        assert const_adj.adjustment_pct == 7.0


# ── Cross-Dataset Broker Insight Tests ───────────────────────────────────


class TestBrokerInsights:
    """Outputs should differentiate meaningfully across property types."""

    def test_price_curves_scale_with_property_value(self) -> None:
        curves = {}
        for key, ds in DATASETS.items():
            curves[key] = compute_price_probability_curve(
                satei_price_yen=ds["satei_price"],
                iterations=50,
                seed=42,
            )
        settlements = {
            k: c.points[len(c.points) // 2].expected_settlement_yen
            for k, c in curves.items()
        }
        assert settlements["luxury_minato"] > settlements["old_adachi"]

    def test_coaching_ladder_scales_with_price(self) -> None:
        results = {}
        for key, ds in DATASETS.items():
            results[key] = run_coaching_session(
                asking_price_yen=ds["satei_price"],
                client=ClientProfile(
                    role="seller",
                    reservation_price_yen=int(ds["satei_price"] * 0.90),
                ),
                seed=42,
            )
        lux = results["luxury_minato"].concession_ladder
        ada = results["old_adachi"].concession_ladder
        lux_step = lux[0] - lux[1] if len(lux) > 1 else 0
        ada_step = ada[0] - ada[1] if len(ada) > 1 else 0
        assert lux_step > ada_step

    def test_all_datasets_produce_settled_scenarios(self) -> None:
        for key, ds in DATASETS.items():
            result = run_coaching_session(
                asking_price_yen=ds["satei_price"],
                client=ClientProfile(
                    role="seller",
                    reservation_price_yen=int(ds["satei_price"] * 0.85),
                ),
                num_scenarios=3,
                max_rounds=10,
                seed=42,
            )
            settled = [s for s in result.scenarios if s.settled]
            assert len(settled) >= 1, f"{ds['label']}: no scenarios settled"
