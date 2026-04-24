"""Tests for Japanese regulatory guardrails (Phase 2).

Covers:
- 重要事項説明書 (juuyou jikou setsumeisho) required disclosures per 宅建業法35条
- Brokerage fee ceiling per 宅建業法46条 (3% + 6万円 for > 4M yen)
- 旧耐震 (pre-1981/6) loan risk warning
- JPY offer validation using MoneyJPY
- Jurisdiction-aware dispatch (us → guardrails.py, jp_tokyo → guardrails_jp.py)
"""

import pytest

from services.money_jp import MoneyJPY


# ---------------------------------------------------------------------------
# Import the module under test — these will fail until guardrails_jp.py exists
# ---------------------------------------------------------------------------
from agent.guardrails_jp import (
    REQUIRED_JUUYOU_JIKOU,
    validate_juuyou_jikou,
    calc_brokerage_fee_ceiling,
    check_kyuutaishin_risk,
    validate_offer_jp,
    validate_disclosures_jp,
    GuardrailResult,
)
from agent.guardrails_dispatch import dispatch_validate_offer, dispatch_validate_disclosures


# ── 重要事項説明書 disclosure validation ──────────────────────────────────────


class TestJuuyouJikouValidation:
    """Tests for 宅建業法35条 required disclosures."""

    def test_all_present_passes(self):
        disclosures = {key: "noted" for key in REQUIRED_JUUYOU_JIKOU}
        result = validate_juuyou_jikou(disclosures)
        assert result.passed is True

    def test_missing_single_key_fails(self):
        disclosures = {key: "noted" for key in REQUIRED_JUUYOU_JIKOU}
        del disclosures[REQUIRED_JUUYOU_JIKOU[0]]
        result = validate_juuyou_jikou(disclosures)
        assert result.passed is False
        assert REQUIRED_JUUYOU_JIKOU[0] in result.reason

    def test_empty_disclosures_fails(self):
        result = validate_juuyou_jikou({})
        assert result.passed is False

    def test_extra_keys_still_pass(self):
        disclosures = {key: "noted" for key in REQUIRED_JUUYOU_JIKOU}
        disclosures["extra_field"] = "extra"
        result = validate_juuyou_jikou(disclosures)
        assert result.passed is True

    def test_required_list_is_nonempty(self):
        assert len(REQUIRED_JUUYOU_JIKOU) >= 5


# ── Brokerage fee ceiling (宅建業法46条) ────────────────────────────────────


class TestBrokerageFeeCeiling:
    """Brokerage fee schedule:
      <= 2,000,000 yen: 5% + tax
      <= 4,000,000 yen: 4% + 20,000 + tax
      >  4,000,000 yen: 3% + 60,000 + tax
    Tax rate = 10% (消費税)
    """

    @pytest.mark.parametrize("price_yen,expected_ceiling", [
        # 5,000万円 → 3% + 6万 = 156万 → ×1.10 = 171.6万 = 1,716,000
        (50_000_000, 1_716_000),
        # 3,000万円 → 3% + 6万 = 96万 → ×1.10 = 1,056,000
        (30_000_000, 1_056_000),
        # 3,000,000 (300万) → 4% + 2万 = 14万 → ×1.10 = 154,000
        (3_000_000, 154_000),
        # 1,500,000 (150万) → 5% = 75,000 → ×1.10 = 82,500
        (1_500_000, 82_500),
        # Exact boundary: 4,000,000 → 4% + 2万 = 18万 → ×1.10 = 198,000
        (4_000_000, 198_000),
        # Exact boundary: 2,000,000 → 5% = 100,000 → ×1.10 = 110,000
        (2_000_000, 110_000),
    ])
    def test_fee_schedule(self, price_yen: int, expected_ceiling: int):
        ceiling = calc_brokerage_fee_ceiling(MoneyJPY(price_yen))
        assert ceiling.amount == expected_ceiling

    def test_returns_money_jpy(self):
        ceiling = calc_brokerage_fee_ceiling(MoneyJPY(50_000_000))
        assert isinstance(ceiling, MoneyJPY)

    def test_zero_price_returns_zero(self):
        ceiling = calc_brokerage_fee_ceiling(MoneyJPY(0))
        assert ceiling.amount == 0


# ── 旧耐震 (pre-1981/6) loan risk ──────────────────────────────────────────


