from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class Item:
    id: int
    name: str
    category: str
    value: float
    created_at: float


@dataclass(slots=True)
class ItemCreate:
    name: str
    category: str = ""
    value: float = 0.0


@dataclass(slots=True)
class Job:
    job_id: str
    kind: str
    status: JobStatus
    created_at: float
    updated_at: float
    progress: float = 0.0
    total: int = 0
    done: int = 0
    error: str | None = None
    meta: dict[str, object] | None = None
