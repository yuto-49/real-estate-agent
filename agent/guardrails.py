"""Hard-coded business rules — the circuit breakers of the system.

These CANNOT be overridden by the LLM. Think of them as hardware interrupts:
no matter what the CPU (agent) is doing, these fire unconditionally.
"""

from dataclasses import dataclass
from config import settings


REQUIRED_DISCLOSURES = [
    "known_defects",
    "flood_zone",
    "hoa_fees",
    "lead_paint",
    "environmental_hazards",
]

PRICE_PER_SQFT_MAX = 5000  # Flag for manual review


@dataclass
class GuardrailResult:
    passed: bool
    reason: str


def validate_offer(offer_price: float, asking_price: float, buyer_budget: float) -> GuardrailResult:
    """Validate an offer against hard-coded rules."""
    if offer_price > buyer_budget:
        return GuardrailResult(False, "Offer exceeds buyer budget")
    if offer_price < asking_price * settings.min_offer_percent:
        return GuardrailResult(False, f"Offer below {int(settings.min_offer_percent * 100)}% of asking")
    return GuardrailResult(True, "OK")


def check_escalation(deal_value: float) -> bool:
    """Returns True if the deal requires human broker escalation."""
    return deal_value > settings.max_deal_value_auto


def check_max_rounds(round_count: int) -> bool:
    """Returns True if negotiation has exceeded max counter rounds."""
    return round_count >= settings.max_counter_rounds


def validate_disclosures(disclosures: dict) -> GuardrailResult:
    """Ensure all required disclosures are present before listing."""
    missing = [d for d in REQUIRED_DISCLOSURES if d not in disclosures]
    if missing:
        return GuardrailResult(False, f"Missing disclosures: {', '.join(missing)}")
    return GuardrailResult(True, "OK")


def check_price_per_sqft(price: float, sqft: int) -> GuardrailResult:
    """Flag unusually high price/sqft for manual review."""
    if sqft <= 0:
        return GuardrailResult(False, "Invalid sqft")
    ppsf = price / sqft
    if ppsf > PRICE_PER_SQFT_MAX:
        return GuardrailResult(False, f"Price/sqft ${ppsf:.0f} exceeds ${PRICE_PER_SQFT_MAX} threshold")
    return GuardrailResult(True, "OK")
