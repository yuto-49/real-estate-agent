"""Geohash-based Redis cache for Maps API responses."""

import json

import redis.asyncio as redis


class GeohashCache:
    """Caches geocoding and neighborhood data keyed by geohash prefix."""

    PRECISION = 6
    TTL_SECONDS = 86400  # 24 hours

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _make_key(self, lat: float, lng: float, suffix: str = "") -> str:
        try:
            import geohash2
            gh = geohash2.encode(lat, lng, precision=self.PRECISION)
        except ImportError:
            gh = f"{lat:.4f}:{lng:.4f}"
        return f"geocache:{gh}:{suffix}" if suffix else f"geocache:{gh}"

    async def get(self, lat: float, lng: float, suffix: str = "") -> dict | None:
        key = self._make_key(lat, lng, suffix)
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set(self, lat: float, lng: float, data: dict, suffix: str = "") -> None:
        key = self._make_key(lat, lng, suffix)
        await self.redis.set(key, json.dumps(data), ex=self.TTL_SECONDS)

    async def invalidate(self, lat: float, lng: float, suffix: str = "") -> None:
        key = self._make_key(lat, lng, suffix)
        await self.redis.delete(key)
