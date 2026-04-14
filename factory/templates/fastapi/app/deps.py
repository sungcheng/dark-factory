from __future__ import annotations

from collections.abc import AsyncIterator

from app.db import connect
from app.events import JobEventBus, get_event_bus
from app.repositories.items import ItemRepository
from app.repositories.jobs import JobRepository
from app.services.item_service import ItemService
from app.services.job_runner import JobRunner

_job_runner: JobRunner | None = None


async def get_item_service() -> AsyncIterator[ItemService]:
    async with connect() as conn:
        yield ItemService(ItemRepository(conn))


async def get_job_repo() -> AsyncIterator[JobRepository]:
    async with connect() as conn:
        yield JobRepository(conn)


def get_job_runner() -> JobRunner:
    global _job_runner
    if _job_runner is None:
        _job_runner = JobRunner(get_event_bus())
    return _job_runner


def get_bus() -> JobEventBus:
    return get_event_bus()
