"""Tests for POST /api/v1/events endpoint, models, DB layer, and app wiring."""

from __future__ import annotations

import re
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path

import aiosqlite
import pytest
from httpx import ASGITransport
from httpx import AsyncClient

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event_payload(
    *,
    task_id: str = "task-abc",
    event_type: str = "task_started",
    status: str = "pending",
    message: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "task_id": task_id,
        "event_type": event_type,
        "status": status,
    }
    if message is not None:
        payload["message"] = message
    return payload


# ---------------------------------------------------------------------------
# Model tests (no I/O)
# ---------------------------------------------------------------------------


class TestModels:
    """EventIn and EventOut Pydantic models have the correct fields."""

    def test_event_in_importable(self) -> None:
        """EventIn must be importable from factory.dashboard.models."""
        from factory.dashboard.models import EventIn  # noqa: F401

    def test_event_out_importable(self) -> None:
        """EventOut must be importable from factory.dashboard.models."""
        from factory.dashboard.models import EventOut  # noqa: F401

    def test_event_in_required_fields(self) -> None:
        """EventIn must accept task_id, event_type, and status."""
        from factory.dashboard.models import EventIn

        event = EventIn(task_id="t1", event_type="task_started", status="pending")
        assert event.task_id == "t1"
        assert event.event_type == "task_started"
        assert event.status == "pending"
        assert event.message is None

    def test_event_in_optional_message(self) -> None:
        """EventIn.message must be optional and default to None."""
        from factory.dashboard.models import EventIn

        event = EventIn(task_id="t1", event_type="error", status="failure", message="oops")
        assert event.message == "oops"

    def test_event_out_has_id_and_timestamp(self) -> None:
        """EventOut must have id (str) and timestamp (datetime) fields."""
        from factory.dashboard.models import EventOut

        now = datetime.now(UTC)
        out = EventOut(
            id="some-uuid",
            task_id="t1",
            event_type="task_started",
            status="pending",
            timestamp=now,
        )
        assert out.id == "some-uuid"
        assert out.timestamp == now

    def test_event_out_from_attributes(self) -> None:
        """EventOut must have model_config = ConfigDict(from_attributes=True)."""
        from factory.dashboard.models import EventOut

        config = EventOut.model_config
        assert config.get("from_attributes") is True, (
            "EventOut.model_config must have from_attributes=True"
        )


# ---------------------------------------------------------------------------
# File-structure tests
# ---------------------------------------------------------------------------


class TestRouterFileExists:
    """factory/dashboard/routers/events.py exists and is importable."""

    def test_events_router_file_exists(self) -> None:
        """factory/dashboard/routers/events.py must be a file on disk."""
        path = PROJECT_ROOT / "factory" / "dashboard" / "routers" / "events.py"
        assert path.is_file(), f"Missing file: {path}"

    def test_events_router_importable(self) -> None:
        """factory.dashboard.routers.events must be importable."""
        from factory.dashboard.routers import events  # noqa: F401

    def test_events_router_exposes_router(self) -> None:
        """factory.dashboard.routers.events must expose an APIRouter named `router`."""
        from fastapi import APIRouter

        from factory.dashboard.routers.events import router

        assert isinstance(router, APIRouter)


# ---------------------------------------------------------------------------
# Database-layer tests (use in-memory SQLite)
# ---------------------------------------------------------------------------


