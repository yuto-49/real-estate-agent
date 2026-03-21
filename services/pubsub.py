"""Redis Pub/Sub event bus for real-time event distribution."""

import json
from typing import Any, Callable, Awaitable

import redis.asyncio as redis


class EventBus:
    """Wraps Redis pub/sub for typed event distribution.

    Channels:
    - negotiation:{id}   — events for a specific negotiation
    - agent:{type}:{user_id} — agent-specific events
    - system:timeout     — timeout notifications
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._pubsub: redis.client.PubSub | None = None

    async def publish(self, channel: str, event: dict) -> int:
        """Publish an event to a channel. Returns subscriber count."""
        return await self.redis.publish(channel, json.dumps(event))

    async def publish_negotiation_event(
        self, negotiation_id: str, event_type: str, payload: dict
    ) -> int:
        channel = f"negotiation:{negotiation_id}"
        return await self.publish(channel, {"type": event_type, "payload": payload})

    async def publish_agent_event(
        self, agent_type: str, user_id: str, event_type: str, payload: dict
    ) -> int:
        channel = f"agent:{agent_type}:{user_id}"
        return await self.publish(channel, {"type": event_type, "payload": payload})

    async def publish_timeout(self, negotiation_id: str, payload: dict) -> int:
        return await self.publish("system:timeout", {
            "type": "timeout",
            "negotiation_id": negotiation_id,
            "payload": payload,
        })

    async def subscribe(
        self,
        channels: list[str],
        callback: Callable[[str, dict], Awaitable[None]],
    ) -> None:
        """Subscribe to channels and invoke callback for each message."""
        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe(*channels)

        async for message in self._pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                data = json.loads(message["data"])
                await callback(channel, data)

    async def unsubscribe(self) -> None:
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.aclose()
            self._pubsub = None
