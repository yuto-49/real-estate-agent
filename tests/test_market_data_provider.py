"""Market data provider tests."""

import pytest

from services.market_data_provider import (
    MockMarketDataProvider,
    MarketDataFactory,
    MarketDataProvider,
)


@pytest.mark.asyncio
async def test_mock_provider_local_stats():
    provider = MockMarketDataProvider()
    stats = await provider.get_local_stats("60614")
    assert stats["zip_code"] == "60614"
    assert stats["median_price"] == 475000
    assert stats["yoy_change"] == 4.2


@pytest.mark.asyncio
async def test_mock_provider_fallback_stats():
    provider = MockMarketDataProvider()
    stats = await provider.get_local_stats("99999")
    assert stats["zip_code"] == "99999"
    assert stats["median_price"] == 325000


@pytest.mark.asyncio
async def test_mock_provider_active_listings():
    provider = MockMarketDataProvider()
    listings = await provider.get_active_listings(41.88, -87.63)
    assert len(listings) > 0
    for listing in listings:
        assert "address" in listing
        assert "price" in listing


@pytest.mark.asyncio
async def test_mock_provider_listings_with_filters():
    provider = MockMarketDataProvider()
    listings = await provider.get_active_listings(
        41.88, -87.63, min_price=300000, max_price=400000
    )
    for listing in listings:
        assert 300000 <= listing["price"] <= 400000


@pytest.mark.asyncio
async def test_mock_provider_listings_by_type():
    provider = MockMarketDataProvider()
    listings = await provider.get_active_listings(
        41.88, -87.63, property_types=["condo"]
    )
    for listing in listings:
        assert listing["property_type"] == "condo"


@pytest.mark.asyncio
async def test_mock_provider_comps():
    provider = MockMarketDataProvider()
    comps = await provider.get_comps("1842 W Armitage Ave")
    assert len(comps) > 0
    assert "sold_price" in comps[0]


def test_factory_creates_mock():
    provider = MarketDataFactory.create("mock")
    assert isinstance(provider, MarketDataProvider)


def test_factory_default_is_mock():
    provider = MarketDataFactory.create()
    assert isinstance(provider, MockMarketDataProvider)
