"""Background worker processing simulation jobs from the queue."""

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import MiroFishReport, MiroFishSeed
from intelligence.mirofish_client import MiroFishClient, MockMiroFishClient, CircuitBreakerOpen
from intelligence.seed_assembly import SeedAssemblyService
from services.job_queue import JobQueue
from services.logging import get_logger

logger = get_logger(__name__)


class SimulationWorker:
    """Processes simulation jobs from the Redis queue."""

    def __init__(
        self,
        job_queue: JobQueue,
        session_factory: async_sessionmaker,
        mirofish: MiroFishClient | MockMiroFishClient,
        seed_service: SeedAssemblyService,
        consumer_name: str = "worker-1",
    ):
        self.job_queue = job_queue
        self.session_factory = session_factory
        self.mirofish = mirofish
        self.seed_service = seed_service
        self.consumer_name = consumer_name
        self._running = False

    async def start(self):
        """Start the worker loop."""
        self._running = True
        await self.job_queue.initialize()
        logger.info("simulation_worker.started", consumer=self.consumer_name)

        while self._running:
            try:
                jobs = await self.job_queue.dequeue(self.consumer_name, count=1, block_ms=5000)
                for msg_id, job_data in jobs:
                    await self._process_job(msg_id, job_data)
            except Exception as e:
                logger.error("simulation_worker.error", error=str(e))
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False

    async def _process_job(self, msg_id: str, job_data: dict):
        """Process a single simulation job."""
        payload = job_data.get("payload", {})
        report_id = payload.get("report_id")
        user_id = payload.get("user_id")
        question = payload.get("question", "What is the best investment strategy?")
        ticks = payload.get("ticks", 30)

        logger.info("simulation_worker.processing", report_id=report_id, user_id=user_id)

        async with self.session_factory() as db:
            try:
                # Update report status to running
                result = await db.execute(
                    select(MiroFishReport).where(MiroFishReport.id == report_id)
                )
                report = result.scalar_one_or_none()
                if not report:
                    logger.error("simulation_worker.report_not_found", report_id=report_id)
                    await self.job_queue.ack(msg_id)
                    return

                report.status = "running"
                await db.commit()

                # Build seed
                seed_text = await self.seed_service.build_seed(user_id)

                # Save seed snapshot
                seed = MiroFishSeed(
                    user_id=user_id,
                    seed_text=seed_text,
                )
                db.add(seed)
                report.seed_hash = self.seed_service.seed_hash(seed_text)

                # Run simulation
                report_data = await self.mirofish.run_simulation(seed_text, question, ticks)

                report.report_json = report_data.raw_json
                report.status = "completed"
                await db.commit()

                logger.info("simulation_worker.completed", report_id=report_id)

            except CircuitBreakerOpen:
                logger.warning("simulation_worker.circuit_open", report_id=report_id)
                report.status = "failed"
                await db.commit()

            except Exception as e:
                logger.error("simulation_worker.failed", report_id=report_id, error=str(e))
                report.status = "failed"
                await db.commit()

        await self.job_queue.ack(msg_id)
