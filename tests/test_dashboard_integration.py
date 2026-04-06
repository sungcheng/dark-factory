"""Integration tests for the Dark Factory dashboard pipeline.

Phase 1 (Red): Covers the full end-to-end pipeline:
- POST a complete job lifecycle sequence (8+ events), each returns 201
- GET /api/v1/jobs returns the job with correct task_count, completed_count, status
- GET /api/v1/jobs/{id} returns full detail with tasks
- GET /api/v1/jobs/{id}/log returns events in chronological order
- EventEmitter posts to the real FastAPI test app and verifies DB storage
- EventEmitter fire-and-forget behaviour (errors swallowed, never raised)
- Frontend production build succeeds (npm run build exits 0)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Generator
from unittest.mock import patch
from urllib.parse import quote

import httpx
import pytest
from httpx import ASGITransport
from httpx import AsyncClient

PROJECT_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

REPO_NAME = "test-repo"
ISSUE_NUMBER = 42
JOB_ID = f"{REPO_NAME}#{ISSUE_NUMBER}"
# URL-safe version: # must be percent-encoded so httpx doesn't strip it as a fragment
JOB_ID_PATH = quote(JOB_ID, safe="")  # "test-repo%2342"
TASK_ID = "task-arch-001"

# 8-event lifecycle sequence simulating a complete job
LIFECYCLE_EVENTS: list[dict[str, object]] = [
    {
        "task_id": JOB_ID,
        "event_type": "job_started",
        "status": "pending",
        "job_id": JOB_ID,
    },
    {
        "task_id": TASK_ID,
        "event_type": "agent_spawned",
        "status": "pending",
        "message": "Architect",
        "job_id": JOB_ID,
    },
    {
        "task_id": TASK_ID,
        "event_type": "task_started",
        "status": "pending",
        "job_id": JOB_ID,
    },
    {
        "task_id": TASK_ID,
        "event_type": "round_result",
        "status": "failure",
        "message": "round 1",
        "job_id": JOB_ID,
    },
    {
        "task_id": TASK_ID,
        "event_type": "round_result",
        "status": "success",
        "message": "round 2",
        "job_id": JOB_ID,
    },
    {
        "task_id": TASK_ID,
        "event_type": "task_completed",
        "status": "success",
        "job_id": JOB_ID,
    },
    {
        "task_id": TASK_ID,
        "event_type": "agent_exited",
        "status": "success",
        "message": "Architect",
        "job_id": JOB_ID,
    },
    {
        "task_id": JOB_ID,
        "event_type": "job_completed",
        "status": "success",
        "job_id": JOB_ID,
    },
]

# All lifecycle events now appear in /log (job-level + task-level)
ALL_LOG_EVENTS = LIFECYCLE_EVENTS

# State file written by the orchestrator for the test job
TEST_JOB_STATE: dict[str, object] = {
    "repo_name": REPO_NAME,
    "issue_number": ISSUE_NUMBER,
    "working_dir": f"/tmp/{REPO_NAME}",
    "branch": f"factory/issue-{ISSUE_NUMBER}",
    "status": "success",
    "pr_number": None,
    "tasks": [
        {
            "id": TASK_ID,
            "title": "Design architecture",
            "description": "Design the system architecture for the feature.",
            "status": "success",
            "issue_number": None,
            "failure_issue": None,
            "acceptance_criteria": ["Architecture is documented"],
            "depends_on": [],
        }
    ],
}


# ---------------------------------------------------------------------------
# Fixtures — DB and state isolation
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_db(tmp_path: Path) -> Generator[str, None, None]:
    """Point db module at a fresh SQLite file, restore when done."""
    import factory.dashboard.db as db_module

    db_path = str(tmp_path / "integration_test.db")
    original: str = db_module.DB_PATH  # type: ignore[attr-defined]
    db_module.DB_PATH = db_path  # type: ignore[attr-defined]
    yield db_path
    db_module.DB_PATH = original  # type: ignore[attr-defined]


@pytest.fixture
def isolated_state_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Point jobs router at a fresh temporary state directory, restore when done."""
    import factory.dashboard.routers.jobs as jobs_module

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    original: Path = jobs_module.STATE_DIR  # type: ignore[attr-defined]
    jobs_module.STATE_DIR = state_dir  # type: ignore[attr-defined]
    yield state_dir
    jobs_module.STATE_DIR = original  # type: ignore[attr-defined]


