"""Redis Streams-based job queue for async task processing."""

import json
import time
from typing import Any

import redis.asyncio as redis

from services.logging import get_logger

logger = get_logger(__name__)


class JobQueue:
    """Simple job queue built on Redis Streams."""

    STREAM_KEY = "jobs:simulations"
    GROUP_NAME = "simulation_workers"

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def initialize(self):
        """Create the consumer group if it doesn't exist."""
        try:
            await self.redis.xgroup_create(
                self.STREAM_KEY, self.GROUP_NAME, id="0", mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def enqueue(self, job_type: str, payload: dict) -> str:
        """Add a job to the queue. Returns the stream message ID."""
        message = {
            "job_type": job_type,
            "payload": json.dumps(payload),
            "enqueued_at": str(time.time()),
        }
        msg_id = await self.redis.xadd(self.STREAM_KEY, message)
        logger.info("job.enqueued", job_type=job_type, msg_id=msg_id)
        return msg_id

    async def dequeue(
        self, consumer_name: str, count: int = 1, block_ms: int = 5000
    ) -> list[tuple[str, dict]]:
        """Read pending jobs for a consumer. Returns list of (msg_id, data) tuples."""
        results = await self.redis.xreadgroup(
            self.GROUP_NAME,
            consumer_name,
            {self.STREAM_KEY: ">"},
            count=count,
            block=block_ms,
        )
        jobs = []
        if results:
            for stream_name, messages in results:
                for msg_id, data in messages:
                    payload = json.loads(data.get("payload", "{}"))
                    jobs.append((msg_id, {
                        "job_type": data.get("job_type", ""),
                        "payload": payload,
                        "enqueued_at": data.get("enqueued_at", ""),
                    }))
        return jobs

    async def ack(self, msg_id: str):
        """Acknowledge a processed job."""
        await self.redis.xack(self.STREAM_KEY, self.GROUP_NAME, msg_id)
        logger.info("job.acked", msg_id=msg_id)

    async def pending_count(self) -> int:
        """Get the number of pending messages in the stream."""
        info = await self.redis.xinfo_stream(self.STREAM_KEY)
        return info.get("length", 0)
