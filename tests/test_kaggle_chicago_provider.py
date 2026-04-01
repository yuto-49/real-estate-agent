"""Tests for KaggleChicagoMarketDataProvider using the frozen fixture CSV."""

import pytest
from pathlib import Path

from services.market_data_provider import (
    KaggleChicagoMarketDataProvider,
    MarketDataFactory,
)

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "chicago_2024_sample.csv"


@pytest.fixture
def provider():
    return KaggleChicagoMarketDataProvider(csv_path=FIXTURE_CSV)


class TestKaggleChicagoStats:

    @pytest.mark.asyncio
    async def test_local_stats_returns_valid_structure(self, provider):
        stats = await provider.get_local_stats("60601")
        assert stats["zip_code"] == "60601"
        assert stats["median_price"] > 0
        assert stats["total_listings"] == 50
        assert stats["mortgage_rate"] == 6.3

    @pytest.mark.asyncio
    async def test_stats_median_in_plausible_range(self, provider):
        stats = await provider.get_local_stats("60614")
        # Chicago 2024 fixture median should be between 100k and 2M
        assert 100_000 <= stats["median_price"] <= 2_000_000

    @pytest.mark.asyncio
    async def test_stats_fallback_on_empty_csv(self):
        provider = KaggleChicagoMarketDataProvider(csv_path="/nonexistent.csv")
        stats = await provider.get_local_stats("60601")
        assert stats["median_price"] == 325000  # default fallback


class TestKaggleChicagoListings:

    @pytest.mark.asyncio
    async def test_all_listings_returned_without_filters(self, provider):
        listings = await provider.get_active_listings(41.88, -87.62)
        assert len(listings) == 50

    @pytest.mark.asyncio
    async def test_min_price_filter(self, provider):
        listings = await provider.get_active_listings(
            41.88, -87.62, min_price=500_000,
        )
        assert all(item["price"] >= 500_000 for item in listings)

    @pytest.mark.asyncio
    async def test_max_price_filter(self, provider):
        listings = await provider.get_active_listings(
            41.88, -87.62, max_price=300_000,
        )
        assert all(item["price"] <= 300_000 for item in listings)

    @pytest.mark.asyncio
    async def test_price_range_filter(self, provider):
        listings = await provider.get_active_listings(
            41.88, -87.62, min_price=200_000, max_price=400_000,
        )
        for item in listings:
            assert 200_000 <= item["price"] <= 400_000

    @pytest.mark.asyncio
    async def test_property_type_filter(self, provider):
        listings = await provider.get_active_listings(
            41.88, -87.62, property_types=["condo"],
        )
        assert all(item["property_type"] == "condo" for item in listings)
        assert len(listings) > 0

    @pytest.mark.asyncio
    async def test_listing_has_required_fields(self, provider):
        listings = await provider.get_active_listings(41.88, -87.62)
        required = {"address", "price", "bedrooms", "bathrooms", "sqft",
                     "property_type", "latitude", "longitude"}
        for item in listings:
            assert required.issubset(item.keys())

    @pytest.mark.asyncio
    async def test_coordinates_are_in_chicago_area(self, provider):
        listings = await provider.get_active_listings(41.88, -87.62)
        for item in listings:
            assert 41.6 <= item["latitude"] <= 42.1
            assert -87.9 <= item["longitude"] <= -87.5


class TestKaggleChicagoComps:

    @pytest.mark.asyncio
    async def test_comps_returns_list(self, provider):
        comps = await provider.get_comps("123 Main St")
        assert isinstance(comps, list)

    @pytest.mark.asyncio
    async def test_comps_have_sold_price(self, provider):
        comps = await provider.get_comps("123 Main St")
        for comp in comps:
            assert "sold_price" in comp
            assert comp["sold_price"] > 0


class TestMarketDataFactory:

    def test_factory_creates_kaggle_provider(self):
        provider = MarketDataFactory.create("kaggle_chicago")
        assert isinstance(provider, KaggleChicagoMarketDataProvider)

    def test_factory_default_is_mock(self):
        from services.market_data_provider import MockMarketDataProvider
        provider = MarketDataFactory.create("mock")
        assert isinstance(provider, MockMarketDataProvider)
