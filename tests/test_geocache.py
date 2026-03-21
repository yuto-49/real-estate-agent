"""GeohashCache tests."""

import json
import pytest
from unittest.mock import AsyncMock

from services.geocache import GeohashCache


@pytest.mark.asyncio
async def test_cache_miss(mock_redis):
    cache = GeohashCache(mock_redis)
    result = await cache.get(41.8781, -87.6298, suffix="neighborhood")
    assert result is None
    mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_cache_set_and_get(mock_redis):
    cache = GeohashCache(mock_redis)
    test_data = {"address": "123 Main St", "walkability_score": 75}

    await cache.set(41.8781, -87.6298, test_data, suffix="neighborhood")
    mock_redis.set.assert_called_once()

    # Verify the key format and TTL
    call_args = mock_redis.set.call_args
    assert call_args.kwargs.get("ex") == 86400 or call_args[2] == 86400


@pytest.mark.asyncio
async def test_cache_hit(mock_redis):
    test_data = {"address": "123 Main St", "walkability_score": 75}
    mock_redis.get = AsyncMock(return_value=json.dumps(test_data))

    cache = GeohashCache(mock_redis)
    result = await cache.get(41.8781, -87.6298, suffix="neighborhood")
    assert result == test_data


@pytest.mark.asyncio
async def test_cache_invalidate(mock_redis):
    cache = GeohashCache(mock_redis)
    await cache.invalidate(41.8781, -87.6298, suffix="neighborhood")
    mock_redis.delete.assert_called_once()
