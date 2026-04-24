"""Japanese regulatory guardrails — Tokyo jurisdiction.

Hard-coded rules that CANNOT be overridden by the LLM, same as
agent/guardrails.py but for jp_tokyo jurisdiction.

Key regulations:
- 宅建業法35条: 重要事項説明書 (juuyou jikou setsumeisho) required disclosures
- 宅建業法46条: Brokerage fee ceiling schedule
- 旧耐震基準: Pre-June-1981 earthquake resistance standard → loan risk
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from config import settings
from services.money_jp import MoneyJPY


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    passed: bool
    reason: str


# ── 重要事項説明書 required items (宅建業法35条) ─────────────────────────────
# These are the minimum disclosure keys a JP listing must carry.

REQUIRED_JUUYOU_JIKOU: Final[list[str]] = [
    "youto_chiiki",          # 用途地域 (zoning designation)
    "kenpei_ritsu",          # 建ぺい率 (building coverage ratio)
    "youseki_ritsu",         # 容積率 (floor-area ratio)
    "setback",               # セットバック (road setback requirements)
    "saigai_kiken",          # 災害危険区域 (disaster risk zone)
    "kyuukyuu_setsubi",      # 給排水設備 (water supply/drainage)
    "taishin_kijun",         # 耐震基準 (earthquake resistance standard)
    "flood_zone",            # 洪水ハザードマップ対象
    "dojo_osen",             # 土壌汚染 (soil contamination)
    "asbesto",               # アスベスト調査
]


def validate_juuyou_jikou(disclosures: dict) -> GuardrailResult:
    """Ensure all 重要事項説明書 items are present."""
    missing = [k for k in REQUIRED_JUUYOU_JIKOU if k not in disclosures]
    if missing:
        return GuardrailResult(False, f"重要事項説明書 欠落項目: {', '.join(missing)}")
    return GuardrailResult(True, "OK")


# ── Brokerage fee ceiling (宅建業法46条) ─────────────────────────────────────
# Schedule (excluding tax):
#   sale price <=  200万: 5%
#   sale price <=  400万: 4% + 2万
#   sale price >   400万: 3% + 6万
# 消費税 (consumption tax) = 10%

_TAX_RATE: Final[float] = 0.10
_TIER_LOW: Final[int] = 2_000_000
_TIER_MID: Final[int] = 4_000_000


def calc_brokerage_fee_ceiling(sale_price: MoneyJPY) -> MoneyJPY:
    """Return the maximum one-side brokerage fee (税込) for a given sale price."""
    yen = sale_price.amount
    if yen <= 0:
        return MoneyJPY(0)
    if yen <= _TIER_LOW:
        base = int(yen * 0.05)
    elif yen <= _TIER_MID:
        base = int(yen * 0.04) + 20_000
    else:
        base = int(yen * 0.03) + 60_000
    with_tax = int(round(base * (1 + _TAX_RATE)))
    return MoneyJPY(with_tax)


# ── 旧耐震基準 risk check ───────────────────────────────────────────────────
# The new earthquake resistance standard (新耐震基準) took effect 1981-06-01.
# Since built_year alone cannot distinguish month, we conservatively flag
# any building with built_year <= 1981 as potentially 旧耐震.

_SHINTAISHIN_CUTOFF: Final[int] = 1981


def check_kyuutaishin_risk(built_year: int | None) -> GuardrailResult:
    """Flag buildings that may fall under 旧耐震基準 (pre-1981/6)."""
    if built_year is None:
        return GuardrailResult(
            False,
            "築年数不明 (unknown built year) — 旧耐震リスク判定不可。融資審査に影響する可能性があります。",
        )
    if built_year <= _SHINTAISHIN_CUTOFF:
        return GuardrailResult(
            False,
            f"旧耐震基準の可能性 (built {built_year}, cutoff 1981/6)。"
            "多くの金融機関で融資条件が厳しくなる場合があります。",
        )
    return GuardrailResult(True, "OK")


# ── JPY offer validation ────────────────────────────────────────────────────


def validate_offer_jp(
    offer_price: MoneyJPY,
    asking_price: MoneyJPY,
    buyer_budget: MoneyJPY,
) -> GuardrailResult:
    """Validate an offer in JPY against hard-coded rules."""
    if offer_price.amount > buyer_budget.amount:
        return GuardrailResult(False, "予算超過: offer exceeds buyer budget")
    min_offer = int(asking_price.amount * settings.min_offer_percent)
    if offer_price.amount < min_offer:
        pct = int(settings.min_offer_percent * 100)
        return GuardrailResult(False, f"指値が低すぎます: offer below {pct}% of asking price")
    return GuardrailResult(True, "OK")


# ── JP disclosure validation (wraps juuyou jikou) ───────────────────────────


def validate_disclosures_jp(disclosures: dict) -> GuardrailResult:
    """Full JP disclosure check — currently delegates to juuyou jikou validation."""
    return validate_juuyou_jikou(disclosures)
