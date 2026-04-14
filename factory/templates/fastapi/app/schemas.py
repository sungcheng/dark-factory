from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="", max_length=100)
    value: float = Field(default=0.0)


class ItemOut(BaseModel):
    id: int
    name: str
    category: str
    value: float
    created_at: float


class ListRequest(BaseModel):
    category: str | None = Field(default=None)
    cursor: int | None = Field(
        default=None,
        description="Opaque cursor; pass next_cursor from prior page",
    )
    limit: int = Field(default=50, ge=1, le=500)


class ListResponse(BaseModel):
    items: list[ItemOut]
    next_cursor: int | None = None


class JobOut(BaseModel):
    job_id: str
    kind: str
    status: str
    progress: float
    total: int
    done: int
    error: str | None = None
    meta: dict[str, Any] | None = None
