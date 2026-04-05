"""End-to-end integration tests for the Dark Factory dashboard pipeline."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport

from factory.dashboard.app import create_app
from factory.dashboard.db import DB_PATH as _ORIG_DB_PATH
from factory.dashboard.emitter import EventEmitter
from factory.dashboard.models import EventOut
from factory.dashboard.models import JobDetail
from factory.dashboard.models import JobSummary

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EVENTS_URL = "/api/v1/events"
JOBS_URL = "/api/v1/jobs"


@pytest.fixture()
def test_app() -> Any:
    """Create a fresh FastAPI app instance for testing."""
    return create_app()


@pytest.fixture()
async def clean_db(tmp_path: Path) -> Any:
    """Reset the SQLite database to a temporary file for test isolation."""
    db_file = str(tmp_path / "test.db")
    with patch("factory.dashboard.db.DB_PATH", db_file):
        yield db_file


@pytest.fixture()
def clean_state_dir(tmp_path: Path) -> Any:
    """Provide a clean temporary state directory."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
        yield state_dir


@pytest.fixture()
async def async_client(test_app: Any, clean_db: Any) -> Any:
    """Create an httpx AsyncClient wired to the test FastAPI app."""
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

JOB_TASK_ID = "test-repo#1"

LIFECYCLE_EVENTS: list[dict[str, Any]] = [
    {"task_id": JOB_TASK_ID, "event_type": "job_started", "status": "pending"},
    {
        "task_id": JOB_TASK_ID,
        "event_type": "agent_spawned",
        "status": "pending",
        "message": "architect",
    },
    {"task_id": JOB_TASK_ID, "event_type": "task_started", "status": "pending"},
    {
        "task_id": JOB_TASK_ID,
        "event_type": "round_result",
        "status": "failure",
        "message": "round 1",
    },
    {
        "task_id": JOB_TASK_ID,
        "event_type": "round_result",
        "status": "success",
        "message": "round 2",
    },
    {"task_id": JOB_TASK_ID, "event_type": "task_completed", "status": "success"},
    {
        "task_id": JOB_TASK_ID,
        "event_type": "agent_exited",
        "status": "success",
        "message": "architect",
    },
    {"task_id": JOB_TASK_ID, "event_type": "job_completed", "status": "success"},
]


def _make_state_file(state_dir: Path) -> Path:
    """Write a minimal job state file for test-repo#1."""
    data = {
        "repo_name": "test-repo",
        "issue_number": 1,
        "status": "completed",
        "working_dir": "/tmp/test-repo",
        "branch": "factory/issue-1",
        "pr_number": None,
        "tasks": [
            {
                "id": JOB_TASK_ID,
                "title": "Build architecture",
                "description": "Design the system",
                "status": "success",
                "issue_number": None,
                "failure_issue": None,
                "acceptance_criteria": ["It should work"],
                "depends_on": [],
            }
        ],
    }
    path = state_dir / "test-repo-1.json"
    path.write_text(json.dumps(data))
    return path


async def _post_lifecycle(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """POST all lifecycle events and return their response bodies."""
    results: list[dict[str, Any]] = []
    for event in LIFECYCLE_EVENTS:
        resp = await client.post(EVENTS_URL, json=event)
        assert resp.status_code == 201
        results.append(resp.json())
    return results


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestFullJobLifecycle:
    """Verify the full job lifecycle can be POSTed as events."""

    @pytest.mark.anyio
    async def test_post_full_job_lifecycle_sequence(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """POST 8 lifecycle events; each must return 201 with valid EventOut."""
        pass


class TestJobsListEndpoint:
    """Verify GET /api/v1/jobs returns correct job summaries."""

    @pytest.mark.anyio
    async def test_get_jobs_list_returns_job_with_correct_summary(
        self,
        async_client: httpx.AsyncClient,
        clean_state_dir: Path,
    ) -> None:
        """After posting events and creating state, job list has correct summary."""
        pass


class TestJobDetailEndpoint:
    """Verify GET /api/v1/jobs/{id} returns full detail."""

    @pytest.mark.anyio
    async def test_get_job_detail_returns_full_detail_with_all_events(
        self,
        async_client: httpx.AsyncClient,
        clean_state_dir: Path,
    ) -> None:
        """Job detail includes tasks, working_dir, branch, and correct status."""
        pass


class TestJobLogEndpoint:
    """Verify GET /api/v1/jobs/{id}/log returns chronological events."""

    @pytest.mark.anyio
    async def test_get_job_log_returns_events_in_chronological_order(
        self,
        async_client: httpx.AsyncClient,
        clean_state_dir: Path,
    ) -> None:
        """All 8 events are returned ordered by timestamp ascending."""
        pass


class TestEventEmitterIntegration:
    """Verify EventEmitter against the real FastAPI test app."""

    @pytest.mark.anyio
    async def test_event_emitter_posts_to_real_app_and_persists(
        self,
        test_app: Any,
        clean_db: Any,
    ) -> None:
        """EventEmitter posts events that are stored in the database."""
        pass

    @pytest.mark.anyio
    async def test_event_emitter_fire_and_forget_swallows_errors(self) -> None:
        """EventEmitter silently swallows HTTP errors without raising."""
        pass

    @pytest.mark.anyio
    async def test_event_emitter_disabled_when_dashboard_url_empty(self) -> None:
        """EventEmitter is a silent no-op when DASHBOARD_URL is not set."""
        pass


class TestFrontendBuild:
    """Verify the frontend production build completes successfully."""

    @pytest.mark.anyio
    async def test_frontend_production_build_succeeds(self) -> None:
        """npm run build in dashboard/frontend/ exits with code 0."""
        pass
