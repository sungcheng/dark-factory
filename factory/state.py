"""Session state persistence — resume crashed jobs."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from factory.github_client import SubTaskInfo
from factory.github_client import TaskInfo

LOG = logging.getLogger(__name__)

STATE_DIR = Path.home() / ".dark-factory" / "state"


@dataclass
class JobState:
    """Persisted state for a factory job."""

    repo_name: str
    issue_number: int
    working_dir: str = ""
    branch: str = ""
    status: str = "in_progress"
    pr_number: int | None = None
    tasks: list[TaskInfo] = field(default_factory=list)


def _state_path(repo_name: str, issue_number: int) -> Path:
    """Get the state file path for a job."""
    return STATE_DIR / f"{repo_name}-{issue_number}.json"


def save_state(state: JobState) -> None:
    """Persist job state to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _state_path(state.repo_name, state.issue_number)

    data = {
        "repo_name": state.repo_name,
        "issue_number": state.issue_number,
        "working_dir": state.working_dir,
        "branch": state.branch,
        "status": state.status,
        "pr_number": state.pr_number,
        "tasks": [asdict(t) for t in state.tasks],
    }

    path.write_text(json.dumps(data, indent=2))
    LOG.debug("Saved state to %s", path)


def load_state(repo_name: str, issue_number: int) -> JobState | None:
    """Load job state from disk. Returns None if no state exists."""
    path = _state_path(repo_name, issue_number)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        LOG.warning("Corrupt state file %s, ignoring", path)
        return None

    # Don't resume completed jobs
    if data.get("status") == "completed":
        return None

    tasks = [
        TaskInfo(
            id=t["id"],
            title=t["title"],
            description=t["description"],
            acceptance_criteria=t.get("acceptance_criteria", []),
            depends_on=t.get("depends_on", []),
            subtasks=[
                SubTaskInfo(
                    id=s["id"],
                    title=s["title"],
                    description=s.get("description", ""),
                    acceptance_criteria=s.get("acceptance_criteria", []),
                    depends_on=s.get("depends_on", []),
                    status=s.get("status", "pending"),
                    failure_issue=s.get("failure_issue"),
                )
                for s in t.get("subtasks", [])
            ],
            issue_number=t.get("issue_number"),
            status=t.get("status", "pending"),
            failure_issue=t.get("failure_issue"),
        )
        for t in data.get("tasks", [])
    ]

    return JobState(
        repo_name=data["repo_name"],
        issue_number=data["issue_number"],
        working_dir=data.get("working_dir", ""),
        branch=data.get("branch", ""),
        status=data.get("status", "in_progress"),
        pr_number=data.get("pr_number"),
        tasks=tasks,
    )


def clear_state(repo_name: str, issue_number: int) -> None:
    """Delete saved state for a job."""
    path = _state_path(repo_name, issue_number)
    if path.exists():
        path.unlink()
        LOG.info("Cleared state for %s#%d", repo_name, issue_number)


def cleanup_stale_state_files(repo_name: str, active_issue: int) -> int:
    """Remove in_progress state files for a repo except the active issue.

    Called at job start to clean up leftovers from killed/crashed runs.
    Returns the number of files removed.
    """
    prefix = f"{repo_name}-"
    removed = 0
    for path in STATE_DIR.glob(f"{prefix}*.json"):
        try:
            data = json.loads(path.read_text())
            issue_num = data.get("issue_number")
            if issue_num == active_issue:
                continue
            if data.get("status") == "in_progress":
                path.unlink()
                LOG.info(
                    "🧹 Removed stale state file: %s#%d",
                    repo_name,
                    issue_num,
                )
                removed += 1
        except Exception:
            pass
    return removed
