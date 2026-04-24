"""REINS listing provider — mock implementation reads from JSON fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "tokyo" / "reins_samples"


@runtime_checkable
class ReinsListingProvider(Protocol):
    """Protocol for REINS listing data access."""

    async def search_listings(
        self,
        ku: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        property_types: list[str] | None = None,
    ) -> list[dict]: ...

    async def get_listing(self, bukken_bangou: str) -> dict | None: ...


class MockReinsProvider:
    """Reads synthetic REINS fixtures from disk, caches on first load."""

    def __init__(self, fixtures_dir: Path = _FIXTURES_DIR) -> None:
        self._fixtures_dir = fixtures_dir
        self._cache: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._cache is not None:
            return self._cache
        listings: list[dict] = []
        for fp in sorted(self._fixtures_dir.glob("listings_*.json")):
            data = json.loads(fp.read_text(encoding="utf-8"))
            listings.extend(data.get("listings", []))
        self._cache = listings
        return listings

    async def search_listings(
        self,
        ku: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        property_types: list[str] | None = None,
    ) -> list[dict]:
        results = self._load()
        if ku is not None:
            results = [r for r in results if r.get("shozaichi", {}).get("shikuchouson") == ku]
        if min_price is not None:
            results = [r for r in results if r.get("baibai_kakaku_yen", 0) >= min_price]
        if max_price is not None:
            results = [r for r in results if r.get("baibai_kakaku_yen", 0) <= max_price]
        if property_types is not None:
            results = [r for r in results if r.get("bukken_shubetsu") in property_types]
        return results

    async def get_listing(self, bukken_bangou: str) -> dict | None:
        for listing in self._load():
            if listing.get("bukken_bangou") == bukken_bangou:
                return listing
        return None
