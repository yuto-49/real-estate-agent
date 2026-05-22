"""Strategy profile extractor tests — Phase S5."""

from __future__ import annotations

import pytest

from api.schemas import StrategyProfile
from services.strategy_profile import (
    HeuristicStrategyExtractor,
    default_strategy_profile,
    extract_strategy_profile,
)


@pytest.mark.asyncio
async def test_empty_text_returns_default_profile():
    profile = await extract_strategy_profile("")
    assert profile == default_strategy_profile()
    assert profile.assumptions.rent_growth == 0.03
    assert profile.policy_config.risk_tolerance == "medium"
    assert profile.thesis.market_outlook == "neutral"


@pytest.mark.asyncio
async def test_heuristic_extracts_percentages():
    text = "I expect rent growth around 4% with 8% vacancy and a 10-year hold."
    profile = await extract_strategy_profile(text)
    assert profile.assumptions.rent_growth == pytest.approx(0.04)
    assert profile.assumptions.vacancy_rate == pytest.approx(0.08)
    assert profile.assumptions.hold_period_years == 10


@pytest.mark.asyncio
async def test_heuristic_detects_buy_and_hold_low_risk():
    text = "Buy and hold, low risk, protect tenants from displacement."
    profile = await extract_strategy_profile(text)
    assert profile.policy_config.risk_tolerance == "low"
    assert profile.policy_config.sell_bias < 0
    assert profile.policy_config.tenant_protection is True
    assert profile.thesis.trajectory == "displacement_pressure"


@pytest.mark.asyncio
async def test_heuristic_detects_aggressive_flip_thesis():
    text = (
        "Aggressive strategy — flip after 3 years in a gentrifying zip. "
        "Push rent toward market."
    )
    profile = await extract_strategy_profile(text)
    assert profile.policy_config.risk_tolerance == "high"
    assert profile.policy_config.sell_bias > 0
    assert profile.policy_config.raise_rent_bias > 0
    assert profile.thesis.market_outlook == "bullish"
    assert profile.thesis.trajectory == "neighborhood_trajectory"
    assert profile.assumptions.hold_period_years == 3


@pytest.mark.asyncio
async def test_injected_extractor_is_used():
    captured: list[str] = []

    class StubExtractor:
        async def extract(self, text: str) -> StrategyProfile | None:
            captured.append(text)
            return StrategyProfile()

    profile = await extract_strategy_profile(
        "anything", extractor=StubExtractor()
    )
    assert profile == StrategyProfile()
    assert captured == ["anything"]


@pytest.mark.asyncio
async def test_extractor_failure_falls_back_to_heuristic():
    class FailingExtractor:
        async def extract(self, text: str) -> StrategyProfile | None:
            raise RuntimeError("LLM unavailable")

    profile = await extract_strategy_profile(
        "Long-term buy and hold at 5% rent growth.",
        extractor=FailingExtractor(),
    )
    # Falls back to heuristic, which still parses the 5% figure.
    assert profile.assumptions.rent_growth == pytest.approx(0.05)
    assert profile.policy_config.sell_bias < 0


@pytest.mark.asyncio
async def test_heuristic_extractor_direct_returns_none_for_empty():
    result = await HeuristicStrategyExtractor().extract("")
    assert result is None
