"""Tests for mock MLIT reinfolib provider."""

from __future__ import annotations

import pytest

from services.providers_jp.reinfolib import MockReinfolibProvider, ReinfolibProvider


@pytest.fixture
def provider() -> MockReinfolibProvider:
    return MockReinfolibProvider()


@pytest.mark.asyncio
async def test_get_transactions_returns_all(provider: MockReinfolibProvider) -> None:
    txns = await provider.get_transactions()
    # CSV has 13 data rows (header excluded)
    assert len(txns) == 13


@pytest.mark.asyncio
async def test_filter_by_city_code(provider: MockReinfolibProvider) -> None:
    txns = await provider.get_transactions(city_code="13103")
    assert len(txns) > 0
    assert all(r["市区町村コード"] == "13103" for r in txns)


@pytest.mark.asyncio
async def test_get_price_index_returns_median(provider: MockReinfolibProvider) -> None:
    idx = await provider.get_price_index("13103")
    assert idx["city_code"] == "13103"
    assert idx["median_price"] is not None
    assert isinstance(idx["median_price"], int)
    assert idx["count"] > 0


@pytest.mark.asyncio
async def test_csv_numeric_parsing(provider: MockReinfolibProvider) -> None:
    txns = await provider.get_transactions()
    for txn in txns:
        if txn.get("取引価格_int") is not None:
            assert isinstance(txn["取引価格_int"], int)
        if txn.get("面積_float") is not None:
            assert isinstance(txn["面積_float"], float)


def test_protocol_compliance() -> None:
    assert isinstance(MockReinfolibProvider(), ReinfolibProvider)
