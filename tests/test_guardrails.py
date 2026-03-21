"""Guardrail unit tests — these are your circuit breaker tests."""

from agent.guardrails import (
    validate_offer,
    check_escalation,
    check_max_rounds,
    validate_disclosures,
    check_price_per_sqft,
)


def test_offer_within_budget():
    result = validate_offer(300_000, 350_000, 400_000)
    assert result.passed


def test_offer_exceeds_budget():
    result = validate_offer(500_000, 350_000, 400_000)
    assert not result.passed
    assert "exceeds" in result.reason.lower()


def test_offer_below_minimum():
    result = validate_offer(100_000, 350_000, 400_000)
    assert not result.passed
    assert "below" in result.reason.lower()


def test_escalation_above_threshold():
    assert check_escalation(2_500_000) is True


def test_no_escalation_below_threshold():
    assert check_escalation(1_500_000) is False


def test_max_rounds_exceeded():
    assert check_max_rounds(11) is True


def test_max_rounds_not_exceeded():
    assert check_max_rounds(5) is False


def test_valid_disclosures():
    disclosures = {
        "known_defects": "none",
        "flood_zone": "no",
        "hoa_fees": "0",
        "lead_paint": "no",
        "environmental_hazards": "none",
    }
    result = validate_disclosures(disclosures)
    assert result.passed


def test_missing_disclosures():
    result = validate_disclosures({"known_defects": "none"})
    assert not result.passed
    assert "flood_zone" in result.reason


def test_price_per_sqft_normal():
    result = check_price_per_sqft(400_000, 2000)
    assert result.passed


def test_price_per_sqft_excessive():
    result = check_price_per_sqft(1_000_000, 100)
    assert not result.passed