@pytest.fixture
def job_state_file(isolated_state_dir: Path) -> Path:
    """Write the test job state JSON file into the isolated state directory."""
    state_file = isolated_state_dir / f"{REPO_NAME}-{ISSUE_NUMBER}.json"
    state_file.write_text(json.dumps(TEST_JOB_STATE))
    return state_file


# ---------------------------------------------------------------------------
# Integration: full job lifecycle
# ---------------------------------------------------------------------------


class TestFullJobLifecycle:
    """End-to-end integration test: post a lifecycle sequence, then read it back."""

    @pytest.mark.anyio
    async def test_lifecycle_has_at_least_eight_events(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """The test lifecycle sequence must contain at least 8 events."""
        assert len(LIFECYCLE_EVENTS) >= 8, (
            f"Lifecycle sequence has only {len(LIFECYCLE_EVENTS)} events — need 8+"
        )

    @pytest.mark.anyio
    async def test_all_lifecycle_events_return_201(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """Every POST /api/v1/events in the lifecycle must return HTTP 201."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for event in LIFECYCLE_EVENTS:
                response = await client.post("/api/v1/events", json=event)
                assert response.status_code == 201, (
                    f"Event {event['event_type']!r} returned {response.status_code}: "
                    f"{response.text}"
                )

    @pytest.mark.anyio
    async def test_list_jobs_returns_correct_task_count(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs returns the job with task_count matching state file."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for event in LIFECYCLE_EVENTS:
                await client.post("/api/v1/events", json=event)

            response = await client.get("/api/v1/jobs")

        assert response.status_code == 200
        jobs = response.json()
        assert isinstance(jobs, list)

        job = next((j for j in jobs if j["job_id"] == JOB_ID), None)
        assert job is not None, f"Job {JOB_ID!r} not found in response: {jobs}"
        assert job["task_count"] == len(TEST_JOB_STATE["tasks"])  # type: ignore[arg-type]

    @pytest.mark.anyio
    async def test_list_jobs_returns_correct_completed_count(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs returns the job with completed_task_count == 1."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for event in LIFECYCLE_EVENTS:
                await client.post("/api/v1/events", json=event)

            response = await client.get("/api/v1/jobs")

        jobs = response.json()
        job = next((j for j in jobs if j["job_id"] == JOB_ID), None)
        assert job is not None
        expected_completed = sum(
            1
            for t in TEST_JOB_STATE["tasks"]  # type: ignore[union-attr]
            if t["status"] == "success"  # type: ignore[index]
        )
        assert job["completed_task_count"] == expected_completed

    @pytest.mark.anyio
    async def test_list_jobs_returns_correct_status(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs returns the job with status == 'success'."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for event in LIFECYCLE_EVENTS:
                await client.post("/api/v1/events", json=event)

            response = await client.get("/api/v1/jobs")

        jobs = response.json()
        job = next((j for j in jobs if j["job_id"] == JOB_ID), None)
        assert job is not None
        assert job["status"] == TEST_JOB_STATE["status"]

    @pytest.mark.anyio
    async def test_get_job_detail_returns_200(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs/{id} must return 200 for an existing job."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/jobs/{JOB_ID_PATH}")

        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_get_job_detail_contains_correct_fields(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs/{id} returns job_id, repo_name, issue_number, status."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/jobs/{JOB_ID_PATH}")

        detail = response.json()
        assert detail["job_id"] == JOB_ID
        assert detail["repo_name"] == REPO_NAME
        assert detail["issue_number"] == ISSUE_NUMBER
        assert detail["status"] == TEST_JOB_STATE["status"]

    @pytest.mark.anyio
    async def test_get_job_detail_contains_tasks(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs/{id} response includes all tasks from state file."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/jobs/{JOB_ID_PATH}")

        detail = response.json()
        assert "tasks" in detail
        assert isinstance(detail["tasks"], list)
        assert len(detail["tasks"]) == len(TEST_JOB_STATE["tasks"])  # type: ignore[arg-type]

        task = detail["tasks"][0]
        assert task["id"] == TASK_ID
        assert task["title"] == "Design architecture"
        assert task["status"] == "success"

    @pytest.mark.anyio
    async def test_get_job_detail_not_found_returns_404(
        self,
        isolated_db: str,
        isolated_state_dir: Path,
    ) -> None:
        """GET /api/v1/jobs/{id} returns 404 when the job does not exist."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/jobs/no-such-repo#9999")

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_get_job_log_returns_200(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs/{id}/log must return 200 for an existing job."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for event in LIFECYCLE_EVENTS:
                await client.post("/api/v1/events", json=event)

            response = await client.get(f"/api/v1/jobs/{JOB_ID_PATH}/log")

        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_get_job_log_returns_task_events_only(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs/{id}/log returns events for task IDs listed in state file."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for event in LIFECYCLE_EVENTS:
                await client.post("/api/v1/events", json=event)

            response = await client.get(f"/api/v1/jobs/{JOB_ID_PATH}/log")

        log = response.json()
        assert isinstance(log, list)
        assert len(log) == len(ALL_LOG_EVENTS), (
            f"Expected {len(ALL_LOG_EVENTS)} log entries, "
            f"got {len(log)}: {[e.get('event_type') for e in log]}"
        )

    @pytest.mark.anyio
    async def test_get_job_log_events_are_in_chronological_order(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs/{id}/log events are ordered by timestamp ascending."""
        from datetime import datetime

        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for event in LIFECYCLE_EVENTS:
                await client.post("/api/v1/events", json=event)

            response = await client.get(f"/api/v1/jobs/{JOB_ID_PATH}/log")

        log = response.json()
        timestamps = [datetime.fromisoformat(e["timestamp"]) for e in log]
        assert timestamps == sorted(timestamps), (
            f"Log events are not in chronological order: {timestamps}"
        )

    @pytest.mark.anyio
    async def test_get_job_log_event_types_match_posted_sequence(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs/{id}/log event types match the posted task-level sequence."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for event in LIFECYCLE_EVENTS:
                await client.post("/api/v1/events", json=event)

            response = await client.get(f"/api/v1/jobs/{JOB_ID_PATH}/log")

        log = response.json()
        actual_types = [e["event_type"] for e in log]
        expected_types = [e["event_type"] for e in ALL_LOG_EVENTS]
        assert actual_types == expected_types, (
            f"Event type mismatch.\nExpected: {expected_types}\nActual:   {actual_types}"
        )

    @pytest.mark.anyio
    async def test_get_job_log_not_found_returns_404(
        self,
        isolated_db: str,
        isolated_state_dir: Path,
    ) -> None:
        """GET /api/v1/jobs/{id}/log returns 404 when the job does not exist."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/jobs/no-such-repo#9999/log")

        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_get_job_log_is_empty_when_no_events_posted(
        self,
        isolated_db: str,
        job_state_file: Path,
    ) -> None:
        """GET /api/v1/jobs/{id}/log returns an empty list when no events exist."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/jobs/{JOB_ID_PATH}/log")

        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# EventEmitter integration
# ---------------------------------------------------------------------------


def _make_test_client_class(app: object) -> type:
    """Return a patched AsyncClient subclass that routes requests to *app*."""

    class _TestAsyncClient(httpx.AsyncClient):
        def __init__(self) -> None:
            super().__init__(
                transport=ASGITransport(app=app),  # type: ignore[arg-type]
                base_url="http://test",
            )

    return _TestAsyncClient


class TestEventEmitterIntegration:
    """EventEmitter integration against the real FastAPI test application."""

    @pytest.mark.anyio
    async def test_emitter_posts_job_started_to_test_app(
        self, isolated_db: str
    ) -> None:
        """emit_job_started() POSTs to the real test app and stores the event in DB."""
        import factory.dashboard.db as db_module
        from factory.dashboard.app import app
        from factory.dashboard.emitter import EventEmitter

        TestClient = _make_test_client_class(app)

        with patch("factory.dashboard.emitter.httpx.AsyncClient", TestClient):
            emitter = EventEmitter()
            emitter._base_url = "http://test"  # type: ignore[attr-defined]
            assert emitter.enabled is True

            await emitter.emit_job_started(REPO_NAME, ISSUE_NUMBER)

        stored = await db_module.fetch_events_for_job([JOB_ID])
        assert len(stored) == 1
        assert stored[0].event_type == "job_started"
        assert stored[0].status == "pending"
        assert stored[0].task_id == JOB_ID

    @pytest.mark.anyio
    async def test_emitter_posts_task_events_to_test_app(
        self, isolated_db: str
    ) -> None:
        """emit_task_started/completed POSTs are stored correctly in the test app DB."""
        import factory.dashboard.db as db_module
        from factory.dashboard.app import app
        from factory.dashboard.emitter import EventEmitter

        TestClient = _make_test_client_class(app)

        with patch("factory.dashboard.emitter.httpx.AsyncClient", TestClient):
            emitter = EventEmitter()
            emitter._base_url = "http://test"  # type: ignore[attr-defined]

            await emitter.emit_task_started(TASK_ID)
            await emitter.emit_task_completed(TASK_ID)

        stored = await db_module.fetch_events_for_job([TASK_ID])
        assert len(stored) == 2
        assert stored[0].event_type == "task_started"
        assert stored[1].event_type == "task_completed"

    @pytest.mark.anyio
    async def test_emitter_posts_round_result_with_correct_status(
        self, isolated_db: str
    ) -> None:
        """emit_round_result() stores failure then success with correct status/message."""
        import factory.dashboard.db as db_module
        from factory.dashboard.app import app
        from factory.dashboard.emitter import EventEmitter

        TestClient = _make_test_client_class(app)

        with patch("factory.dashboard.emitter.httpx.AsyncClient", TestClient):
            emitter = EventEmitter()
            emitter._base_url = "http://test"  # type: ignore[attr-defined]

            await emitter.emit_round_result(TASK_ID, 1, passed=False)
            await emitter.emit_round_result(TASK_ID, 2, passed=True)

        stored = await db_module.fetch_events_for_job([TASK_ID])
        assert len(stored) == 2
        assert stored[0].event_type == "round_result"
        assert stored[0].status == "failure"
        assert stored[0].message == "round 1"
        assert stored[1].event_type == "round_result"
        assert stored[1].status == "success"
        assert stored[1].message == "round 2"

    @pytest.mark.anyio
    async def test_emitter_posts_full_lifecycle_to_test_app(
        self, isolated_db: str
    ) -> None:
        """EventEmitter can emit all 9 event types through the test app without error."""
        import factory.dashboard.db as db_module
        from factory.dashboard.app import app
        from factory.dashboard.emitter import EventEmitter

        TestClient = _make_test_client_class(app)

        with patch("factory.dashboard.emitter.httpx.AsyncClient", TestClient):
            emitter = EventEmitter()
            emitter._base_url = "http://test"  # type: ignore[attr-defined]

            await emitter.emit_job_started(REPO_NAME, ISSUE_NUMBER)
            await emitter.emit_agent_spawned(TASK_ID, "Architect")
            await emitter.emit_task_started(TASK_ID)
            await emitter.emit_round_result(TASK_ID, 1, passed=False)
            await emitter.emit_round_result(TASK_ID, 2, passed=True)
            await emitter.emit_task_completed(TASK_ID)
            await emitter.emit_agent_exited(TASK_ID, "Architect", success=True)
            await emitter.emit_job_completed(REPO_NAME, ISSUE_NUMBER)
            await emitter.emit_job_failed(REPO_NAME, ISSUE_NUMBER + 1)

        # 6 task-scoped events: agent_spawned, task_started, round_result×2,
        #                        task_completed, agent_exited
        task_events = await db_module.fetch_events_for_job([TASK_ID])
        assert len(task_events) == 6

        # 2 job-level "success" events + 1 job-level "failure" event
        job_events = await db_module.fetch_events_for_job([JOB_ID])
        assert len(job_events) == 2

        failed_job_id = f"{REPO_NAME}#{ISSUE_NUMBER + 1}"
        failed_events = await db_module.fetch_events_for_job([failed_job_id])
        assert len(failed_events) == 1
        assert failed_events[0].event_type == "job_failed"

    # ------------------------------------------------------------------
    # Fire-and-forget: errors must be swallowed, never raised
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_emitter_swallows_connection_error(self) -> None:
        """EventEmitter does not raise when the target server is unreachable."""
        from factory.dashboard.emitter import EventEmitter

        emitter = EventEmitter()
        # Use a port where nothing is listening
        emitter._base_url = "http://127.0.0.1:19753"  # type: ignore[attr-defined]
        assert emitter.enabled is True

        # None of these must raise
        await emitter.emit_job_started(REPO_NAME, ISSUE_NUMBER)
        await emitter.emit_task_started(TASK_ID)
        await emitter.emit_job_completed(REPO_NAME, ISSUE_NUMBER)

    @pytest.mark.anyio
    async def test_emitter_swallows_http_error_response(
        self, isolated_db: str
    ) -> None:
        """EventEmitter does not raise when the server returns a 500 response."""
        from fastapi import FastAPI
        from fastapi import Response
        from factory.dashboard.emitter import EventEmitter

        # Minimal app that always returns 500
        error_app = FastAPI()

        @error_app.post("/api/v1/events")
        async def always_fail() -> Response:
            return Response(status_code=500)

        TestClient = _make_test_client_class(error_app)

        with patch("factory.dashboard.emitter.httpx.AsyncClient", TestClient):
            emitter = EventEmitter()
            emitter._base_url = "http://test"  # type: ignore[attr-defined]

            # Must not raise despite the 500
            await emitter.emit_job_started(REPO_NAME, ISSUE_NUMBER)
            await emitter.emit_task_started(TASK_ID)

    @pytest.mark.anyio
    async def test_emitter_no_op_when_dashboard_url_unset(self) -> None:
        """EventEmitter is a silent no-op when DASHBOARD_URL env var is absent."""
        import os

        from factory.dashboard.emitter import EventEmitter

        original = os.environ.get("DASHBOARD_URL")
        os.environ.pop("DASHBOARD_URL", None)
        try:
            emitter = EventEmitter()
            assert emitter.enabled is False
            # Should return immediately without touching the network
            await emitter.emit_job_started(REPO_NAME, ISSUE_NUMBER)
            await emitter.emit_task_started(TASK_ID)
        finally:
            if original is not None:
                os.environ["DASHBOARD_URL"] = original

    @pytest.mark.anyio
    async def test_emitter_no_op_when_dashboard_url_empty(self) -> None:
        """EventEmitter is a silent no-op when DASHBOARD_URL is set to empty string."""
        import os

        from factory.dashboard.emitter import EventEmitter

        original = os.environ.get("DASHBOARD_URL")
        os.environ["DASHBOARD_URL"] = ""
        try:
            emitter = EventEmitter()
            assert emitter.enabled is False
            await emitter.emit_job_started(REPO_NAME, ISSUE_NUMBER)
        finally:
            if original is None:
                os.environ.pop("DASHBOARD_URL", None)
            else:
                os.environ["DASHBOARD_URL"] = original


# ---------------------------------------------------------------------------
# Frontend production build
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestFrontendBuild:
    """Verify the React/TypeScript frontend can be built for production."""

    def test_frontend_directory_exists(self) -> None:
        """The dashboard/frontend directory must be present in the repository."""
        frontend_dir = PROJECT_ROOT / "dashboard" / "frontend"
        assert frontend_dir.is_dir(), (
            f"Frontend directory not found: {frontend_dir}"
        )

    def test_frontend_package_json_exists(self) -> None:
        """dashboard/frontend/package.json must be present."""
        pkg = PROJECT_ROOT / "dashboard" / "frontend" / "package.json"
        assert pkg.is_file(), f"package.json not found: {pkg}"

    def test_frontend_package_json_has_build_script(self) -> None:
        """package.json must define a 'build' script."""
        pkg = PROJECT_ROOT / "dashboard" / "frontend" / "package.json"
        data = json.loads(pkg.read_text())
        assert "scripts" in data, "package.json is missing the 'scripts' key"
        assert "build" in data["scripts"], (
            f"package.json has no 'build' script: {data['scripts']}"
        )

    def test_frontend_node_modules_installed(self) -> None:
        """node_modules must be present (npm install must have been run)."""
        node_modules = PROJECT_ROOT / "dashboard" / "frontend" / "node_modules"
        assert node_modules.is_dir(), (
            f"node_modules not found at {node_modules}. "
            "Run: cd dashboard/frontend && npm install"
        )

    def test_frontend_typescript_config_exists(self) -> None:
        """tsconfig.json must exist for TypeScript compilation."""
        tsconfig = PROJECT_ROOT / "dashboard" / "frontend" / "tsconfig.json"
        assert tsconfig.is_file(), (
            f"tsconfig.json not found: {tsconfig}"
        )

    def test_frontend_production_build_exits_zero(self) -> None:
        """Running 'npm run build' must complete successfully (exit code 0)."""
        frontend_dir = PROJECT_ROOT / "dashboard" / "frontend"
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"npm run build failed (exit {result.returncode}).\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
