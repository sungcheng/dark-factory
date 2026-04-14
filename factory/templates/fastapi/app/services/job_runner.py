from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from app.db import connect
from app.events import JobEventBus
from app.models import JobStatus
from app.repositories.jobs import JobRepository

LOG = logging.getLogger(__name__)

JobFunc = Callable[[str, JobEventBus], Awaitable[None]]


class JobRunner:
    """Schedules async background jobs, tracks their tasks, publishes progress.

    Routers call `submit(kind, func)` to start a job. The runner:
      1. Creates a jobs row in PENDING status
      2. Spawns an asyncio task that runs `func(job_id, bus)`
      3. Marks the job COMPLETED or FAILED when the task finishes
      4. Cleans up tasks at shutdown
    """

    def __init__(self, bus: JobEventBus) -> None:
        self._bus = bus
        self._tasks: set[asyncio.Task[None]] = set()
        self._stopped = False

    async def start(self) -> None:
        self._stopped = False

    async def submit(self, kind: str, func: JobFunc) -> str:
        if self._stopped:
            raise RuntimeError("job runner is stopped")
        job_id = str(uuid.uuid4())
        async with connect() as conn:
            await JobRepository(conn).create(job_id, kind)

        task = asyncio.create_task(self._run(job_id, func))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job_id

    async def _run(self, job_id: str, func: JobFunc) -> None:
        async with connect() as conn:
            await JobRepository(conn).update_progress(job_id, status=JobStatus.RUNNING, done=0)
        await self._bus.publish_progress(job_id, JobStatus.RUNNING, 0, 0)

        try:
            await func(job_id, self._bus)
        except Exception as e:
            LOG.exception("job %s failed", job_id)
            async with connect() as conn:
                await JobRepository(conn).update_progress(
                    job_id, status=JobStatus.FAILED, done=0, error=str(e)
                )
            await self._bus.publish_progress(job_id, JobStatus.FAILED, 0, 0, message=str(e))
        finally:
            await self._bus.close(job_id)

    async def stop(self) -> None:
        self._stopped = True
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
