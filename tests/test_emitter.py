"""Tests for factory.dashboard.emitter — EventEmitter class.

Phase 1 (Red): All tests must fail until factory/dashboard/emitter.py is implemented.
"""

from __future__ import annotations

import asyncio
import inspect
import os
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_httpx_client() -> tuple[AsyncMock, MagicMock]:
    """Return (mock_client, mock_response) for patching httpx.AsyncClient."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client, mock_response


def _patch_httpx(mock_client: AsyncMock) -> MagicMock:
    """Build a patched httpx module whose AsyncClient yields mock_client."""
    mock_httpx = MagicMock()
    mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)
    # Also support direct httpx.post / httpx.AsyncClient() without context manager
    mock_httpx.AsyncClient.return_value.post = mock_client.post
    return mock_httpx


# ---------------------------------------------------------------------------
# Module structure
# ---------------------------------------------------------------------------


class TestEmitterModuleStructure:
    """factory/dashboard/emitter.py exists and exposes EventEmitter."""

    def test_emitter_file_exists(self) -> None:
        """factory/dashboard/emitter.py must be a file on disk."""
        path = PROJECT_ROOT / "factory" / "dashboard" / "emitter.py"
        assert path.is_file(), f"Missing: {path}"

    def test_emitter_importable(self) -> None:
        """factory.dashboard.emitter must be importable without error."""
        import factory.dashboard.emitter  # noqa: F401

    def test_event_emitter_class_exists(self) -> None:
        """factory.dashboard.emitter must expose EventEmitter."""
        from factory.dashboard import emitter as m

        assert hasattr(m, "EventEmitter"), "EventEmitter not found in factory.dashboard.emitter"

    def test_event_emitter_is_a_class(self) -> None:
        """EventEmitter must be a class, not a function or constant."""
        from factory.dashboard.emitter import EventEmitter

        assert inspect.isclass(EventEmitter)


# ---------------------------------------------------------------------------
# Method surface area
# ---------------------------------------------------------------------------


class TestEmitterInterface:
    """EventEmitter exposes all 9 required async emit methods."""

    @pytest.fixture()
    def emitter(self) -> object:
        from factory.dashboard.emitter import EventEmitter

        return EventEmitter()

    def _assert_async_method(self, obj: object, name: str) -> None:
        assert hasattr(obj, name), f"EventEmitter missing method: {name}"
        method = getattr(obj, name)
        assert callable(method), f"EventEmitter.{name} is not callable"
        assert asyncio.iscoroutinefunction(method), f"EventEmitter.{name} must be async"

    def test_has_emit_job_started(self, emitter: object) -> None:
        self._assert_async_method(emitter, "emit_job_started")

    def test_has_emit_job_completed(self, emitter: object) -> None:
        self._assert_async_method(emitter, "emit_job_completed")

    def test_has_emit_job_failed(self, emitter: object) -> None:
        self._assert_async_method(emitter, "emit_job_failed")

    def test_has_emit_agent_spawned(self, emitter: object) -> None:
        self._assert_async_method(emitter, "emit_agent_spawned")

    def test_has_emit_agent_exited(self, emitter: object) -> None:
        self._assert_async_method(emitter, "emit_agent_exited")

    def test_has_emit_task_started(self, emitter: object) -> None:
        self._assert_async_method(emitter, "emit_task_started")

    def test_has_emit_task_completed(self, emitter: object) -> None:
        self._assert_async_method(emitter, "emit_task_completed")

    def test_has_emit_task_failed(self, emitter: object) -> None:
        self._assert_async_method(emitter, "emit_task_failed")

    def test_has_emit_round_result(self, emitter: object) -> None:
        self._assert_async_method(emitter, "emit_round_result")


# ---------------------------------------------------------------------------
# No-op behaviour (DASHBOARD_URL absent or empty)
# ---------------------------------------------------------------------------


class TestEmitterNoOp:
    """EventEmitter is a silent no-op when DASHBOARD_URL is not set or empty."""

    @pytest.mark.anyio
    async def test_no_op_when_dashboard_url_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No HTTP calls are made when DASHBOARD_URL is absent from environment."""
        monkeypatch.delenv("DASHBOARD_URL", raising=False)

        from factory.dashboard.emitter import EventEmitter

        emitter = EventEmitter()
        mock_client, _ = _make_mock_httpx_client()
        mock_httpx = _patch_httpx(mock_client)

        with patch("factory.dashboard.emitter.httpx", mock_httpx):
            await emitter.emit_job_started("my-repo", 1)
            await asyncio.sleep(0)  # let any background tasks flush

        mock_client.post.assert_not_called()

    @pytest.mark.anyio
    async def test_no_op_when_dashboard_url_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No HTTP calls are made when DASHBOARD_URL is set to an empty string."""
        monkeypatch.setenv("DASHBOARD_URL", "")

        from factory.dashboard.emitter import EventEmitter

        emitter = EventEmitter()
        mock_client, _ = _make_mock_httpx_client()
        mock_httpx = _patch_httpx(mock_client)

        with patch("factory.dashboard.emitter.httpx", mock_httpx):
            await emitter.emit_task_started("task-1")
            await asyncio.sleep(0)

        mock_client.post.assert_not_called()

    @pytest.mark.anyio
    async def test_no_op_never_raises_job_started(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_job_started must not raise even without DASHBOARD_URL."""
        monkeypatch.delenv("DASHBOARD_URL", raising=False)
        from factory.dashboard.emitter import EventEmitter

        await EventEmitter().emit_job_started("repo", 99)

    @pytest.mark.anyio
    async def test_no_op_never_raises_all_methods(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All 9 emit methods are callable without DASHBOARD_URL without raising."""
        monkeypatch.delenv("DASHBOARD_URL", raising=False)
        from factory.dashboard.emitter import EventEmitter

        e = EventEmitter()
        await e.emit_job_started("repo", 1)
        await e.emit_job_completed("repo", 1)
        await e.emit_job_failed("repo", 1)
        await e.emit_agent_spawned("task-1", "generator")
        await e.emit_agent_exited("task-1", "generator", success=True)
        await e.emit_task_started("task-1")
        await e.emit_task_completed("task-1")
        await e.emit_task_failed("task-1")
        await e.emit_round_result("task-1", 1, passed=True)


# ---------------------------------------------------------------------------
# Correct payload construction
# ---------------------------------------------------------------------------


class TestEmitterPayloads:
    """Each emit method POSTs a correctly structured EventIn payload."""

    @pytest.mark.anyio
    async def test_emit_job_started_posts_to_events_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_job_started must POST to {DASHBOARD_URL}/api/v1/events."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        mock_httpx = _patch_httpx(mock_client)

        with patch("factory.dashboard.emitter.httpx", mock_httpx):
            emitter = EventEmitter()
            await emitter.emit_job_started("my-repo", 7)
            await asyncio.sleep(0)

        assert mock_client.post.call_count >= 1
        call_args = mock_client.post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "http://dashboard:8000" in str(url), f"Wrong base URL in call: {call_args}"
        assert "/api/v1/events" in str(url), f"Missing /api/v1/events in call: {call_args}"

    @pytest.mark.anyio
    async def test_emit_job_started_payload_event_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_job_started payload must have event_type='job_started'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        mock_httpx = _patch_httpx(mock_client)

        with patch("factory.dashboard.emitter.httpx", mock_httpx):
            emitter = EventEmitter()
            await emitter.emit_job_started("repo", 1)
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("event_type") == "job_started", f"Unexpected payload: {payload}"

    @pytest.mark.anyio
    async def test_emit_job_completed_payload_event_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_job_completed payload must have event_type='job_completed'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_job_completed("repo", 1)
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("event_type") == "job_completed", f"Unexpected payload: {payload}"

    @pytest.mark.anyio
    async def test_emit_job_failed_payload_event_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_job_failed payload must have event_type='job_failed'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_job_failed("repo", 1)
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("event_type") == "job_failed", f"Unexpected payload: {payload}"

    @pytest.mark.anyio
    async def test_emit_agent_spawned_payload_event_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_agent_spawned payload must have event_type='agent_spawned'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_agent_spawned("task-1", "generator")
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("event_type") == "agent_spawned", f"Unexpected payload: {payload}"

    @pytest.mark.anyio
    async def test_emit_agent_exited_payload_event_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_agent_exited payload must have event_type='agent_exited'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_agent_exited("task-1", "evaluator", success=False)
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("event_type") == "agent_exited", f"Unexpected payload: {payload}"

    @pytest.mark.anyio
    async def test_emit_task_started_payload_event_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_task_started payload must have event_type='task_started'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_task_started("task-42")
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("event_type") == "task_started", f"Unexpected payload: {payload}"

    @pytest.mark.anyio
    async def test_emit_task_completed_payload_event_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_task_completed payload must have event_type='task_completed'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_task_completed("task-42")
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("event_type") == "task_completed", f"Unexpected payload: {payload}"

    @pytest.mark.anyio
    async def test_emit_task_failed_payload_event_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_task_failed payload must have event_type='task_failed'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_task_failed("task-42")
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("event_type") == "task_failed", f"Unexpected payload: {payload}"

    @pytest.mark.anyio
    async def test_emit_round_result_payload_event_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_round_result payload must have event_type='round_result'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_round_result("task-42", round_num=3, passed=True)
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("event_type") == "round_result", f"Unexpected payload: {payload}"

    @pytest.mark.anyio
    async def test_emit_task_started_payload_has_task_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Payload must include the task_id passed to the method."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_task_started("task-99")
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("task_id") == "task-99", f"task_id missing or wrong: {payload}"

    @pytest.mark.anyio
    async def test_emit_task_started_payload_has_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Payload must include a non-empty status field."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_task_started("task-1")
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert "status" in payload and payload["status"], f"status missing or empty: {payload}"

    @pytest.mark.anyio
    async def test_emit_job_started_payload_has_task_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_job_started payload task_id must reference the job (repo + issue)."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_job_started("my-repo", 42)
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        task_id = payload.get("task_id", "")
        assert "my-repo" in str(task_id) or "42" in str(task_id), (
            f"job task_id must reference repo/issue, got: {task_id!r}"
        )

    @pytest.mark.anyio
    async def test_emit_round_result_pass_status_is_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_round_result with passed=True must emit a success status."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_round_result("task-1", round_num=2, passed=True)
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("status") == "success", f"Expected success, got: {payload}"

    @pytest.mark.anyio
    async def test_emit_round_result_fail_status_is_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_round_result with passed=False must emit a failure status."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_round_result("task-1", round_num=2, passed=False)
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("status") == "failure", f"Expected failure, got: {payload}"

    @pytest.mark.anyio
    async def test_emit_agent_exited_success_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_agent_exited with success=True must emit status='success'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_agent_exited("task-1", "generator", success=True)
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("status") == "success", f"Expected success, got: {payload}"

    @pytest.mark.anyio
    async def test_emit_agent_exited_failure_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """emit_agent_exited with success=False must emit status='failure'."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client, _ = _make_mock_httpx_client()
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_agent_exited("task-1", "generator", success=False)
            await asyncio.sleep(0)

        payload = _extract_json_payload(mock_client)
        assert payload.get("status") == "failure", f"Expected failure, got: {payload}"


def _extract_json_payload(mock_client: AsyncMock) -> dict[str, object]:
    """Extract the json= kwarg from the most recent post() call."""
    assert mock_client.post.call_count >= 1, "httpx client.post was never called"
    call = mock_client.post.call_args
    # Support both positional and keyword json argument
    if call[1].get("json") is not None:
        return call[1]["json"]  # type: ignore[return-value]
    if len(call[0]) >= 2:
        return call[0][1]  # type: ignore[return-value]
    raise AssertionError(f"Could not find json payload in call: {call}")


# ---------------------------------------------------------------------------
# Error / exception swallowing
# ---------------------------------------------------------------------------


class TestEmitterErrorHandling:
    """HTTP errors and network failures must never propagate out of emit methods."""

    @pytest.mark.anyio
    async def test_http_status_error_is_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 500 response from the dashboard must not raise in the caller."""
        import httpx

        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(),
            )
        )
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            # Must not raise
            await emitter.emit_task_started("task-1")
            await asyncio.sleep(0)

    @pytest.mark.anyio
    async def test_connect_error_is_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A network connection error must not raise in the caller."""
        import httpx

        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_task_completed("task-1")
            await asyncio.sleep(0)

    @pytest.mark.anyio
    async def test_timeout_error_is_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A request timeout must not raise in the caller."""
        import httpx

        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_job_failed("repo", 1)
            await asyncio.sleep(0)

    @pytest.mark.anyio
    async def test_generic_exception_is_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Any unexpected exception during POST must not propagate."""
        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=RuntimeError("unexpected!"))
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_round_result("task-1", 1, passed=True)
            await asyncio.sleep(0)

    @pytest.mark.anyio
    async def test_error_does_not_affect_subsequent_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After a POST failure, subsequent emit calls must still work."""
        import httpx

        monkeypatch.setenv("DASHBOARD_URL", "http://dashboard:8000")
        from factory.dashboard.emitter import EventEmitter

        call_count = 0
        response_mock = MagicMock()
        response_mock.raise_for_status = MagicMock()

        async def side_effect(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("first call fails")
            return response_mock

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=side_effect)
        with patch("factory.dashboard.emitter.httpx", _patch_httpx(mock_client)):
            emitter = EventEmitter()
            await emitter.emit_task_started("task-1")
            await asyncio.sleep(0)
            await emitter.emit_task_completed("task-1")
            await asyncio.sleep(0)

        # Second call should succeed — no exception raised
        assert call_count >= 2


# ---------------------------------------------------------------------------
# .env.example
# ---------------------------------------------------------------------------


class TestEnvExample:
    """.env.example includes DASHBOARD_URL placeholder."""

    def test_env_example_has_dashboard_url(self) -> None:
        """DASHBOARD_URL must appear in .env.example."""
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.is_file(), ".env.example not found"
        contents = env_example.read_text()
        assert "DASHBOARD_URL" in contents, "DASHBOARD_URL missing from .env.example"

    def test_env_example_dashboard_url_has_value(self) -> None:
        """DASHBOARD_URL in .env.example must have a placeholder value (not blank)."""
        env_example = PROJECT_ROOT / ".env.example"
        for line in env_example.read_text().splitlines():
            if line.startswith("DASHBOARD_URL"):
                assert "=" in line, "DASHBOARD_URL line has no '='"
                value = line.split("=", 1)[1].strip()
                assert value, "DASHBOARD_URL has no placeholder value in .env.example"
                return
        pytest.fail("DASHBOARD_URL not found in .env.example")


# ---------------------------------------------------------------------------
# pyproject.toml dependency
# ---------------------------------------------------------------------------


class TestDependencies:
    """httpx is listed as a main (non-dev) dependency in pyproject.toml."""

    def test_httpx_in_main_dependencies(self) -> None:
        """httpx must appear in [project.dependencies] in pyproject.toml."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        assert pyproject.is_file(), "pyproject.toml not found"
        content = pyproject.read_text()
        # Look for httpx under [project.dependencies], not just dev
        # Simple check: httpx appears before the [project.optional-dependencies] section
        deps_section_start = content.find("[project.dependencies]")
        optional_section_start = content.find("[project.optional-dependencies]")
        if deps_section_start == -1:
            # Inline table style
            assert "httpx" in content, "httpx not found in pyproject.toml"
            return
        deps_section = content[deps_section_start:optional_section_start] if optional_section_start != -1 else content[deps_section_start:]
        assert "httpx" in deps_section, (
            "httpx not found in [project.dependencies]. "
            "It must be a main dependency, not just a dev dependency."
        )


