"""Tests for the persona analyst council scaffolding.

Focus on the pure helpers (serialize, depreciation context, score blending)
since the Claude calls are I/O-bound and tested separately at the persona
prompt level.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.analyst_council import (
    AnalystVerdict,
    _blend_overall_score,
    _build_depreciation_context,
    _extract_persona_score,
    _serialize_listing,
    review_listing,
)
from db.models import AssetTier, ConstructionType, Property, SeismicCode


def _make_aparuto() -> Property:
    p = Property()
    p.id = "p-aparuto-1"
    p.address = "東京都江戸川区..."
    p.baibai_kakaku_yen = 45_000_000
    p.asking_price = 45_000_000.0
    p.asset_tier = AssetTier.APARUTO
    p.construction_type = ConstructionType.WOOD
    p.seismic_code = SeismicCode.SHIN_TAISHIN
    p.re_buildable = 1
    p.road_frontage_m = 4.2
    p.ward_code = "13123"
    p.walk_minutes_to_station = 8
    p.nearest_stations = [{"line": "JR総武線", "station": "新小岩", "walk_minutes": 8}]
    p.built_year = 2010
    p.menseki_m2 = 180.0
    p.youto_chiiki = "第一種住居地域"
    p.kenpei_ritsu = 60
    p.youseki_ritsu = 200
    p.kanrihi_yen = 0
    p.shuuzenzumitatekin_yen = 0
    p.assumed_monthly_rent_yen = 320_000
    p.occupancy_rate = 0.95
    p.hazard_flags = {}
    p.listed_at = datetime.utcnow()
    return p


class TestSerializeListing:
    def test_prefers_yen_over_float(self):
        p = _make_aparuto()
        out = _serialize_listing(p)
        assert out["asking_price_yen"] == 45_000_000
        assert out["asset_tier"] == "aparuto"
        assert out["construction_type"] == "wood"
        assert out["seismic_code"] == "shin_taishin"

    def test_handles_missing_jp_fields(self):
        p = Property()
        p.id = "p-bare"
        p.address = "..."
        p.baibai_kakaku_yen = None
        p.asking_price = 1_000_000.0
        out = _serialize_listing(p)
        assert out["asking_price_yen"] == 1_000_000
        assert out["asset_tier"] is None
        assert out["construction_type"] is None


class TestDepreciationContext:
    def test_unavailable_when_construction_missing(self):
        p = Property()
        p.construction_type = None
        ctx = _build_depreciation_context(
            p, building_basis_yen=10_000_000, building_age_years=5, marginal_tax_rate=0.33
        )
        assert ctx == {"available": False, "reason": "missing construction_type or basis or age"}

    def test_unavailable_when_basis_missing(self):
        p = _make_aparuto()
        ctx = _build_depreciation_context(
            p, building_basis_yen=None, building_age_years=15, marginal_tax_rate=0.33
        )
        assert ctx["available"] is False

    def test_computes_aparuto_schedule(self):
        p = _make_aparuto()
        # 15-year-old wood, 25M building basis, 33% rate
        ctx = _build_depreciation_context(
            p, building_basis_yen=25_000_000, building_age_years=15, marginal_tax_rate=0.33
        )
        assert ctx["available"] is True
        # (22-15) + 15*0.20 = 10 years residual
        assert ctx["residual_life_years"] == 10
        assert ctx["shield_expires_year"] == 10
        # annual dep = 25M / 10 = 2.5M; shield = 0.33 × 2.5M × 10 = 8.25M
        assert ctx["total_shield_yen"] == pytest.approx(0.33 * 25_000_000)


class TestScoreBlending:
    def _verdict(self, key: str, payload: dict, error: str | None = None) -> AnalystVerdict:
        return AnalystVerdict(persona_key=key, persona_title_ja=key, payload=payload, error=error)

    def test_extract_risk_score(self):
        v = self._verdict("risk_finder", {"score": 72})
        assert _extract_persona_score(v) == 72.0

    def test_extract_vacancy_score_scales_to_100(self):
        v = self._verdict("vacancy_demand", {"occupancy_forecast": 0.93})
        assert _extract_persona_score(v) == pytest.approx(93.0)

    def test_extract_depreciation_thesis_maps_to_score(self):
        v = self._verdict("depreciation_strategist", {"thesis": "aparuto_shield"})
        assert _extract_persona_score(v) == 75

    def test_blend_weighted_average(self):
        verdicts = (
            self._verdict("risk_finder", {"score": 80}),               # weight 0.40
            self._verdict("location_advantage", {"score": 70}),         # weight 0.30
            self._verdict("vacancy_demand", {"occupancy_forecast": 0.90}),  # weight 0.20 → 90
            self._verdict("depreciation_strategist", {"thesis": "aparuto_shield"}),  # weight 0.10 → 75
        )
        # (80*0.4 + 70*0.3 + 90*0.2 + 75*0.1) / 1.0 = 32 + 21 + 18 + 7.5 = 78.5
        assert _blend_overall_score(verdicts) == pytest.approx(78.5)

    def test_blend_skips_errored_personas(self):
        verdicts = (
            self._verdict("risk_finder", {}, error="api_error"),
            self._verdict("location_advantage", {"score": 60}),
        )
        # Only location counts: 60
        assert _blend_overall_score(verdicts) == 60.0

    def test_blend_returns_zero_when_all_failed(self):
        verdicts = (
            self._verdict("risk_finder", {}, error="x"),
            self._verdict("location_advantage", {}, error="y"),
        )
        assert _blend_overall_score(verdicts) == 0.0


class TestReviewListing:
    @pytest.mark.asyncio
    async def test_review_runs_all_personas_in_parallel(self):
        p = _make_aparuto()

        # Mock Claude returning a valid JSON payload for any persona
        mock_message = MagicMock()
        mock_message.content = [MagicMock(type="text", text='{"score": 70, "summary": "ok"}')]
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(return_value=mock_message)

        result = await review_listing(
            p,
            client=client,
            building_basis_yen=25_000_000,
            building_age_years=15,
            marginal_tax_rate=0.33,
        )

        assert result.listing_id == "p-aparuto-1"
        assert len(result.verdicts) == 4
        assert client.messages.create.call_count == 4
        assert all(v.error is None for v in result.verdicts)
