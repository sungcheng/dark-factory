"""Tests for GET /api/v1/jobs endpoints, models, and app wiring."""

from __future__ import annotations

import json
import tempfile
import uuid
from datetime import UTC
from datetime import datetime
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import aiosqlite
import pytest
from httpx import ASGITransport
from httpx import AsyncClient

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job_state(
    *,
    repo_name: str = "test-repo",
    issue_number: int = 42,
    status: str = "in_progress",
    working_dir: str = "/tmp/test-repo",
    branch: str = "factory/issue-42",
    pr_number: int | None = None,
    tasks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "repo_name": repo_name,
        "issue_number": issue_number,
        "status": status,
        "working_dir": working_dir,
        "branch": branch,
        "pr_number": pr_number,
        "tasks": tasks or [],
    }


def _make_task(
    *,
    task_id: str = "task-1",
    title: str = "Test task",
    description: str = "A test task",
    status: str = "pending",
    issue_number: int | None = None,
    failure_issue: int | None = None,
    acceptance_criteria: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": task_id,
        "title": title,
        "description": description,
        "status": status,
        "issue_number": issue_number,
        "failure_issue": failure_issue,
        "acceptance_criteria": acceptance_criteria or ["It should work"],
        "depends_on": depends_on or [],
    }


def _write_state_file(state_dir: Path, state: dict[str, Any]) -> Path:
    """Write a job state JSON file into state_dir."""
    repo_name = state["repo_name"]
    issue_number = state["issue_number"]
    path = state_dir / f"{repo_name}-{issue_number}.json"
    path.write_text(json.dumps(state))
    return path


# ---------------------------------------------------------------------------
# Pydantic model tests (no I/O)
# ---------------------------------------------------------------------------


class TestJobModels:
    """JobSummary, JobDetail, TaskOut Pydantic models have the correct fields."""

    def test_job_summary_importable(self) -> None:
        """JobSummary must be importable from factory.dashboard.models."""
        from factory.dashboard.models import JobSummary  # noqa: F401

    def test_job_detail_importable(self) -> None:
        """JobDetail must be importable from factory.dashboard.models."""
        from factory.dashboard.models import JobDetail  # noqa: F401

    def test_task_out_importable(self) -> None:
        """TaskOut must be importable from factory.dashboard.models."""
        from factory.dashboard.models import TaskOut  # noqa: F401

    def test_job_summary_required_fields(self) -> None:
        """JobSummary must accept all required fields."""
        from factory.dashboard.models import JobSummary

        summary = JobSummary(
            job_id="my-repo#7",
            repo_name="my-repo",
            issue_number=7,
            status="in_progress",
            task_count=3,
            completed_task_count=1,
        )
        assert summary.job_id == "my-repo#7"
        assert summary.repo_name == "my-repo"
        assert summary.issue_number == 7
        assert summary.status == "in_progress"
        assert summary.task_count == 3
        assert summary.completed_task_count == 1

    def test_job_summary_from_attributes(self) -> None:
        """JobSummary must have model_config = ConfigDict(from_attributes=True)."""
        from factory.dashboard.models import JobSummary

        assert JobSummary.model_config.get("from_attributes") is True

    def test_job_detail_required_fields(self) -> None:
        """JobDetail must accept all required fields including tasks list."""
        from factory.dashboard.models import JobDetail

        detail = JobDetail(
            job_id="repo#1",
            repo_name="repo",
            issue_number=1,
            status="completed",
            working_dir="/tmp/repo",
            branch="main",
            pr_number=99,
            tasks=[],
        )
        assert detail.job_id == "repo#1"
        assert detail.pr_number == 99
        assert detail.tasks == []

    def test_job_detail_pr_number_optional(self) -> None:
        """JobDetail.pr_number must be optional and default to None."""
        from factory.dashboard.models import JobDetail

        detail = JobDetail(
            job_id="repo#1",
            repo_name="repo",
            issue_number=1,
            status="in_progress",
            working_dir="/tmp/repo",
            branch="main",
            tasks=[],
        )
        assert detail.pr_number is None

    def test_task_out_required_fields(self) -> None:
        """TaskOut must accept all required fields."""
        from factory.dashboard.models import TaskOut

        task = TaskOut(
            id="task-abc",
            title="Do something",
            description="Full description",
            status="success",
            acceptance_criteria=["It works"],
            depends_on=[],
        )
        assert task.id == "task-abc"
        assert task.status == "success"
        assert task.issue_number is None
        assert task.failure_issue is None

    def test_task_out_from_attributes(self) -> None:
        """TaskOut must have model_config = ConfigDict(from_attributes=True)."""
        from factory.dashboard.models import TaskOut

        assert TaskOut.model_config.get("from_attributes") is True


