"""Market data provider pattern — Protocol + Mock (Tokyo) implementation."""

from typing import Protocol, runtime_checkable

from config import settings


@runtime_checkable
class MarketDataProvider(Protocol):
    async def get_local_stats(self, zip_code: str, radius_km: int = 10) -> dict: ...
    async def get_active_listings(
        self,
        latitude: float,
        longitude: float,
        min_price: float | None = None,
        max_price: float | None = None,
        property_types: list[str] | None = None,
    ) -> list[dict]: ...
    async def get_comps(self, address: str, radius_km: float = 1.0) -> list[dict]: ...


class MockMarketDataProvider:
    """Mock data for Tokyo wards development."""

    TOKYO_STATS = {
        "106": {"median_price": 85_000_000, "mortgage_rate": 1.2, "months_inventory": 2.1, "days_on_market": 35, "rent_vs_buy": 1.30, "yoy_change": 4.5, "ward": "港区"},
        "150": {"median_price": 78_000_000, "mortgage_rate": 1.2, "months_inventory": 1.8, "days_on_market": 28, "rent_vs_buy": 1.25, "yoy_change": 5.2, "ward": "渋谷区"},
        "160": {"median_price": 62_000_000, "mortgage_rate": 1.2, "months_inventory": 2.3, "days_on_market": 40, "rent_vs_buy": 1.10, "yoy_change": 3.1, "ward": "新宿区"},
        "113": {"median_price": 55_000_000, "mortgage_rate": 1.2, "months_inventory": 2.5, "days_on_market": 42, "rent_vs_buy": 1.05, "yoy_change": 2.8, "ward": "文京区"},
        "170": {"median_price": 48_000_000, "mortgage_rate": 1.2, "months_inventory": 3.0, "days_on_market": 50, "rent_vs_buy": 0.95, "yoy_change": 1.9, "ward": "豊島区"},
        "132": {"median_price": 38_000_000, "mortgage_rate": 1.2, "months_inventory": 3.5, "days_on_market": 55, "rent_vs_buy": 0.88, "yoy_change": 1.2, "ward": "江戸川区"},
    }

    MOCK_LISTINGS = [
        {"address": "東京都港区六本木6-10-1", "price": 198_000_000, "bedrooms": 2, "bathrooms": 1, "sqft_m2": 84.55, "property_type": "mansion", "latitude": 35.6604, "longitude": 139.7292},
        {"address": "東京都港区赤坂1-12-32", "price": 89_000_000, "bedrooms": 3, "bathrooms": 1, "sqft_m2": 72.30, "property_type": "mansion", "latitude": 35.6737, "longitude": 139.7410},
        {"address": "東京都渋谷区恵比寿西2-20-7", "price": 65_000_000, "bedrooms": 2, "bathrooms": 1, "sqft_m2": 55.00, "property_type": "mansion", "latitude": 35.6467, "longitude": 139.7082},
        {"address": "東京都新宿区西新宿3-7-1", "price": 52_000_000, "bedrooms": 3, "bathrooms": 1, "sqft_m2": 68.40, "property_type": "mansion", "latitude": 35.6896, "longitude": 139.6917},
        {"address": "東京都文京区本郷3-38-1", "price": 45_000_000, "bedrooms": 2, "bathrooms": 1, "sqft_m2": 50.20, "property_type": "kodate", "latitude": 35.7089, "longitude": 139.7600},
        {"address": "東京都豊島区駒込1-35-3", "price": 42_000_000, "bedrooms": 3, "bathrooms": 1, "sqft_m2": 62.15, "property_type": "kodate", "latitude": 35.7364, "longitude": 139.7483},
        {"address": "東京都江戸川区西葛西6-8-10", "price": 35_000_000, "bedrooms": 3, "bathrooms": 1, "sqft_m2": 75.80, "property_type": "kodate", "latitude": 35.6591, "longitude": 139.8551},
        {"address": "東京都渋谷区神宮前4-3-15", "price": 120_000_000, "bedrooms": 1, "bathrooms": 1, "sqft_m2": 45.00, "property_type": "apt", "latitude": 35.6695, "longitude": 139.7073},
    ]

    MOCK_COMPS = [
        {"address": "東京都港区六本木6-12-3", "sold_price": 185_000_000, "sold_date": "2026-01-15", "sqft_m2": 80.20, "bedrooms": 2, "bathrooms": 1},
        {"address": "東京都港区六本木7-3-8", "sold_price": 205_000_000, "sold_date": "2025-12-08", "sqft_m2": 88.50, "bedrooms": 2, "bathrooms": 1},
        {"address": "東京都港区赤坂2-5-10", "sold_price": 92_000_000, "sold_date": "2025-11-22", "sqft_m2": 74.30, "bedrooms": 3, "bathrooms": 1},
    ]

    async def get_local_stats(self, zip_code: str, radius_km: int = 10) -> dict:
        prefix = zip_code[:3] if len(zip_code) >= 3 else zip_code
        base = self.TOKYO_STATS.get(prefix, {
            "median_price": 50_000_000, "mortgage_rate": 1.2, "months_inventory": 2.5,
            "days_on_market": 42, "rent_vs_buy": 1.0, "yoy_change": 2.0,
        })
        return {"zip_code": zip_code, **base}

    async def get_active_listings(
        self,
        latitude: float,
        longitude: float,
        min_price: float | None = None,
        max_price: float | None = None,
        property_types: list[str] | None = None,
    ) -> list[dict]:
        results = []
        for listing in self.MOCK_LISTINGS:
            if min_price and listing["price"] < min_price:
                continue
            if max_price and listing["price"] > max_price:
                continue
            if property_types and listing["property_type"] not in property_types:
                continue
            results.append(listing)
        return results

    async def get_comps(self, address: str, radius_km: float = 1.0) -> list[dict]:
        return self.MOCK_COMPS


class MarketDataFactory:
    @staticmethod
    def create(provider_name: str | None = None) -> MarketDataProvider:
        name = provider_name or settings.market_data_provider
        return MockMarketDataProvider()
