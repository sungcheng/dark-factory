from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException

from factory.dashboard.db import fetch_all_jobs
from factory.dashboard.db import fetch_events_for_job
from factory.dashboard.db import fetch_job
from factory.dashboard.models import EventOut
from factory.dashboard.models import JobDetail
from factory.dashboard.models import JobSummary
from factory.dashboard.models import SubTaskOut
from factory.dashboard.models import TaskOut

LOG = logging.getLogger(__name__)

STATE_DIR = Path.home() / ".dark-factory" / "state"

router = APIRouter()


def _parse_job_id(job_id: str) -> tuple[str, int]:
    """Parse job_id into (repo_name, issue_number).

    Args:
        job_id: Job identifier in format {repo_name}#{issue_number}

    Returns:
        Tuple of (repo_name, issue_number)

    Raises:
        HTTPException: If job_id format is invalid
    """
    parts = job_id.rsplit("#", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    try:
        return parts[0], int(parts[1])
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


def _load_job_data(job_id: str) -> dict[str, Any]:
    """Load raw job data from state file.

    Args:
        job_id: Job identifier in format {repo_name}#{issue_number}

    Returns:
        Parsed JSON data from state file

    Raises:
        HTTPException: If state file does not exist or is corrupt
    """
    repo_name, issue_number = _parse_job_id(job_id)
    path = STATE_DIR / f"{repo_name}-{issue_number}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    result: dict[str, Any] = data
    return result


def _list_all_jobs() -> list[dict[str, Any]]:
    """List all job state files.

    Returns:
        List of parsed JSON data from all state files,
        sorted by issue_number descending.
    """
    if not STATE_DIR.exists():
        return []

    jobs = []
    for path in STATE_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            jobs.append(data)
        except (json.JSONDecodeError, OSError):
            LOG.warning("Corrupt state file %s, skipping", path)
            continue

    jobs.sort(key=lambda j: j.get("issue_number", 0), reverse=True)
    return jobs


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs() -> list[JobSummary]:
    """List all jobs from state files + DB (for historical jobs)."""
    seen: set[str] = set()
    results: list[JobSummary] = []

    # Active jobs from state files (most up-to-date)
    for j in _list_all_jobs():
        job_id = f"{j['repo_name']}#{j['issue_number']}"
        seen.add(job_id)
        tasks = j.get("tasks", [])
        task_count = len(tasks)
        completed_count = sum(
            1 for t in tasks if t.get("status") in ("success", "completed")
        )
        failed_count = sum(1 for t in tasks if t.get("status") == "failed")
        # Derive status if state file is stale
        status = j.get("status", "in_progress")
        if status == "in_progress" and task_count > 0:
            if completed_count == task_count:
                status = "completed"
            elif failed_count > 0 and (completed_count + failed_count) == task_count:
                status = "failed"
        results.append(
            JobSummary(
                job_id=job_id,
                repo_name=j["repo_name"],
                issue_number=j["issue_number"],
                status=status,
                task_count=task_count,
                completed_task_count=completed_count,
            )
        )

    # Historical jobs from DB (not in state files)
    for j in await fetch_all_jobs():
        job_id = str(j["job_id"])
        if job_id in seen:
            continue
        issue_num = j["issue_number"]
        t_count = j["task_count"]
        c_count = j["completed_task_count"]
        results.append(
            JobSummary(
                job_id=job_id,
                repo_name=str(j["repo_name"]),
                issue_number=int(str(issue_num)),
                status=str(j["status"]),
                task_count=int(str(t_count)),
                completed_task_count=int(str(c_count)),
            )
        )

    return results


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(job_id: str) -> JobDetail:
    """Get full details for a single job including tasks."""
    data = _load_job_data(job_id)
    tasks = [
        TaskOut(
            id=t["id"],
            title=t["title"],
            description=t["description"],
            status=t.get("status", "pending"),
            issue_number=t.get("issue_number"),
            failure_issue=t.get("failure_issue"),
            acceptance_criteria=t.get("acceptance_criteria", []),
            depends_on=t.get("depends_on", []),
            subtasks=[
                SubTaskOut(
                    id=s["id"],
                    title=s["title"],
                    description=s.get("description", ""),
                    status=s.get("status", "pending"),
                    acceptance_criteria=s.get("acceptance_criteria", []),
                    depends_on=s.get("depends_on", []),
                    failure_issue=s.get("failure_issue"),
                )
                for s in t.get("subtasks", [])
            ],
        )
        for t in data.get("tasks", [])
    ]
    return JobDetail(
        job_id=job_id,
        repo_name=data["repo_name"],
        issue_number=data["issue_number"],
        status=data.get("status", "in_progress"),
        working_dir=data.get("working_dir", ""),
        branch=data.get("branch", ""),
        pr_number=data.get("pr_number"),
        tasks=tasks,
    )


@router.get("/jobs/{job_id}/log", response_model=list[EventOut])
async def get_job_log(job_id: str) -> list[EventOut]:
    """Get chronological event log for a job."""
    data = _load_job_data(job_id)
    # Collect all IDs: job_id itself, task IDs, and subtask IDs
    task_ids = [job_id]
    for t in data.get("tasks", []):
        task_ids.append(t["id"])
        for s in t.get("subtasks", []):
            task_ids.append(s["id"])

    # Get the job's created_at to scope fallback queries
    db_job = await fetch_job(job_id)
    created_at = str(db_job["created_at"]) if db_job else ""

    return await fetch_events_for_job(task_ids, job_id=job_id, since=created_at)
