from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from app.models import JobStatus


@dataclass(slots=True)
class JobEvent:
    job_id: str
    status: str
    progress: float
    done: int
    total: int
    message: str | None = None


def progress_fraction(done: int, total: int, status: JobStatus) -> float:
    if status == JobStatus.COMPLETED:
        return 1.0
    if total <= 0:
        return 0.0
    return done / total


class JobEventBus:
    """In-process pub/sub for job progress events.

    Subscribers register a queue before returning; publishers fan out to
    every subscriber. SSE handlers use this to stream live progress.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[JobEvent | None]]] = {}

    def subscribe(self, job_id: str) -> AsyncGenerator[JobEvent]:
        queue: asyncio.Queue[JobEvent | None] = asyncio.Queue()
        self._subs.setdefault(job_id, []).append(queue)
        return self._iterate(job_id, queue)

    async def _iterate(
        self, job_id: str, queue: asyncio.Queue[JobEvent | None]
    ) -> AsyncGenerator[JobEvent]:
        try:
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield event
        finally:
            subs = self._subs.get(job_id, [])
            if queue in subs:
                subs.remove(queue)
            if not subs and job_id in self._subs:
                del self._subs[job_id]

    async def publish(self, event: JobEvent) -> None:
        for q in list(self._subs.get(event.job_id, [])):
            q.put_nowait(event)

    async def publish_progress(
        self,
        job_id: str,
        status: JobStatus,
        done: int,
        total: int,
        message: str | None = None,
    ) -> None:
        await self.publish(
            JobEvent(
                job_id=job_id,
                status=status.value,
                progress=progress_fraction(done, total, status),
                done=done,
                total=total,
                message=message,
            )
        )

    async def close(self, job_id: str) -> None:
        for q in list(self._subs.get(job_id, [])):
            q.put_nowait(None)


_bus = JobEventBus()


def get_event_bus() -> JobEventBus:
    return _bus
