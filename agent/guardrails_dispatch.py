"""Jurisdiction-aware guardrail dispatch.

Routes validation calls to US or JP guardrails based on settings.jurisdiction.
Callers use these functions instead of importing guardrails / guardrails_jp directly.
"""

from __future__ import annotations

from config import settings
from agent.guardrails import (
    GuardrailResult as USGuardrailResult,
    validate_offer as validate_offer_us,
    validate_disclosures as validate_disclosures_us,
)
from agent.guardrails_jp import (
    GuardrailResult,
    validate_offer_jp,
    validate_disclosures_jp,
)
from services.money_jp import MoneyJPY


def dispatch_validate_offer(
    offer_price: float | int,
    asking_price: float | int,
    buyer_budget: float | int,
) -> GuardrailResult:
    """Route offer validation by jurisdiction.

    For jp_tokyo: converts numeric yen to MoneyJPY and delegates to guardrails_jp.
    For us: delegates to guardrails.py (float USD).
    """
    if settings.jurisdiction.startswith("jp"):
        result = validate_offer_jp(
            offer_price=MoneyJPY(int(offer_price)),
            asking_price=MoneyJPY(int(asking_price)),
            buyer_budget=MoneyJPY(int(buyer_budget)),
        )
        return result

    us_result = validate_offer_us(float(offer_price), float(asking_price), float(buyer_budget))
    return GuardrailResult(passed=us_result.passed, reason=us_result.reason)


def dispatch_validate_disclosures(disclosures: dict) -> GuardrailResult:
    """Route disclosure validation by jurisdiction."""
    if settings.jurisdiction.startswith("jp"):
        return validate_disclosures_jp(disclosures)

    us_result = validate_disclosures_us(disclosures)
    return GuardrailResult(passed=us_result.passed, reason=us_result.reason)
