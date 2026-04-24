"""Tests for mock e-Stat demographics provider."""

from __future__ import annotations

import pytest

from services.providers_jp.estat import MockEstatProvider, EstatProvider


@pytest.fixture
def provider() -> MockEstatProvider:
    return MockEstatProvider()


@pytest.mark.asyncio
async def test_get_all_population(provider: MockEstatProvider) -> None:
    records = await provider.get_population()
    assert len(records) == 4


@pytest.mark.asyncio
async def test_filter_by_area_code(provider: MockEstatProvider) -> None:
    # 13103 = 港区
    records = await provider.get_population(area_code="13103")
    assert len(records) == 2
    assert all(r["kcode"].startswith("13103") for r in records)


@pytest.mark.asyncio
async def test_filter_by_area_code_no_match(provider: MockEstatProvider) -> None:
    records = await provider.get_population(area_code="99999")
    assert len(records) == 0


def test_protocol_compliance() -> None:
    assert isinstance(MockEstatProvider(), EstatProvider)
