"""Redis connection pool management."""

import redis.asyncio as redis

from config import settings

_pool: redis.ConnectionPool | None = None
_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _pool, _client
    if _client is None:
        _pool = redis.ConnectionPool.from_url(
            settings.redis_url, decode_responses=True, max_connections=20
        )
        _client = redis.Redis(connection_pool=_pool)
    return _client


async def close_redis() -> None:
    global _pool, _client
    if _client:
        await _client.aclose()
        _client = None
    if _pool:
        await _pool.aclose()
        _pool = None
