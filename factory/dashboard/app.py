from __future__ import annotations

from fastapi import APIRouter
from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI instance with /api/v1 router prefix
    """
    application = FastAPI(title="Dark Factory Dashboard")
    router = APIRouter(prefix="/api/v1")
    application.include_router(router)
    return application


app: FastAPI = create_app()
