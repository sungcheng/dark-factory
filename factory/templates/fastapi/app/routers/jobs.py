from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.db import connect
from app.deps import get_bus
from app.events import JobEvent, JobEventBus
from app.models import Job, JobStatus
from app.repositories.jobs import JobRepository
from app.schemas import JobOut

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _job_to_out(job: Job) -> JobOut:
    return JobOut(
        job_id=job.job_id,
        kind=job.kind,
        status=job.status.value,
        progress=job.progress,
        total=job.total,
        done=job.done,
        error=job.error,
        meta=job.meta,
    )


def _serialize_event(ev: JobEvent) -> bytes:
    payload = {
        "job_id": ev.job_id,
        "status": ev.status,
        "progress": ev.progress,
        "done": ev.done,
        "total": ev.total,
        "message": ev.message,
    }
    return f"data: {json.dumps(payload)}\n\n".encode()


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str) -> JobOut:
    async with connect() as conn:
        job = await JobRepository(conn).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_to_out(job)


@router.get("/{job_id}/events")
async def stream_job_events(
    job_id: str,
    request: Request,
    bus: JobEventBus = Depends(get_bus),
) -> StreamingResponse:
    subscription = bus.subscribe(job_id)

    async with connect() as conn:
        job = await JobRepository(conn).get(job_id)

    async def event_gen() -> AsyncIterator[bytes]:
        try:
            if job is None:
                return
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                yield _serialize_event(
                    JobEvent(
                        job_id=job.job_id,
                        status=job.status.value,
                        progress=job.progress,
                        done=job.done,
                        total=job.total,
                        message=job.error,
                    )
                )
                return
            async for ev in subscription:
                if await request.is_disconnected():
                    break
                yield _serialize_event(ev)
        finally:
            await subscription.aclose()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache"},
    )