class TestKyuutaishinRisk:
    """Buildings completed before June 1981 are 旧耐震基準 and many banks
    apply stricter lending conditions or refuse loans entirely."""

    def test_pre_1981_flagged(self):
        result = check_kyuutaishin_risk(built_year=1979)
        assert result.passed is False
        assert "旧耐震" in result.reason or "kyuutaishin" in result.reason.lower()

    def test_1981_flagged(self):
        # June 1981 is the cutoff; buildings completed in 1981 may be either.
        # Conservative: flag 1981 as risky (built_year alone can't distinguish month).
        result = check_kyuutaishin_risk(built_year=1981)
        assert result.passed is False

    def test_1982_passes(self):
        result = check_kyuutaishin_risk(built_year=1982)
        assert result.passed is True

    def test_modern_passes(self):
        result = check_kyuutaishin_risk(built_year=2020)
        assert result.passed is True

    def test_none_built_year_warns(self):
        result = check_kyuutaishin_risk(built_year=None)
        assert result.passed is False
        assert "unknown" in result.reason.lower() or "不明" in result.reason


# ── JPY offer validation ───────────────────────────────────────────────────


class TestValidateOfferJP:
    """Offer validation for jp_tokyo jurisdiction using MoneyJPY."""

    def test_valid_offer_passes(self):
        result = validate_offer_jp(
            offer_price=MoneyJPY(48_000_000),
            asking_price=MoneyJPY(50_000_000),
            buyer_budget=MoneyJPY(60_000_000),
        )
        assert result.passed is True

    def test_over_budget_fails(self):
        result = validate_offer_jp(
            offer_price=MoneyJPY(70_000_000),
            asking_price=MoneyJPY(50_000_000),
            buyer_budget=MoneyJPY(60_000_000),
        )
        assert result.passed is False
        assert "budget" in result.reason.lower() or "予算" in result.reason

    def test_lowball_fails(self):
        result = validate_offer_jp(
            offer_price=MoneyJPY(20_000_000),
            asking_price=MoneyJPY(50_000_000),
            buyer_budget=MoneyJPY(60_000_000),
        )
        assert result.passed is False
        assert "50%" in result.reason or "低" in result.reason

    def test_exact_50_percent_passes(self):
        result = validate_offer_jp(
            offer_price=MoneyJPY(25_000_000),
            asking_price=MoneyJPY(50_000_000),
            buyer_budget=MoneyJPY(60_000_000),
        )
        assert result.passed is True


# ── JP disclosure validation ───────────────────────────────────────────────


class TestValidateDisclosuresJP:
    """validate_disclosures_jp wraps juuyou jikou + adds property-level checks."""

    def test_valid_disclosures_pass(self):
        disclosures = {key: "noted" for key in REQUIRED_JUUYOU_JIKOU}
        result = validate_disclosures_jp(disclosures)
        assert result.passed is True

    def test_missing_key_fails(self):
        disclosures = {key: "noted" for key in REQUIRED_JUUYOU_JIKOU}
        del disclosures[REQUIRED_JUUYOU_JIKOU[-1]]
        result = validate_disclosures_jp(disclosures)
        assert result.passed is False


# ── Jurisdiction dispatch ──────────────────────────────────────────────────


class TestJurisdictionDispatch:
    """dispatch_validate_offer and dispatch_validate_disclosures route
    based on settings.jurisdiction."""

    def test_us_offer_dispatch(self, monkeypatch):
        monkeypatch.setattr("agent.guardrails_dispatch.settings.jurisdiction", "us")
        result = dispatch_validate_offer(
            offer_price=400_000.0, asking_price=500_000.0, buyer_budget=600_000.0
        )
        assert isinstance(result.passed, bool)

    def test_jp_offer_dispatch(self, monkeypatch):
        monkeypatch.setattr("agent.guardrails_dispatch.settings.jurisdiction", "jp_tokyo")
        result = dispatch_validate_offer(
            offer_price=48_000_000, asking_price=50_000_000, buyer_budget=60_000_000
        )
        assert isinstance(result.passed, bool)

    def test_us_disclosures_dispatch(self, monkeypatch):
        monkeypatch.setattr("agent.guardrails_dispatch.settings.jurisdiction", "us")
        from agent.guardrails import REQUIRED_DISCLOSURES
        disclosures = {key: "yes" for key in REQUIRED_DISCLOSURES}
        result = dispatch_validate_disclosures(disclosures)
        assert result.passed is True

    def test_jp_disclosures_dispatch(self, monkeypatch):
        monkeypatch.setattr("agent.guardrails_dispatch.settings.jurisdiction", "jp_tokyo")
        disclosures = {key: "noted" for key in REQUIRED_JUUYOU_JIKOU}
        result = dispatch_validate_disclosures(disclosures)
        assert result.passed is True
