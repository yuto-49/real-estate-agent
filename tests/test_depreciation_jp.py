"""Tests for the JP statutory depreciation engine."""

import pytest

from db.models import ConstructionType
from intelligence.depreciation_jp import (
    project_depreciation,
    residual_life_used,
    statutory_life,
)


class TestStatutoryLife:
    def test_wood_is_22_years(self):
        assert statutory_life(ConstructionType.WOOD) == 22

    def test_rc_is_47_years(self):
        assert statutory_life(ConstructionType.RC) == 47

    def test_light_steel_is_27_years(self):
        assert statutory_life(ConstructionType.LIGHT_STEEL) == 27


class TestResidualLifeUsed:
    def test_new_building_keeps_full_life(self):
        assert residual_life_used(ConstructionType.WOOD, 0) == 22

    def test_fully_depreciated_wood_floors_at_4(self):
        # 22 × 0.20 = 4.4 → 4
        assert residual_life_used(ConstructionType.WOOD, 30) == 4

    def test_15_year_old_wood_simplified_rule(self):
        # (22 - 15) + 15 × 0.20 = 7 + 3 = 10
        assert residual_life_used(ConstructionType.WOOD, 15) == 10

    def test_floor_at_2_years(self):
        # If statute × 0.20 < 2, we floor at 2
        # Steel × 0.20 = 6.8, so this is irrelevant for steel
        # The floor protects against e.g. very low custom statutes
        assert residual_life_used(ConstructionType.WOOD, 999) >= 2

    def test_negative_age_rejected(self):
        with pytest.raises(ValueError):
            residual_life_used(ConstructionType.WOOD, -1)


class TestProjectDepreciation:
    def test_aparuto_thesis_shape(self):
        # 30M yen building basis, 10-year-old 木造, 45% bracket
        # residual = (22 - 10) + 10 × 0.20 = 12 + 2 = 14 years
        # annual dep = 30M / 14 ≈ 2,142,857
        # annual shield = dep × 0.45 ≈ 964,286
        schedule = project_depreciation(
            construction=ConstructionType.WOOD,
            building_basis_yen=30_000_000,
            building_age_years=10,
            marginal_tax_rate=0.45,
        )
        assert schedule.residual_life_years == 14
        assert schedule.annual_depreciation_yen == pytest.approx(30_000_000 / 14)
        assert len(schedule.years) == 14
        assert schedule.years[0].tax_shield_yen == pytest.approx(
            (30_000_000 / 14) * 0.45
        )

    def test_horizon_beyond_residual_pads_with_zeros(self):
        schedule = project_depreciation(
            construction=ConstructionType.WOOD,
            building_basis_yen=10_000_000,
            building_age_years=20,
            marginal_tax_rate=0.30,
            horizon_years=10,
        )
        # residual = (22-20) + 20×0.20 = 2 + 4 = 6
        assert schedule.residual_life_years == 6
        assert len(schedule.years) == 10
        # Years 1-6 have shield, years 7-10 are zero
        assert all(y.depreciation_yen > 0 for y in schedule.years[:6])
        assert all(y.depreciation_yen == 0 for y in schedule.years[6:])

    def test_cumulative_shield_is_monotonic(self):
        schedule = project_depreciation(
            construction=ConstructionType.RC,
            building_basis_yen=80_000_000,
            building_age_years=15,
            marginal_tax_rate=0.33,
        )
        cumulatives = [y.cumulative_shield_yen for y in schedule.years]
        assert cumulatives == sorted(cumulatives)

    def test_rejects_negative_basis(self):
        with pytest.raises(ValueError):
            project_depreciation(
                construction=ConstructionType.WOOD,
                building_basis_yen=-1,
                building_age_years=0,
                marginal_tax_rate=0.30,
            )

    def test_rejects_invalid_tax_rate(self):
        with pytest.raises(ValueError):
            project_depreciation(
                construction=ConstructionType.WOOD,
                building_basis_yen=1_000_000,
                building_age_years=0,
                marginal_tax_rate=1.5,
            )