class TestDatabaseLayer:
    """init_db() and insert_event() behave correctly against a real SQLite DB."""

    @pytest.mark.anyio
    async def test_init_db_creates_events_table(self) -> None:
        """init_db() must create the 'events' table in the SQLite database."""
        import factory.dashboard.db as db_module

        # Point the module at a fresh in-memory database for this test
        original_db_path = getattr(db_module, "DB_PATH", None)
        db_module.DB_PATH = ":memory:"  # type: ignore[attr-defined]

        try:
            await db_module.init_db()

            # Verify the table was created
            async with aiosqlite.connect(":memory:") as conn:
                # If init_db used a shared/global connection, we check through it
                pass

            # More direct check: call init_db on a known path, then inspect
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                tmp_path = f.name

            db_module.DB_PATH = tmp_path  # type: ignore[attr-defined]
            await db_module.init_db()

            async with aiosqlite.connect(tmp_path) as conn:
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
                )
                row = await cursor.fetchone()
                assert row is not None, "init_db() did not create the 'events' table"
        finally:
            if original_db_path is not None:
                db_module.DB_PATH = original_db_path  # type: ignore[attr-defined]

    @pytest.mark.anyio
    async def test_insert_event_persists_to_database(self) -> None:
        """insert_event() must write the event to the SQLite database."""
        import tempfile

        import factory.dashboard.db as db_module
        from factory.dashboard.models import EventIn

        original_db_path = getattr(db_module, "DB_PATH", None)

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = f.name

        try:
            db_module.DB_PATH = tmp_path  # type: ignore[attr-defined]
            await db_module.init_db()

            event_in = EventIn(
                task_id="task-persist-test",
                event_type="agent_completed",
                status="success",
                message="done",
            )
            result = await db_module.insert_event(event_in)

            # Verify the event is actually in the database
            async with aiosqlite.connect(tmp_path) as conn:
                cursor = await conn.execute(
                    "SELECT id, task_id, event_type, status, message FROM events WHERE id = ?",
                    (result.id,),
                )
                row = await cursor.fetchone()
                assert row is not None, (
                    "insert_event() did not persist the event to the database"
                )
                assert row[1] == "task-persist-test"
                assert row[2] == "agent_completed"
                assert row[3] == "success"
                assert row[4] == "done"
        finally:
            if original_db_path is not None:
                db_module.DB_PATH = original_db_path  # type: ignore[attr-defined]

    @pytest.mark.anyio
    async def test_insert_event_returns_event_out(self) -> None:
        """insert_event() must return an EventOut with server-generated id and timestamp."""
        import tempfile

        import factory.dashboard.db as db_module
        from factory.dashboard.models import EventIn
        from factory.dashboard.models import EventOut

        original_db_path = getattr(db_module, "DB_PATH", None)

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = f.name

        try:
            db_module.DB_PATH = tmp_path  # type: ignore[attr-defined]
            await db_module.init_db()

            event_in = EventIn(
                task_id="t1",
                event_type="task_started",
                status="pending",
            )
            before = datetime.now(UTC)
            result = await db_module.insert_event(event_in)
            after = datetime.now(UTC)

            assert isinstance(result, EventOut)
            assert result.task_id == "t1"
            assert result.event_type == "task_started"
            assert result.status == "pending"
            assert result.message is None
            # id must be a valid UUID
            uuid.UUID(result.id)  # raises ValueError if invalid
            # timestamp must be UTC and within the call window
            assert result.timestamp.tzinfo is not None, "timestamp must be timezone-aware"
            ts_utc = result.timestamp.astimezone(UTC)
            assert before <= ts_utc <= after

        finally:
            if original_db_path is not None:
                db_module.DB_PATH = original_db_path  # type: ignore[attr-defined]

    @pytest.mark.anyio
    async def test_init_db_is_idempotent(self) -> None:
        """Calling init_db() multiple times must not raise an error."""
        import tempfile

        import factory.dashboard.db as db_module

        original_db_path = getattr(db_module, "DB_PATH", None)

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = f.name

        try:
            db_module.DB_PATH = tmp_path  # type: ignore[attr-defined]
            await db_module.init_db()
            await db_module.init_db()  # second call must not raise
        finally:
            if original_db_path is not None:
                db_module.DB_PATH = original_db_path  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# API endpoint tests (httpx AsyncClient)
# ---------------------------------------------------------------------------


