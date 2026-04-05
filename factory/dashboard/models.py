from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict


class EventIn(BaseModel):
    """Event data received from orchestrator."""

    task_id: str
    event_type: str  # e.g., "task_started", "agent_completed", "error"
    status: str  # e.g., "pending", "success", "failure"
    message: str | None = None  # Optional description


class EventOut(BaseModel):
    """Event returned from API with server-generated fields."""

    id: str  # UUID, server-generated
    task_id: str
    event_type: str
    status: str
    message: str | None = None
    timestamp: datetime  # ISO 8601, server-generated, UTC

    model_config = ConfigDict(from_attributes=True)
