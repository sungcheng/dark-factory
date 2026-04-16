"""Tests for Phase 4 stage handlers.

These verify the decomposition wiring: handlers pull JobRuntime out of
PipelineContext, call the underlying orchestrator helpers, and return a
NodeResult with the expected status. Deep behavior is covered by
existing orchestrator tests — these tests lock the contract between
the engine and the stage layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from factory.pipeline.engine import PipelineContext
from factory.pipeline.handlers import HANDLERS
from factory.pipeline.job_runtime import RUNTIME_KEY
from factory.pipeline.job_runtime import JobRuntime
from factory.pipeline.schema import Node


@dataclass
class _FakeTechStack:
    def summary(self) -> str:
        return "python/fastapi"

    def as_guardrail_prompt(self) -> str:
        return ""


def _runtime_stub() -> JobRuntime:
    """Build a JobRuntime with no-op stubs covering every handler's preconditions."""
    emitter = MagicMock()
    emitter.emit_log = AsyncMock()
    emitter.update_job_tasks = AsyncMock()
    emitter.emit_job_completed = AsyncMock()

    github = MagicMock()
    github.cleanup_orphaned_issues.return_value = 0
    github.cleanup_stale_prs.return_value = 0
    github.close_stale_sub_issues.return_value = 0
    github.create_sub_issues.side_effect = lambda _repo, _issue, tasks: tasks

    job_ctx = MagicMock()
    job_ctx.working_dir = "/tmp/df-runtime-stub"
    job_ctx.branch = ""
    job_ctx.tasks = []

    state = MagicMock()
    state.tasks = []
    state.working_dir = ""
    state.branch = ""
    state.status = "in_progress"

    issue = MagicMock()
    issue.title = "Test issue"
    issue.body = "- criterion a\n- criterion b\n"

    preflight = SimpleNamespace(
        passed=True,
        blocking_reasons=[],
        secret_findings=[],
        tech_stack=_FakeTechStack(),
    )

    return JobRuntime(
        repo_name="acme",
        issue_number=1,
        model=None,
        merge_mode="auto",
        github=github,
        emitter=emitter,
        state=state,
        ctx=job_ctx,
        issue=issue,
        preflight=preflight,
    )


def _ctx_with(runtime: JobRuntime) -> PipelineContext:
    ctx = PipelineContext(working_dir=".")
    ctx.state[RUNTIME_KEY] = runtime
    return ctx


def test_every_phase4_handler_registered() -> None:
    expected = {
        "job_setup",
        "clone_repo",
        "preflight",
        "pre_job_skills",
        "regression_gate",
        "architect",
        "create_sub_issues",
        "process_batches",
        "post_merge_validation",
        "qa_lead_review",
        "post_job_skills",
    }
    assert expected.issubset(HANDLERS)


@pytest.mark.anyio
async def test_preflight_handler_fails_when_preflight_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from factory.pipeline.handlers.stages import preflight_handler

    blocked = SimpleNamespace(
        passed=False,
        blocking_reasons=["secret detected"],
        secret_findings=[],
        tech_stack=_FakeTechStack(),
    )
    monkeypatch.setattr(
        "factory.guardrails.run_preflight_checks",
        lambda _wd: blocked,
    )
    runtime = _runtime_stub()
    result = await preflight_handler(
        Node(id="preflight", handler="preflight"),
        _ctx_with(runtime),
    )
    assert result.status == "failed"
    assert "Pre-flight" in result.message


@pytest.mark.anyio
async def test_architect_handler_fast_tracks_simple_issue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from factory.pipeline.handlers.stages import architect_handler

    monkeypatch.setattr("factory.orchestrator._is_simple_issue", lambda *_a: True)
    monkeypatch.setattr("factory.state.save_state", lambda _s: None)

    runtime = _runtime_stub()
    result = await architect_handler(
        Node(id="architect", handler="architect"),
        _ctx_with(runtime),
    )
    assert result.status == "success"
    assert runtime.ctx is not None
    assert len(runtime.ctx.tasks) == 1
    assert runtime.ctx.tasks[0].id == "task-1"


@pytest.mark.anyio
async def test_regression_gate_skips_when_no_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from factory.pipeline.handlers.stages import regression_gate_handler

    async def no_tests(_wd: str) -> bool:
        return False

    monkeypatch.setattr("factory.orchestrator._has_tests", no_tests)

    runtime = _runtime_stub()
    result = await regression_gate_handler(
        Node(id="regression_gate", handler="regression_gate"),
        _ctx_with(runtime),
    )
    assert result.status == "success"
    assert runtime.has_existing_tests is False


@pytest.mark.anyio
async def test_get_runtime_raises_when_setup_skipped() -> None:
    from factory.pipeline.handlers.stages import clone_repo_handler

    with pytest.raises(RuntimeError, match="JobRuntime not found"):
        await clone_repo_handler(
            Node(id="clone_repo", handler="clone_repo"),
            PipelineContext(working_dir="."),
        )