class TestPostEventsEndpoint:
    """POST /api/v1/events behaves according to acceptance criteria."""

    @pytest.mark.anyio
    async def test_post_events_returns_201(self) -> None:
        """POST /api/v1/events with a valid body must return 201."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/events", json=_make_event_payload()
            )
        assert response.status_code == 201

    @pytest.mark.anyio
    async def test_post_events_response_body_is_json(self) -> None:
        """Response body must be valid JSON."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/events", json=_make_event_payload()
            )
        assert response.headers["content-type"].startswith("application/json")
        response.json()  # must not raise

    @pytest.mark.anyio
    async def test_post_events_response_contains_id(self) -> None:
        """Response must include a server-generated id field."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/events", json=_make_event_payload()
            )
        data = response.json()
        assert "id" in data, "Response missing 'id' field"
        # id must be a valid UUID string
        uuid.UUID(data["id"])

    @pytest.mark.anyio
    async def test_post_events_response_contains_timestamp(self) -> None:
        """Response must include a server-generated timestamp field."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/events", json=_make_event_payload()
            )
        data = response.json()
        assert "timestamp" in data, "Response missing 'timestamp' field"
        # Timestamp must be parseable as ISO 8601
        datetime.fromisoformat(data["timestamp"])

    @pytest.mark.anyio
    async def test_post_events_response_fields_match_input(self) -> None:
        """Response must echo back task_id, event_type, status from the request."""
        from factory.dashboard.app import app

        payload = _make_event_payload(
            task_id="task-xyz",
            event_type="agent_completed",
            status="success",
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/events", json=payload)
        data = response.json()
        assert data["task_id"] == "task-xyz"
        assert data["event_type"] == "agent_completed"
        assert data["status"] == "success"

    @pytest.mark.anyio
    async def test_post_events_with_message(self) -> None:
        """Response must include the optional message when provided."""
        from factory.dashboard.app import app

        payload = _make_event_payload(message="All good")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/events", json=payload)
        data = response.json()
        assert data["message"] == "All good"

    @pytest.mark.anyio
    async def test_post_events_without_message_returns_none(self) -> None:
        """Response message must be null when not provided in the request."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/events", json=_make_event_payload()
            )
        data = response.json()
        assert data.get("message") is None

    @pytest.mark.anyio
    async def test_post_events_ids_are_unique(self) -> None:
        """Each POST /api/v1/events request must produce a unique id."""
        from factory.dashboard.app import app

        ids: list[str] = []
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(5):
                response = await client.post(
                    "/api/v1/events", json=_make_event_payload()
                )
                assert response.status_code == 201
                ids.append(response.json()["id"])

        assert len(set(ids)) == 5, f"IDs are not unique: {ids}"

    @pytest.mark.anyio
    async def test_post_events_timestamp_is_utc(self) -> None:
        """Response timestamp must be a timezone-aware UTC datetime."""
        from factory.dashboard.app import app

        before = datetime.now(UTC)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/events", json=_make_event_payload()
            )
        after = datetime.now(UTC)

        ts_str = response.json()["timestamp"]
        ts = datetime.fromisoformat(ts_str)
        assert ts.tzinfo is not None, "timestamp must be timezone-aware"
        ts_utc = ts.astimezone(UTC)
        assert before <= ts_utc <= after, (
            f"timestamp {ts_utc} not between {before} and {after}"
        )


# ---------------------------------------------------------------------------
# Validation / 422 tests
# ---------------------------------------------------------------------------


class TestPostEventsValidation:
    """POST /api/v1/events returns 422 for invalid request bodies."""

    @pytest.mark.anyio
    async def test_missing_task_id_returns_422(self) -> None:
        """Omitting task_id must return 422."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/events",
                json={"event_type": "task_started", "status": "pending"},
            )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_missing_event_type_returns_422(self) -> None:
        """Omitting event_type must return 422."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/events",
                json={"task_id": "t1", "status": "pending"},
            )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_missing_status_returns_422(self) -> None:
        """Omitting status must return 422."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/events",
                json={"task_id": "t1", "event_type": "task_started"},
            )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_empty_body_returns_422(self) -> None:
        """Sending an empty JSON object must return 422."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/events", json={})
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_non_json_body_returns_422(self) -> None:
        """Sending a non-JSON body must return 422."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/events",
                content=b"not json",
                headers={"content-type": "application/json"},
            )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_422_body_contains_detail(self) -> None:
        """422 response must include a 'detail' field describing validation errors."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/events", json={})
        data = response.json()
        assert "detail" in data, "422 response missing 'detail' field"


# ---------------------------------------------------------------------------
# App wiring: CORS, lifespan, router registration
# ---------------------------------------------------------------------------


class TestAppWiring:
    """App is wired correctly: CORS, lifespan, /api/v1 router."""

    def test_cors_middleware_registered(self) -> None:
        """CORSMiddleware must be in the app's middleware stack."""
        from starlette.middleware.cors import CORSMiddleware

        from factory.dashboard.app import app

        middleware_classes = [
            m.cls for m in app.user_middleware if hasattr(m, "cls")
        ]
        assert CORSMiddleware in middleware_classes, (
            "CORSMiddleware not found in app middleware stack"
        )

    def test_cors_allows_all_origins(self) -> None:
        """CORSMiddleware must be configured with allow_origins=['*']."""
        from starlette.middleware.cors import CORSMiddleware

        from factory.dashboard.app import app

        for m in app.user_middleware:
            if hasattr(m, "cls") and m.cls is CORSMiddleware:
                kwargs = m.kwargs
                assert kwargs.get("allow_origins") == ["*"], (
                    f"CORS allow_origins must be ['*'], got {kwargs.get('allow_origins')!r}"
                )
                return
        pytest.fail("CORSMiddleware not found in middleware stack")

    @pytest.mark.anyio
    async def test_cors_header_present_in_response(self) -> None:
        """A preflight OPTIONS request must return the CORS allow-origin header."""
        from factory.dashboard.app import app

        origin = "http://localhost:5173"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.options(
                "/api/v1/events",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                },
            )
        # CORS must send back an allow-origin header.
        # When allow_credentials=True Starlette reflects the request origin
        # instead of "*", so we accept either.
        assert "access-control-allow-origin" in response.headers, (
            "CORS allow-origin header missing from preflight response"
        )
        assert response.headers["access-control-allow-origin"] in ("*", origin)

    def test_lifespan_function_exists_in_app_module(self) -> None:
        """factory.dashboard.app must expose a `lifespan` async context manager."""
        # Use sys.modules because __init__.py shadows factory.dashboard.app
        # with the FastAPI instance when using `import ... as`.
        import sys

        import factory.dashboard.app  # noqa: F401 – ensure module is loaded

        app_module = sys.modules["factory.dashboard.app"]
        assert hasattr(app_module, "lifespan"), (
            "factory.dashboard.app must define a 'lifespan' function"
        )
        assert callable(app_module.lifespan), "lifespan must be callable"

    @pytest.mark.anyio
    async def test_lifespan_calls_init_db_on_startup(self) -> None:
        """The lifespan context manager must call init_db() during startup."""
        from unittest.mock import AsyncMock
        from unittest.mock import patch

        from factory.dashboard.app import app
        from factory.dashboard.app import lifespan

        # httpx ASGITransport does not send ASGI lifespan events, so we
        # invoke the lifespan context manager directly.
        with patch("factory.dashboard.app.init_db", new_callable=AsyncMock) as mock_init:
            async with lifespan(app):
                pass
            mock_init.assert_called_once()

    def test_events_route_registered_under_api_v1(self) -> None:
        """POST /api/v1/events must appear in the app's route table."""
        from factory.dashboard.app import app

        routes = app.routes
        post_event_routes = [
            r
            for r in routes
            if hasattr(r, "path")
            and r.path == "/api/v1/events"
            and hasattr(r, "methods")
            and "POST" in (r.methods or set())
        ]
        assert len(post_event_routes) >= 1, (
            "No POST /api/v1/events route found in app.routes"
        )

    @pytest.mark.anyio
    async def test_get_events_route_not_found(self) -> None:
        """GET /api/v1/events is not defined and must return 404 or 405."""
        from factory.dashboard.app import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/events")
        assert response.status_code in (404, 405)
