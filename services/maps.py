"""TomTom Maps integration — geocoding + nearby POI search.

Free tier: 2,500 non-tile requests/day, 50,000 tile requests/day, no credit card.
https://developer.tomtom.com/
"""

import hashlib
import json

import httpx

from config import settings
from services.geocache import GeohashCache

# TomTom POI category IDs — https://developer.tomtom.com/search-api/documentation/product-information/supported-category-codes
TOMTOM_CATEGORY_MAP = {
    "school": "7372",           # School
    "restaurant": "7315",       # Restaurant
    "transit_station": "9942",  # Public transport stop
    "park": "9362",             # Park & recreation area
    "grocery": "7332",          # Grocery store
    "hospital": "7321",         # Hospital/polyclinic
}


class MapsService:
    """TomTom-based geocoding and neighborhood analysis."""

    BASE_URL = "https://api.tomtom.com/search/2"

    def __init__(self, api_key: str | None = None, geocache: GeohashCache | None = None):
        self.api_key = api_key or settings.tomtom_api_key
        self.geocache = geocache
        self._http: httpx.AsyncClient | None = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self._http

    async def analyze_neighborhood(
        self, address: str, radius: int = 1500, categories: list[str] | None = None
    ) -> dict:
        """Analyze neighborhood using TomTom Nearby Search (category + radius POI search)."""
        categories = categories or ["school", "restaurant", "transit_station", "park"]

        geo = await self.geocode(address)
        if not geo:
            return {"address": address, "error": "geocoding_failed"}

        lat, lng = geo["lat"], geo["lng"]

        # Check cache
        if self.geocache:
            cached = await self.geocache.get(lat, lng, suffix="neighborhood")
            if cached:
                return cached

        results = {"address": address, "lat": lat, "lng": lng, "nearby": {}}
        total_places = 0

        for cat in categories:
            tt_cat = TOMTOM_CATEGORY_MAP.get(cat, cat)
            try:
                resp = await self.http.get(
                    f"{self.BASE_URL}/nearbySearch/.json",
                    params={
                        "key": self.api_key,
                        "lat": lat,
                        "lon": lng,
                        "radius": radius,
                        "categorySet": tt_cat,
                        "limit": 10,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                nearby = []
                for item in data.get("results", [])[:10]:
                    poi = item.get("poi", {})
                    addr = item.get("address", {})
                    nearby.append({
                        "name": poi.get("name", ""),
                        "rating": poi.get("score"),
                        "types": [c if isinstance(c, str) else c.get("name", "") for c in poi.get("categories", [])],
                        "distance_m": item.get("dist"),
                        "address": addr.get("freeformAddress", ""),
                    })
                results["nearby"][cat] = nearby
                total_places += len(nearby)

            except httpx.HTTPError:
                results["nearby"][cat] = []

        results["walkability_score"] = min(100, total_places * 5)

        # Cache
        if self.geocache:
            await self.geocache.set(lat, lng, results, suffix="neighborhood")

        return results

    async def geocode(self, address: str) -> dict | None:
        """Forward geocode an address to lat/lng using TomTom Geocoding API."""
        # Check cache
        if self.geocache:
            addr_hash = hashlib.md5(address.encode()).hexdigest()[:8]
            cached = await self.geocache.redis.get(f"geocache:addr:{addr_hash}")
            if cached:
                return json.loads(cached)

        try:
            resp = await self.http.get(
                f"{self.BASE_URL}/geocode/{address}.json",
                params={"key": self.api_key, "limit": 1},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return None

            pos = results[0].get("position", {})
            geo_data = {"lat": pos.get("lat"), "lng": pos.get("lon")}

            if geo_data["lat"] is None or geo_data["lng"] is None:
                return None

            # Cache
            if self.geocache:
                addr_hash = hashlib.md5(address.encode()).hexdigest()[:8]
                await self.geocache.redis.set(
                    f"geocache:addr:{addr_hash}",
                    json.dumps(geo_data),
                    ex=GeohashCache.TTL_SECONDS,
                )

            return geo_data

        except httpx.HTTPError:
            return None

    async def reverse_geocode(self, lat: float, lng: float) -> str | None:
        """Reverse geocode lat/lng to an address using TomTom Reverse Geocoding API."""
        try:
            resp = await self.http.get(
                f"{self.BASE_URL}/reverseGeocode/{lat},{lng}.json",
                params={"key": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            addresses = data.get("addresses", [])
            if addresses:
                return addresses[0].get("address", {}).get("freeformAddress")
            return None
        except httpx.HTTPError:
            return None

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None
