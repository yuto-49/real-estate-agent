"""Tests for MockMarketDataProvider (Tokyo ward data)."""

import pytest

from services.market_data_provider import (
    MarketDataFactory,
    MockMarketDataProvider,
)


@pytest.fixture
def provider():
    return MockMarketDataProvider()


class TestTokyoStats:

    @pytest.mark.asyncio
    async def test_local_stats_returns_valid_structure(self, provider):
        stats = await provider.get_local_stats("106")
        assert stats["zip_code"] == "106"
        assert stats["median_price"] == 85_000_000
        assert stats["mortgage_rate"] == 1.2

    @pytest.mark.asyncio
    async def test_stats_for_shibuya(self, provider):
        stats = await provider.get_local_stats("150")
        assert stats["median_price"] == 78_000_000
        assert stats["ward"] == "渋谷区"

    @pytest.mark.asyncio
    async def test_stats_prefix_lookup(self, provider):
        stats = await provider.get_local_stats("106-0032")
        assert stats["median_price"] == 85_000_000

    @pytest.mark.asyncio
    async def test_stats_fallback_on_unknown_code(self, provider):
        stats = await provider.get_local_stats("999")
        assert stats["median_price"] == 50_000_000


class TestTokyoListings:

    @pytest.mark.asyncio
    async def test_all_listings_returned_without_filters(self, provider):
        listings = await provider.get_active_listings(35.68, 139.76)
        assert len(listings) == 8

    @pytest.mark.asyncio
    async def test_min_price_filter(self, provider):
        listings = await provider.get_active_listings(
            35.68, 139.76, min_price=80_000_000,
        )
        assert all(item["price"] >= 80_000_000 for item in listings)
        assert len(listings) > 0

    @pytest.mark.asyncio
    async def test_max_price_filter(self, provider):
        listings = await provider.get_active_listings(
            35.68, 139.76, max_price=50_000_000,
        )
        assert all(item["price"] <= 50_000_000 for item in listings)

    @pytest.mark.asyncio
    async def test_property_type_filter(self, provider):
        listings = await provider.get_active_listings(
            35.68, 139.76, property_types=["kodate"],
        )
        assert all(item["property_type"] == "kodate" for item in listings)
        assert len(listings) > 0

    @pytest.mark.asyncio
    async def test_listing_has_required_fields(self, provider):
        listings = await provider.get_active_listings(35.68, 139.76)
        required = {"address", "price", "bedrooms", "bathrooms", "sqft_m2",
                     "property_type", "latitude", "longitude"}
        for item in listings:
            assert required.issubset(item.keys())

    @pytest.mark.asyncio
    async def test_coordinates_are_in_tokyo_area(self, provider):
        listings = await provider.get_active_listings(35.68, 139.76)
        for item in listings:
            assert 35.5 <= item["latitude"] <= 35.9
            assert 139.5 <= item["longitude"] <= 140.0


class TestTokyoComps:

    @pytest.mark.asyncio
    async def test_comps_returns_list(self, provider):
        comps = await provider.get_comps("東京都港区六本木6-10-1")
        assert isinstance(comps, list)
        assert len(comps) == 3

    @pytest.mark.asyncio
    async def test_comps_have_jpy_prices(self, provider):
        comps = await provider.get_comps("東京都港区六本木6-10-1")
        for comp in comps:
            assert "sold_price" in comp
            assert comp["sold_price"] >= 10_000_000


class TestMarketDataFactory:

    def test_factory_default_is_mock(self):
        provider = MarketDataFactory.create("mock")
        assert isinstance(provider, MockMarketDataProvider)

    def test_factory_none_returns_mock(self):
        provider = MarketDataFactory.create()
        assert isinstance(provider, MockMarketDataProvider)