# ---------------------------------------------------------------------------
# Router file-structure tests
# ---------------------------------------------------------------------------


class TestJobsRouterFileExists:
    """factory/dashboard/routers/jobs.py exists and is importable."""

    def test_jobs_router_file_exists(self) -> None:
        """factory/dashboard/routers/jobs.py must be a file on disk."""
        path = PROJECT_ROOT / "factory" / "dashboard" / "routers" / "jobs.py"
        assert path.is_file(), f"Missing file: {path}"

    def test_jobs_router_importable(self) -> None:
        """factory.dashboard.routers.jobs must be importable."""
        from factory.dashboard.routers import jobs  # noqa: F401

    def test_jobs_router_exposes_router(self) -> None:
        """factory.dashboard.routers.jobs must expose an APIRouter named `router`."""
        from fastapi import APIRouter

        from factory.dashboard.routers.jobs import router

        assert isinstance(router, APIRouter)


# ---------------------------------------------------------------------------
# GET /api/v1/jobs — list all jobs
# ---------------------------------------------------------------------------


async def _empty_db_jobs() -> list[dict[str, object]]:
    return []


class TestListJobsEndpoint:
    """GET /api/v1/jobs behaves according to acceptance criteria."""

    @pytest.fixture(autouse=True)
    def _mock_db(self) -> Generator[None, None, None]:  # type: ignore[type-arg]
        """Isolate tests from the real DB."""
        with patch(
            "factory.dashboard.routers.jobs.fetch_all_jobs",
            new=_empty_db_jobs,
        ):
            yield

    @pytest.mark.anyio
    async def test_list_jobs_returns_200(self) -> None:
        """GET /api/v1/jobs must return 200."""
        from factory.dashboard.app import app

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs")
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_list_jobs_empty_when_no_jobs_exist(self) -> None:
        """GET /api/v1/jobs must return an empty list when no state files exist."""
        from factory.dashboard.app import app

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.anyio
    async def test_list_jobs_returns_job_summary_list(self) -> None:
        """GET /api/v1/jobs must return a list of JobSummary objects."""
        from factory.dashboard.app import app

        state = _make_job_state(
            repo_name="my-repo",
            issue_number=10,
            status="in_progress",
            tasks=[
                _make_task(task_id="t-1", status="success"),
                _make_task(task_id="t-2"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            _write_state_file(state_dir, state)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        job = data[0]
        assert job["job_id"] == "my-repo#10"
        assert job["repo_name"] == "my-repo"
        assert job["issue_number"] == 10
        assert job["status"] == "in_progress"
        assert job["task_count"] == 2
        assert job["completed_task_count"] == 1

    @pytest.mark.anyio
    async def test_list_jobs_sorted_most_recent_first(self) -> None:
        """GET /api/v1/jobs must return jobs sorted by issue_number descending."""
        from factory.dashboard.app import app

        state_old = _make_job_state(repo_name="repo", issue_number=1)
        state_new = _make_job_state(repo_name="repo", issue_number=50)
        state_mid = _make_job_state(repo_name="repo", issue_number=25)

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            _write_state_file(state_dir, state_old)
            _write_state_file(state_dir, state_new)
            _write_state_file(state_dir, state_mid)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        issue_numbers = [j["issue_number"] for j in data]
        assert issue_numbers == [50, 25, 1], (
            f"Jobs not sorted most-recent-first: {issue_numbers}"
        )

    @pytest.mark.anyio
    async def test_list_jobs_response_is_json_array(self) -> None:
        """GET /api/v1/jobs response must be a JSON array."""
        from factory.dashboard.app import app

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs")

        assert response.headers["content-type"].startswith("application/json")
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.anyio
    async def test_list_jobs_job_summary_fields_present(self) -> None:
        """Each JobSummary in the list must contain all required fields."""
        from factory.dashboard.app import app

        state = _make_job_state(repo_name="repo", issue_number=5)

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            _write_state_file(state_dir, state)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs")

        data = response.json()
        assert len(data) == 1
        job = data[0]
        for field in (
            "job_id",
            "repo_name",
            "issue_number",
            "status",
            "task_count",
            "completed_task_count",
        ):
            assert field in job, f"JobSummary missing field: {field}"

    @pytest.mark.anyio
    async def test_list_jobs_ignores_corrupt_state_files(self) -> None:
        """GET /api/v1/jobs must ignore corrupt state files without crashing."""
        from factory.dashboard.app import app

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            # Write a corrupt JSON file
            (state_dir / "corrupt-1.json").write_text("{not valid json")
            # Write a valid state file
            _write_state_file(
                state_dir, _make_job_state(repo_name="good-repo", issue_number=1)
            )
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()
        # Only valid state file should be returned
        assert len(data) == 1
        assert data[0]["repo_name"] == "good-repo"


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{job_id} — job detail
# ---------------------------------------------------------------------------


class TestGetJobDetailEndpoint:
    """GET /api/v1/jobs/{job_id} behaves according to acceptance criteria."""

    @pytest.mark.anyio
    async def test_get_job_returns_200(self) -> None:
        """GET /api/v1/jobs/{job_id} must return 200 when the job exists."""
        from factory.dashboard.app import app

        state = _make_job_state(repo_name="my-repo", issue_number=7)

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            _write_state_file(state_dir, state)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs/my-repo%237")

        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_get_job_returns_job_detail(self) -> None:
        """GET /api/v1/jobs/{job_id} must return a JobDetail object."""
        from factory.dashboard.app import app

        task = _make_task(
            task_id="t-abc",
            title="My Task",
            description="Do something useful",
            status="success",
            issue_number=99,
            acceptance_criteria=["It does something"],
            depends_on=[],
        )
        state = _make_job_state(
            repo_name="dark-factory",
            issue_number=3,
            status="completed",
            working_dir="/home/user/dark-factory",
            branch="factory/issue-3",
            pr_number=55,
            tasks=[task],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            _write_state_file(state_dir, state)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs/dark-factory%233")

        assert response.status_code == 200
        data = response.json()

        assert data["job_id"] == "dark-factory#3"
        assert data["repo_name"] == "dark-factory"
        assert data["issue_number"] == 3
        assert data["status"] == "completed"
        assert data["working_dir"] == "/home/user/dark-factory"
        assert data["branch"] == "factory/issue-3"
        assert data["pr_number"] == 55
        assert isinstance(data["tasks"], list)
        assert len(data["tasks"]) == 1

        t = data["tasks"][0]
        assert t["id"] == "t-abc"
        assert t["title"] == "My Task"
        assert t["description"] == "Do something useful"
        assert t["status"] == "success"
        assert t["issue_number"] == 99

    @pytest.mark.anyio
    async def test_get_job_returns_404_when_not_found(self) -> None:
        """GET /api/v1/jobs/{job_id} must return 404 when the job does not exist."""
        from factory.dashboard.app import app

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs/nonexistent%231")

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_get_job_404_has_detail_message(self) -> None:
        """GET /api/v1/jobs/{job_id} 404 response must include a 'detail' message."""
        from factory.dashboard.app import app

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs/missing-repo%2399")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data, "404 response must include 'detail' field"
        assert data["detail"], "404 detail message must not be empty"

    @pytest.mark.anyio
    async def test_get_job_tasks_have_required_fields(self) -> None:
        """Each TaskOut in JobDetail.tasks must have all required fields."""
        from factory.dashboard.app import app

        task = _make_task(task_id="t-1", title="T1", description="desc")
        state = _make_job_state(repo_name="repo", issue_number=1, tasks=[task])

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            _write_state_file(state_dir, state)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs/repo%231")

        data = response.json()
        task_data = data["tasks"][0]
        for field in (
            "id",
            "title",
            "description",
            "status",
            "acceptance_criteria",
            "depends_on",
        ):
            assert field in task_data, f"TaskOut missing field: {field}"

    @pytest.mark.anyio
    async def test_get_job_with_no_tasks(self) -> None:
        """GET /api/v1/jobs/{job_id} must work when the job has no tasks."""
        from factory.dashboard.app import app

        state = _make_job_state(repo_name="repo", issue_number=2, tasks=[])

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            _write_state_file(state_dir, state)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs/repo%232")

        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []

    @pytest.mark.anyio
    async def test_get_job_pr_number_can_be_null(self) -> None:
        """GET /api/v1/jobs/{job_id} must return null pr_number when not set."""
        from factory.dashboard.app import app

        state = _make_job_state(repo_name="repo", issue_number=3, pr_number=None)

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            _write_state_file(state_dir, state)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs/repo%233")

        assert response.status_code == 200
        assert response.json()["pr_number"] is None

    @pytest.mark.anyio
    async def test_get_job_detail_fields_present(self) -> None:
        """JobDetail response must contain all required fields."""
        from factory.dashboard.app import app

        state = _make_job_state(repo_name="repo", issue_number=4)

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            _write_state_file(state_dir, state)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs/repo%234")

        data = response.json()
        for field in (
            "job_id",
            "repo_name",
            "issue_number",
            "status",
            "working_dir",
            "branch",
            "tasks",
        ):
            assert field in data, f"JobDetail missing field: {field}"


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{job_id}/log — event log
# ---------------------------------------------------------------------------


class TestGetJobLogEndpoint:
    """GET /api/v1/jobs/{job_id}/log behaves according to acceptance criteria."""

    @pytest.mark.anyio
    async def test_get_job_log_returns_200(self) -> None:
        """GET /api/v1/jobs/{job_id}/log must return 200 when job exists."""
        from factory.dashboard.app import app

        task = _make_task(task_id="task-log-1")
        state = _make_job_state(repo_name="log-repo", issue_number=1, tasks=[task])

        with (
            tempfile.TemporaryDirectory() as tmp_state_dir,
            tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db,
        ):
            state_dir = Path(tmp_state_dir)
            db_path = tmp_db.name
            _write_state_file(state_dir, state)

            import factory.dashboard.db as db_module

            original_db_path = db_module.DB_PATH
            db_module.DB_PATH = db_path
            try:
                await db_module.init_db()
                with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.get("/api/v1/jobs/log-repo%231/log")
            finally:
                db_module.DB_PATH = original_db_path

        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_get_job_log_returns_list(self) -> None:
        """GET /api/v1/jobs/{job_id}/log must return a JSON array."""
        from factory.dashboard.app import app

        task = _make_task(task_id="task-list-1")
        state = _make_job_state(repo_name="list-repo", issue_number=1, tasks=[task])

        with (
            tempfile.TemporaryDirectory() as tmp_state_dir,
            tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db,
        ):
            state_dir = Path(tmp_state_dir)
            db_path = tmp_db.name
            _write_state_file(state_dir, state)

            import factory.dashboard.db as db_module

            original_db_path = db_module.DB_PATH
            db_module.DB_PATH = db_path
            try:
                await db_module.init_db()
                with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.get("/api/v1/jobs/list-repo%231/log")
            finally:
                db_module.DB_PATH = original_db_path

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.anyio
    async def test_get_job_log_empty_when_no_events(self) -> None:
        """GET /api/v1/jobs/{job_id}/log must return empty list when no events exist."""
        from factory.dashboard.app import app

        task = _make_task(task_id="task-no-events")
        state = _make_job_state(
            repo_name="empty-log-repo", issue_number=1, tasks=[task]
        )

        with (
            tempfile.TemporaryDirectory() as tmp_state_dir,
            tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db,
        ):
            state_dir = Path(tmp_state_dir)
            db_path = tmp_db.name
            _write_state_file(state_dir, state)

            import factory.dashboard.db as db_module

            original_db_path = db_module.DB_PATH
            db_module.DB_PATH = db_path
            try:
                await db_module.init_db()
                with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.get(
                            "/api/v1/jobs/empty-log-repo%231/log"
                        )
            finally:
                db_module.DB_PATH = original_db_path

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.anyio
    async def test_get_job_log_returns_events_ordered_by_timestamp(self) -> None:
        """GET /api/v1/jobs/{job_id}/log must return events ordered by timestamp asc."""
        from factory.dashboard.app import app
        from factory.dashboard.models import EventIn

        task_id = "task-ordered-" + str(uuid.uuid4())[:8]
        task = _make_task(task_id=task_id)
        state = _make_job_state(repo_name="ordered-repo", issue_number=1, tasks=[task])

        with (
            tempfile.TemporaryDirectory() as tmp_state_dir,
            tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db,
        ):
            state_dir = Path(tmp_state_dir)
            db_path = tmp_db.name
            _write_state_file(state_dir, state)

            import factory.dashboard.db as db_module

            original_db_path = db_module.DB_PATH
            db_module.DB_PATH = db_path
            try:
                await db_module.init_db()
                # Insert events with a small time gap to ensure ordering is deterministic
                for event_type in ["task_started", "agent_completed", "task_done"]:
                    await db_module.insert_event(
                        EventIn(
                            task_id=task_id, event_type=event_type, status="pending"
                        )
                    )

                with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.get("/api/v1/jobs/ordered-repo%231/log")
            finally:
                db_module.DB_PATH = original_db_path

        assert response.status_code == 200
        events = response.json()
        assert len(events) == 3

        timestamps = [datetime.fromisoformat(e["timestamp"]) for e in events]
        assert timestamps == sorted(timestamps), (
            "Events must be returned in ascending timestamp order"
        )

    @pytest.mark.anyio
    async def test_get_job_log_event_fields_present(self) -> None:
        """Each EventOut in the log must have all required fields."""
        from factory.dashboard.app import app
        from factory.dashboard.models import EventIn

        task_id = "task-fields-" + str(uuid.uuid4())[:8]
        task = _make_task(task_id=task_id)
        state = _make_job_state(repo_name="fields-repo", issue_number=1, tasks=[task])

        with (
            tempfile.TemporaryDirectory() as tmp_state_dir,
            tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db,
        ):
            state_dir = Path(tmp_state_dir)
            db_path = tmp_db.name
            _write_state_file(state_dir, state)

            import factory.dashboard.db as db_module

            original_db_path = db_module.DB_PATH
            db_module.DB_PATH = db_path
            try:
                await db_module.init_db()
                await db_module.insert_event(
                    EventIn(
                        task_id=task_id,
                        event_type="task_started",
                        status="pending",
                        message="starting up",
                    )
                )

                with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.get("/api/v1/jobs/fields-repo%231/log")
            finally:
                db_module.DB_PATH = original_db_path

        events = response.json()
        assert len(events) == 1
        event = events[0]
        for field in ("id", "task_id", "event_type", "status", "timestamp"):
            assert field in event, f"EventOut missing field: {field}"
        assert event["event_type"] == "task_started"
        assert event["status"] == "pending"
        assert event["message"] == "starting up"

    @pytest.mark.anyio
    async def test_get_job_log_returns_404_when_job_not_found(self) -> None:
        """GET /api/v1/jobs/{job_id}/log must return 404 when the job does not exist."""
        from factory.dashboard.app import app

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs/nonexistent-repo%231/log")

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_get_job_log_404_has_detail_message(self) -> None:
        """GET /api/v1/jobs/{job_id}/log 404 must include a 'detail' field."""
        from factory.dashboard.app import app

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs/ghost%2342/log")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data, "404 log response must include 'detail' field"
        assert data["detail"], "404 detail message must not be empty"

    @pytest.mark.anyio
    async def test_get_job_log_only_returns_events_for_job_tasks(self) -> None:
        """GET /api/v1/jobs/{job_id}/log must only return events for the job's tasks."""
        from factory.dashboard.app import app
        from factory.dashboard.models import EventIn

        task_id_mine = "task-mine-" + str(uuid.uuid4())[:8]
        task_id_other = "task-other-" + str(uuid.uuid4())[:8]

        my_task = _make_task(task_id=task_id_mine)
        state = _make_job_state(
            repo_name="scoped-repo", issue_number=1, tasks=[my_task]
        )

        with (
            tempfile.TemporaryDirectory() as tmp_state_dir,
            tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db,
        ):
            state_dir = Path(tmp_state_dir)
            db_path = tmp_db.name
            _write_state_file(state_dir, state)

            import factory.dashboard.db as db_module

            original_db_path = db_module.DB_PATH
            db_module.DB_PATH = db_path
            try:
                await db_module.init_db()
                # Insert event for MY task
                await db_module.insert_event(
                    EventIn(
                        task_id=task_id_mine,
                        event_type="task_started",
                        status="pending",
                    )
                )
                # Insert event for ANOTHER task (should not appear)
                await db_module.insert_event(
                    EventIn(
                        task_id=task_id_other,
                        event_type="task_started",
                        status="pending",
                    )
                )

                with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.get("/api/v1/jobs/scoped-repo%231/log")
            finally:
                db_module.DB_PATH = original_db_path

        assert response.status_code == 200
        events = response.json()
        assert len(events) == 1
        assert events[0]["task_id"] == task_id_mine


# ---------------------------------------------------------------------------
# App wiring: jobs router registered in app.py
# ---------------------------------------------------------------------------


class TestJobsAppWiring:
    """Jobs router is properly registered in app.py."""

    def test_jobs_router_imported_in_app(self) -> None:
        """factory.dashboard.app must import the jobs router."""
        import sys

        import factory.dashboard.app  # noqa: F401

        app_module = sys.modules["factory.dashboard.app"]
        # If the import fails, the test above would have raised ImportError
        assert hasattr(app_module, "app"), "factory.dashboard.app must define 'app'"

    def test_list_jobs_route_registered(self) -> None:
        """GET /api/v1/jobs must appear in the app's route table."""
        from factory.dashboard.app import app

        routes = app.routes
        get_jobs_routes = [
            r
            for r in routes
            if hasattr(r, "path")
            and r.path == "/api/v1/jobs"
            and hasattr(r, "methods")
            and "GET" in (r.methods or set())
        ]
        assert len(get_jobs_routes) >= 1, (
            "No GET /api/v1/jobs route found in app.routes"
        )

    def test_get_job_detail_route_registered(self) -> None:
        """GET /api/v1/jobs/{job_id} must appear in the app's route table."""
        from factory.dashboard.app import app

        routes = app.routes
        get_job_routes = [
            r
            for r in routes
            if hasattr(r, "path")
            and r.path == "/api/v1/jobs/{job_id}"
            and hasattr(r, "methods")
            and "GET" in (r.methods or set())
        ]
        assert len(get_job_routes) >= 1, (
            "No GET /api/v1/jobs/{job_id} route found in app.routes"
        )

    def test_get_job_log_route_registered(self) -> None:
        """GET /api/v1/jobs/{job_id}/log must appear in the app's route table."""
        from factory.dashboard.app import app

        routes = app.routes
        get_log_routes = [
            r
            for r in routes
            if hasattr(r, "path")
            and r.path == "/api/v1/jobs/{job_id}/log"
            and hasattr(r, "methods")
            and "GET" in (r.methods or set())
        ]
        assert len(get_log_routes) >= 1, (
            "No GET /api/v1/jobs/{job_id}/log route found in app.routes"
        )

    @pytest.mark.anyio
    async def test_jobs_router_responds_to_requests(self) -> None:
        """The jobs router must be callable through the FastAPI app."""
        from factory.dashboard.app import app

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            with patch("factory.dashboard.routers.jobs.STATE_DIR", state_dir):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/v1/jobs")

        # Must not be 404 (route not found) or 500 (crash)
        assert response.status_code not in (404, 500), (
            f"Jobs router not properly wired: got {response.status_code}"
        )
