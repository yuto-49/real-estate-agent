"""Tests for mock REINS listing provider."""

from __future__ import annotations

import pytest

from services.providers_jp.reins import MockReinsProvider, ReinsListingProvider


@pytest.fixture
def provider() -> MockReinsProvider:
    return MockReinsProvider()


@pytest.mark.asyncio
async def test_search_all_returns_9_listings(provider: MockReinsProvider) -> None:
    results = await provider.search_listings()
    assert len(results) == 9


@pytest.mark.asyncio
async def test_search_by_ku_minato(provider: MockReinsProvider) -> None:
    results = await provider.search_listings(ku="港区")
    assert len(results) == 3
    assert all(r.get("shozaichi", {}).get("shikuchouson") == "港区" for r in results)


@pytest.mark.asyncio
async def test_search_by_price_range(provider: MockReinsProvider) -> None:
    results = await provider.search_listings(min_price=100_000_000, max_price=200_000_000)
    assert len(results) > 0
    assert all(100_000_000 <= r["baibai_kakaku_yen"] <= 200_000_000 for r in results)


@pytest.mark.asyncio
async def test_get_listing_by_bukken_bangou(provider: MockReinsProvider) -> None:
    listing = await provider.get_listing("SYN-13103-0001")
    assert listing is not None
    assert listing["bukken_bangou"] == "SYN-13103-0001"


@pytest.mark.asyncio
async def test_get_listing_not_found_returns_none(provider: MockReinsProvider) -> None:
    listing = await provider.get_listing("NONEXISTENT-9999")
    assert listing is None


def test_protocol_compliance() -> None:
    assert isinstance(MockReinsProvider(), ReinsListingProvider)
