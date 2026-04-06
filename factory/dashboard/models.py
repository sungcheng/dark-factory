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
    job_id: str = ""  # e.g., "weather-app#137"


class EventOut(BaseModel):
    """Event returned from API with server-generated fields."""

    id: str  # UUID, server-generated
    task_id: str
    event_type: str
    status: str
    message: str | None = None
    job_id: str = ""
    timestamp: datetime  # ISO 8601, server-generated, UTC

    model_config = ConfigDict(from_attributes=True)


class SubTaskOut(BaseModel):
    """Subtask within a parent task."""

    id: str
    title: str
    description: str
    status: str
    acceptance_criteria: list[str]
    depends_on: list[str]
    failure_issue: int | None = None

    model_config = ConfigDict(from_attributes=True)


class TaskOut(BaseModel):
    """Task returned from job detail endpoint."""

    id: str
    title: str
    description: str
    status: str  # "pending", "success", "failure", "in_progress"
    issue_number: int | None = None
    failure_issue: int | None = None
    acceptance_criteria: list[str]
    depends_on: list[str]
    subtasks: list[SubTaskOut] = []

    model_config = ConfigDict(from_attributes=True)


class JobSummary(BaseModel):
    """Job summary returned from GET /api/v1/jobs."""

    job_id: str  # {repo_name}#{issue_number}
    repo_name: str
    issue_number: int
    status: str  # "in_progress", "completed"
    task_count: int
    completed_task_count: int

    model_config = ConfigDict(from_attributes=True)


class JobDetail(BaseModel):
    """Full job details returned from GET /api/v1/jobs/{job_id}."""

    job_id: str  # {repo_name}#{issue_number}
    repo_name: str
    issue_number: int
    status: str  # "in_progress", "completed"
    working_dir: str
    branch: str
    pr_number: int | None = None
    tasks: list[TaskOut]

    model_config = ConfigDict(from_attributes=True)