# ---------------------------------------------------------------------------
# Orchestrator integration — structural checks
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    """factory.orchestrator must import and use EventEmitter at lifecycle points."""

    def _get_orchestrator_source(self) -> str:
        import factory.orchestrator as orch

        return inspect.getsource(orch)

    def test_orchestrator_imports_event_emitter(self) -> None:
        """factory.orchestrator must import EventEmitter."""
        source = self._get_orchestrator_source()
        assert "EventEmitter" in source, (
            "factory.orchestrator does not reference EventEmitter. "
            "It must import and use EventEmitter."
        )

    def test_orchestrator_calls_emit_job_started(self) -> None:
        """run_job() must call emit_job_started."""
        source = self._get_orchestrator_source()
        assert "emit_job_started" in source, (
            "orchestrator does not call emit_job_started"
        )

    def test_orchestrator_calls_emit_job_completed(self) -> None:
        """run_job() must call emit_job_completed."""
        source = self._get_orchestrator_source()
        assert "emit_job_completed" in source, (
            "orchestrator does not call emit_job_completed"
        )

    def test_orchestrator_calls_emit_job_failed(self) -> None:
        """run_job() must call emit_job_failed."""
        source = self._get_orchestrator_source()
        assert "emit_job_failed" in source, (
            "orchestrator does not call emit_job_failed"
        )

    def test_orchestrator_calls_emit_agent_spawned(self) -> None:
        """orchestrator must call emit_agent_spawned when spawning agents."""
        source = self._get_orchestrator_source()
        assert "emit_agent_spawned" in source, (
            "orchestrator does not call emit_agent_spawned"
        )

    def test_orchestrator_calls_emit_agent_exited(self) -> None:
        """orchestrator must call emit_agent_exited after agents complete."""
        source = self._get_orchestrator_source()
        assert "emit_agent_exited" in source, (
            "orchestrator does not call emit_agent_exited"
        )

    def test_orchestrator_calls_emit_task_started(self) -> None:
        """orchestrator must call emit_task_started when beginning each task."""
        source = self._get_orchestrator_source()
        assert "emit_task_started" in source, (
            "orchestrator does not call emit_task_started"
        )

    def test_orchestrator_calls_emit_task_completed(self) -> None:
        """orchestrator must call emit_task_completed on task success."""
        source = self._get_orchestrator_source()
        assert "emit_task_completed" in source, (
            "orchestrator does not call emit_task_completed"
        )

    def test_orchestrator_calls_emit_task_failed(self) -> None:
        """orchestrator must call emit_task_failed after MAX_ROUNDS exhausted."""
        source = self._get_orchestrator_source()
        assert "emit_task_failed" in source, (
            "orchestrator does not call emit_task_failed"
        )

    def test_orchestrator_calls_emit_round_result(self) -> None:
        """orchestrator must call emit_round_result after each red/green round."""
        source = self._get_orchestrator_source()
        assert "emit_round_result" in source, (
            "orchestrator does not call emit_round_result"
        )

    def test_orchestrator_creates_emitter_in_run_job(self) -> None:
        """run_job() must instantiate EventEmitter (not just define it)."""
        source = self._get_orchestrator_source()
        # Check that EventEmitter() is called somewhere in the source
        assert "EventEmitter()" in source, (
            "run_job() does not instantiate EventEmitter(). "
            "An emitter must be created at the start of the job."
        )
