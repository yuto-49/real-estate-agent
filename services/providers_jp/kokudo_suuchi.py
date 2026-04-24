"""国土数値情報 hazard/zoning GeoJSON provider — mock reads from fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

_FIXTURES_BASE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "tokyo"


def _point_in_bbox(lat: float, lng: float, coords: list) -> bool:
    """Check if a point falls within the bounding box of a polygon ring."""
    lngs = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return min(lngs) <= lng <= max(lngs) and min(lats) <= lat <= max(lats)


@runtime_checkable
class KokudoSuuchiProvider(Protocol):
    """Protocol for 国土数値情報 hazard and zoning data."""

    async def get_flood_risk(
        self, latitude: float, longitude: float, radius_km: float = 1.0
    ) -> list[dict]: ...

    async def get_zoning(self, latitude: float, longitude: float) -> dict | None: ...


class MockKokudoSuuchiProvider:
    """Reads GeoJSON fixtures, uses bounding-box containment for matching."""

    def __init__(self, fixtures_base: Path = _FIXTURES_BASE) -> None:
        self._fixtures_base = fixtures_base
        self._flood_cache: list[dict] | None = None
        self._zoning_cache: list[dict] | None = None

    def _load_flood(self) -> list[dict]:
        if self._flood_cache is not None:
            return self._flood_cache
        fp = self._fixtures_base / "hazard_maps" / "minato_flood.geojson"
        data = json.loads(fp.read_text(encoding="utf-8"))
        self._flood_cache = data.get("features", [])
        return self._flood_cache

    def _load_zoning(self) -> list[dict]:
        if self._zoning_cache is not None:
            return self._zoning_cache
        fp = self._fixtures_base / "zoning" / "tokyo23_zoning_sample.geojson"
        data = json.loads(fp.read_text(encoding="utf-8"))
        self._zoning_cache = data.get("features", [])
        return self._zoning_cache

    async def get_flood_risk(
        self, latitude: float, longitude: float, radius_km: float = 1.0
    ) -> list[dict]:
        hits = []
        for feature in self._load_flood():
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [[]])[0]
            if coords and _point_in_bbox(latitude, longitude, coords):
                hits.append(feature["properties"])
        return hits

    async def get_zoning(self, latitude: float, longitude: float) -> dict | None:
        for feature in self._load_zoning():
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [[]])[0]
            if coords and _point_in_bbox(latitude, longitude, coords):
                return feature["properties"]
        return None
