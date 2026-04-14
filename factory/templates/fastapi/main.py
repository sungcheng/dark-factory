from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.deps import get_job_runner
from app.routers.items import router as items_router
from app.routers.jobs import router as jobs_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    runner = get_job_runner()
    await runner.start()
    try:
        yield
    finally:
        await runner.stop()


app = FastAPI(
    title="{{SERVICE_NAME}}",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(items_router)
app.include_router(jobs_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
