from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from factory.dashboard.db import init_db
from factory.dashboard.routers.events import router as events_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management.

    On startup:
    - Call init_db() to initialize database

    On shutdown:
    - Cleanup if needed (currently a no-op)

    Args:
        app: FastAPI application instance

    Yields:
        None during app runtime
    """
    await init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Must include:
    - CORS middleware (allow_origins=["*"])
    - Lifespan context manager (calls init_db on startup)
    - /api/v1 APIRouter with events router registered

    Returns:
        FastAPI: Configured application instance
    """
    application = FastAPI(title="Dark Factory Dashboard", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(events_router)
    application.include_router(api_router)
    return application


app: FastAPI = create_app()
