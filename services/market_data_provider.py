"""Market data provider pattern — Protocol + Mock + Real implementations."""

import csv
import math
from pathlib import Path
from statistics import mean, median
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


class KaggleChicagoMarketDataProvider:
    """Market data derived from the Kaggle Chicago 2024 dataset.

    Loads the CSV once (fixture or full dataset) and serves stats,
    listings, and comps computed from real Chicago listing data.
    """

    # Chicago zip centroids for distance filtering
    ZIP_COORDS: dict[str, tuple[float, float]] = {
        "60601": (41.8858, -87.6181), "60605": (41.8713, -87.6277),
        "60607": (41.8721, -87.6578), "60610": (41.9033, -87.6336),
        "60611": (41.8971, -87.6223), "60614": (41.9229, -87.6483),
        "60618": (41.9464, -87.7042), "60622": (41.9019, -87.6779),
        "60625": (41.9703, -87.7042), "60626": (42.0095, -87.6689),
        "60640": (41.9719, -87.6624), "60647": (41.9209, -87.7043),
        "60657": (41.9399, -87.6528), "60660": (41.9909, -87.6629),
    }

    PROPERTY_TYPE_MAP = {
        "single_family": "sfr", "condos": "condo", "townhomes": "condo",
        "multi_family": "multifamily", "apartment": "condo",
        "mobile": "sfr", "land": "land",
    }

    def __init__(self, csv_path: str | Path | None = None):
        if csv_path is None:
            # Try fixture first, then kagglehub cache
            fixture = (
                Path(__file__).resolve().parents[1]
                / "tests" / "fixtures" / "chicago_2024_sample.csv"
            )
            kagglehub = (
                Path.home() / ".cache" / "kagglehub" / "datasets"
                / "kanchana1990" / "real-estate-data-chicago-2024"
                / "versions" / "1" / "real_estate_data_chicago.csv"
            )
            csv_path = fixture if fixture.exists() else kagglehub

        self._csv_path = Path(csv_path)
        self._listings: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._listings is not None:
            return self._listings

        listings: list[dict] = []
        if not self._csv_path.exists():
            self._listings = listings
            return listings

        with open(self._csv_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("status") != "for_sale":
                    continue
                try:
                    price = float(row["listPrice"])
                except (ValueError, TypeError, KeyError):
                    continue
                if price < 50000:
                    continue

                listings.append({
                    "price": price,
                    "bedrooms": int(float(row["beds"])) if row.get("beds") else None,
                    "bathrooms": float(row["baths"]) if row.get("baths") else None,
                    "sqft": int(float(row["sqft"])) if row.get("sqft") else None,
                    "property_type": self.PROPERTY_TYPE_MAP.get(
                        row.get("type", ""), "sfr"
                    ),
                    "year_built": int(row["year_built"]) if row.get("year_built") else None,
                    "last_sold_price": (
                        float(row["lastSoldPrice"])
                        if row.get("lastSoldPrice") else None
                    ),
                    "text": row.get("text", "")[:200],
                })

        self._listings = listings
        return listings

    async def get_local_stats(self, zip_code: str, radius_miles: int = 10) -> dict:
        listings = self._load()
        prices = [item["price"] for item in listings]
        if not prices:
            return {
                "zip_code": zip_code, "median_price": 325000,
                "mortgage_rate": 6.3, "months_inventory": 2.1,
                "days_on_market": 35, "rent_vs_buy": 1.08, "yoy_change": 2.5,
            }

        sold_prices = [
            item["last_sold_price"] for item in listings
            if item["last_sold_price"]
        ]
        yoy = 0.0
        if sold_prices:
            avg_list = mean(prices)
            avg_sold = mean(sold_prices)
            yoy = round(((avg_list - avg_sold) / avg_sold) * 100, 1) if avg_sold else 0.0

        return {
            "zip_code": zip_code,
            "median_price": round(median(prices)),
            "mean_price": round(mean(prices)),
            "total_listings": len(prices),
            "mortgage_rate": 6.3,
            "months_inventory": round(len(prices) / max(len(prices) / 6, 1), 1),
            "days_on_market": 35,
            "rent_vs_buy": 1.10,
            "yoy_change": min(yoy, 15.0),
        }

    async def get_active_listings(
        self,
        latitude: float,
        longitude: float,
        min_price: float | None = None,
        max_price: float | None = None,
        property_types: list[str] | None = None,
    ) -> list[dict]:
        listings = self._load()
        results: list[dict] = []

        for idx, item in enumerate(listings):
            if min_price and item["price"] < min_price:
                continue
            if max_price and item["price"] > max_price:
                continue
            if property_types and item["property_type"] not in property_types:
                continue

            # Assign coordinates from zip centroids with deterministic jitter
            zip_keys = list(self.ZIP_COORDS.keys())
            zip_code = zip_keys[idx % len(zip_keys)]
            base_lat, base_lng = self.ZIP_COORDS[zip_code]
            jitter_lat = math.sin(idx * 0.7) * 0.002
            jitter_lng = math.cos(idx * 0.7) * 0.002

            results.append({
                "address": f"{100 + idx * 10} Chicago, IL {zip_code}",
                "price": item["price"],
                "bedrooms": item["bedrooms"],
                "bathrooms": item["bathrooms"],
                "sqft": item["sqft"],
                "property_type": item["property_type"],
                "latitude": base_lat + jitter_lat,
                "longitude": base_lng + jitter_lng,
            })

        return results

    async def get_comps(self, address: str, radius_miles: float = 1.0) -> list[dict]:
        listings = self._load()
        sold = [
            item for item in listings
            if item["last_sold_price"] and item["last_sold_price"] > 0
        ]
        # Return up to 5 comps
        comps: list[dict] = []
        for item in sold[:5]:
            comps.append({
                "address": f"Comp near {address}",
                "sold_price": item["last_sold_price"],
                "sold_date": "2024-01-01",
                "sqft": item["sqft"],
                "bedrooms": item["bedrooms"],
                "bathrooms": item["bathrooms"],
            })
        return comps


class MarketDataFactory:
    @staticmethod
    def create(provider_name: str | None = None) -> MarketDataProvider:
        name = provider_name or settings.market_data_provider
        if name == "zillow":
            return ZillowMarketDataProvider()
        if name == "kaggle_chicago":
            return KaggleChicagoMarketDataProvider()
        return MockMarketDataProvider()
