"""Market data provider pattern — Protocol + Mock + Real implementations."""

from typing import Protocol, runtime_checkable

from config import settings


@runtime_checkable
class MarketDataProvider(Protocol):
    async def get_local_stats(self, zip_code: str, radius_miles: int = 10) -> dict: ...
    async def get_active_listings(
        self,
        latitude: float,
        longitude: float,
        min_price: float | None = None,
        max_price: float | None = None,
        property_types: list[str] | None = None,
    ) -> list[dict]: ...
    async def get_comps(self, address: str, radius_miles: float = 1.0) -> list[dict]: ...


class MockMarketDataProvider:
    """Rich mock data for Chicago area development."""

    CHICAGO_STATS = {
        "60601": {"median_price": 425000, "mortgage_rate": 6.3, "months_inventory": 1.8, "days_on_market": 28, "rent_vs_buy": 1.15, "yoy_change": 3.1},
        "60602": {"median_price": 510000, "mortgage_rate": 6.3, "months_inventory": 2.0, "days_on_market": 32, "rent_vs_buy": 1.22, "yoy_change": 2.8},
        "60614": {"median_price": 475000, "mortgage_rate": 6.3, "months_inventory": 1.5, "days_on_market": 22, "rent_vs_buy": 1.18, "yoy_change": 4.2},
        "60622": {"median_price": 520000, "mortgage_rate": 6.3, "months_inventory": 1.3, "days_on_market": 18, "rent_vs_buy": 1.25, "yoy_change": 5.1},
        "60640": {"median_price": 310000, "mortgage_rate": 6.3, "months_inventory": 2.8, "days_on_market": 45, "rent_vs_buy": 0.95, "yoy_change": 1.5},
        "60647": {"median_price": 455000, "mortgage_rate": 6.3, "months_inventory": 1.6, "days_on_market": 25, "rent_vs_buy": 1.12, "yoy_change": 3.8},
    }

    MOCK_LISTINGS = [
        {"address": "1842 W Armitage Ave, Chicago, IL 60622", "price": 485000, "bedrooms": 3, "bathrooms": 2, "sqft": 1800, "property_type": "sfr", "latitude": 41.9178, "longitude": -87.6735},
        {"address": "2105 N Damen Ave, Chicago, IL 60647", "price": 340000, "bedrooms": 2, "bathrooms": 1, "sqft": 1200, "property_type": "condo", "latitude": 41.9207, "longitude": -87.6776},
        {"address": "4521 N Sheridan Rd, Chicago, IL 60640", "price": 275000, "bedrooms": 2, "bathrooms": 1.5, "sqft": 1100, "property_type": "condo", "latitude": 41.9667, "longitude": -87.6553},
        {"address": "1620 N Damen Ave, Chicago, IL 60647", "price": 395000, "bedrooms": 3, "bathrooms": 2, "sqft": 1500, "property_type": "sfr", "latitude": 41.9112, "longitude": -87.6776},
        {"address": "3245 N Sheffield Ave, Chicago, IL 60657", "price": 550000, "bedrooms": 4, "bathrooms": 2.5, "sqft": 2200, "property_type": "sfr", "latitude": 41.9403, "longitude": -87.6537},
        {"address": "825 W Addison St, Chicago, IL 60613", "price": 289000, "bedrooms": 2, "bathrooms": 1, "sqft": 950, "property_type": "condo", "latitude": 41.9472, "longitude": -87.6487},
        {"address": "5122 N Clark St, Chicago, IL 60640", "price": 315000, "bedrooms": 2, "bathrooms": 2, "sqft": 1150, "property_type": "condo", "latitude": 41.9750, "longitude": -87.6684},
        {"address": "2850 N Milwaukee Ave, Chicago, IL 60618", "price": 425000, "bedrooms": 3, "bathrooms": 1.5, "sqft": 1650, "property_type": "duplex", "latitude": 41.9332, "longitude": -87.7120},
    ]

    MOCK_COMPS = [
        {"address": "1850 W Armitage Ave", "sold_price": 478000, "sold_date": "2025-12-15", "sqft": 1780, "bedrooms": 3, "bathrooms": 2},
        {"address": "1900 W Armitage Ave", "sold_price": 495000, "sold_date": "2026-01-08", "sqft": 1850, "bedrooms": 3, "bathrooms": 2.5},
        {"address": "2010 W Armitage Ave", "sold_price": 462000, "sold_date": "2025-11-20", "sqft": 1700, "bedrooms": 3, "bathrooms": 2},
    ]

    async def get_local_stats(self, zip_code: str, radius_miles: int = 10) -> dict:
        base = self.CHICAGO_STATS.get(zip_code, {
            "median_price": 325000, "mortgage_rate": 6.3, "months_inventory": 2.1,
            "days_on_market": 42, "rent_vs_buy": 1.08, "yoy_change": 2.2,
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

    async def get_comps(self, address: str, radius_miles: float = 1.0) -> list[dict]:
        return self.MOCK_COMPS


class ZillowMarketDataProvider:
    """Real Zillow/ATTOM API implementation."""

    def __init__(self, zillow_key: str = "", attom_key: str = ""):
        self.zillow_key = zillow_key or settings.zillow_api_key
        self.attom_key = attom_key or settings.attom_api_key

    async def get_local_stats(self, zip_code: str, radius_miles: int = 10) -> dict:
        # TODO: Implement real Zillow/ATTOM API calls
        # Fallback to mock for now
        return await MockMarketDataProvider().get_local_stats(zip_code, radius_miles)

    async def get_active_listings(
        self,
        latitude: float,
        longitude: float,
        min_price: float | None = None,
        max_price: float | None = None,
        property_types: list[str] | None = None,
    ) -> list[dict]:
        # TODO: Implement real Zillow API
        return []

    async def get_comps(self, address: str, radius_miles: float = 1.0) -> list[dict]:
        # TODO: Implement real comps lookup
        return []


class MarketDataFactory:
    @staticmethod
    def create(provider_name: str | None = None) -> MarketDataProvider:
        name = provider_name or settings.market_data_provider
        if name == "zillow":
            return ZillowMarketDataProvider()
        return MockMarketDataProvider()
