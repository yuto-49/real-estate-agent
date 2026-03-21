"""Pub/Sub event bus tests."""

import json
import pytest
from unittest.mock import AsyncMock

from services.pubsub import EventBus


@pytest.mark.asyncio
async def test_publish_event(mock_redis):
    mock_redis.publish = AsyncMock(return_value=1)
    bus = EventBus(mock_redis)
    result = await bus.publish("test:channel", {"type": "test", "data": "hello"})
    assert result == 1
    mock_redis.publish.assert_called_once()


@pytest.mark.asyncio
async def test_publish_negotiation_event(mock_redis):
    mock_redis.publish = AsyncMock(return_value=2)
    bus = EventBus(mock_redis)
    result = await bus.publish_negotiation_event(
        "neg-123", "offer.received", {"price": 300000}
    )
    assert result == 2
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "negotiation:neg-123"
    payload = json.loads(call_args[0][1])
    assert payload["type"] == "offer.received"


@pytest.mark.asyncio
async def test_publish_agent_event(mock_redis):
    mock_redis.publish = AsyncMock(return_value=1)
    bus = EventBus(mock_redis)
    result = await bus.publish_agent_event(
        "buyer", "user-456", "agent.response", {"text": "found 3 listings"}
    )
    assert result == 1
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "agent:buyer:user-456"


@pytest.mark.asyncio
async def test_publish_timeout(mock_redis):
    mock_redis.publish = AsyncMock(return_value=1)
    bus = EventBus(mock_redis)
    result = await bus.publish_timeout("neg-123", {"hours_remaining": 4})
    assert result == 1
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "system:timeout"
