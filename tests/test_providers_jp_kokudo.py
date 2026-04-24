"""Tests for mock 国土数値情報 hazard/zoning provider."""

from __future__ import annotations

import pytest

from services.providers_jp.kokudo_suuchi import MockKokudoSuuchiProvider, KokudoSuuchiProvider


@pytest.fixture
def provider() -> MockKokudoSuuchiProvider:
    return MockKokudoSuuchiProvider()


@pytest.mark.asyncio
async def test_get_flood_risk_within_bounds(provider: MockKokudoSuuchiProvider) -> None:
    # Point inside the first flood polygon (麻布十番 area)
    risks = await provider.get_flood_risk(latitude=35.6545, longitude=139.7380)
    assert len(risks) >= 1
    assert risks[0]["hazard_type"] == "flood"


@pytest.mark.asyncio
async def test_get_flood_risk_outside_bounds_empty(provider: MockKokudoSuuchiProvider) -> None:
    # Point far from any fixture polygon
    risks = await provider.get_flood_risk(latitude=35.0, longitude=139.0)
    assert len(risks) == 0


@pytest.mark.asyncio
async def test_get_zoning_returns_properties(provider: MockKokudoSuuchiProvider) -> None:
    # Point inside 六本木 zoning polygon
    zoning = await provider.get_zoning(latitude=35.6606, longitude=139.7295)
    assert zoning is not None
    assert zoning["youto_chiiki"] == "商業地域"
    assert zoning["kenpei_ritsu"] == 80


@pytest.mark.asyncio
async def test_get_zoning_outside_bounds_none(provider: MockKokudoSuuchiProvider) -> None:
    zoning = await provider.get_zoning(latitude=35.0, longitude=139.0)
    assert zoning is None


def test_protocol_compliance() -> None:
    assert isinstance(MockKokudoSuuchiProvider(), KokudoSuuchiProvider)
