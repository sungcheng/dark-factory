"""Tests for the Conflict Resolver fallback flow.

The resolver itself (an LLM subprocess) is not unit-testable cheaply —
these tests cover the orchestrator's decision logic around it: when
the resolver returns success vs when it escalates, what happens to
the rebase state, where feedback.md lands.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from factory.github_client import TaskInfo
from factory.orchestrator import _try_resolve_rebase_conflict


@pytest.fixture
def rebase_conflict_worktree(tmp_path: Path) -> Path:
    """Create a tmp git repo with a real ongoing rebase conflict."""
    cwd = tmp_path / "repo"
    cwd.mkdir()

    def run(*args: str) -> None:
        subprocess.run(args, cwd=cwd, check=True, capture_output=True)

    run("git", "init", "-b", "main")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    run("git", "config", "commit.gpgsign", "false")

    # Base commit
    (cwd / "shared.txt").write_text("base line\n")
    run("git", "add", "shared.txt")
    run("git", "commit", "-m", "base")

    # Main advances with one version
    (cwd / "shared.txt").write_text("main version\n")
    run("git", "add", "shared.txt")
    run("git", "commit", "-m", "main change")

    # Task branch from the base with a different version
    run("git", "checkout", "-b", "task", "HEAD~1")
    (cwd / "shared.txt").write_text("task version\n")
    run("git", "add", "shared.txt")
    run("git", "commit", "-m", "task change")

    # Set up origin/main as an alias so the rebase target exists
    run("git", "update-ref", "refs/remotes/origin/main", "main")

    # Trigger the conflict
    result = subprocess.run(
        ["git", "rebase", "origin/main"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "expected rebase to conflict"
    return cwd


def _task() -> TaskInfo:
    return TaskInfo(
        id="t1",
        title="Implement shared thing",
        description="Edit shared.txt",
        acceptance_criteria=["shared.txt contains task version"],
        depends_on=[],
    )


@pytest.mark.anyio
async def test_resolver_success_continues_rebase(
    rebase_conflict_worktree: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the agent resolves + tests pass, rebase continues cleanly."""

    async def fake_resolver(**kwargs: object) -> AsyncMock:
        # Simulate the agent writing a resolved file (no conflict markers).
        (rebase_conflict_worktree / "shared.txt").write_text(
            "main version\ntask version\n",
        )
        result = AsyncMock()
        result.success = True
        return result

    monkeypatch.setattr(
        "factory.agents.conflict_resolver.run_conflict_resolver",
        fake_resolver,
    )

    async def fake_tests(_wd: str) -> tuple[bool, str]:
        return True, ""

    monkeypatch.setattr(
        "factory.orchestrator._run_tests_with_check",
        fake_tests,
    )

    ok = await _try_resolve_rebase_conflict(
        wt_dir=str(rebase_conflict_worktree),
        task=_task(),
        task_branch="task",
        rebase_stderr="conflict in shared.txt",
        model=None,
    )
    assert ok is True
    # feedback.md should NOT exist on success
    assert not (rebase_conflict_worktree / "feedback.md").exists()


@pytest.mark.anyio
async def test_resolver_leaves_markers_escalates(
    rebase_conflict_worktree: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the resolver doesn't actually clear conflict markers, escalate."""

    async def fake_resolver(**kwargs: object) -> AsyncMock:
        # Agent "runs" but leaves the file with unresolved markers.
        result = AsyncMock()
        result.success = True
        return result

    monkeypatch.setattr(
        "factory.agents.conflict_resolver.run_conflict_resolver",
        fake_resolver,
    )

    ok = await _try_resolve_rebase_conflict(
        wt_dir=str(rebase_conflict_worktree),
        task=_task(),
        task_branch="task",
        rebase_stderr="conflict in shared.txt",
        model=None,
    )
    assert ok is False
    feedback = (rebase_conflict_worktree / "feedback.md").read_text()
    assert "conflict markers" in feedback.lower()


@pytest.mark.anyio
async def test_resolver_raises_escalates(
    rebase_conflict_worktree: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the resolver raises, escalate without crashing."""

    async def bad_resolver(**kwargs: object) -> AsyncMock:
        raise RuntimeError("resolver exploded")

    monkeypatch.setattr(
        "factory.agents.conflict_resolver.run_conflict_resolver",
        bad_resolver,
    )

    ok = await _try_resolve_rebase_conflict(
        wt_dir=str(rebase_conflict_worktree),
        task=_task(),
        task_branch="task",
        rebase_stderr="conflict",
        model=None,
    )
    assert ok is False
    feedback = (rebase_conflict_worktree / "feedback.md").read_text()
    assert "resolver agent raised" in feedback


@pytest.mark.anyio
async def test_resolver_test_failure_escalates(
    rebase_conflict_worktree: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tests failing post-resolution triggers escalation (and revert)."""

    async def fake_resolver(**kwargs: object) -> AsyncMock:
        (rebase_conflict_worktree / "shared.txt").write_text("merged\n")
        result = AsyncMock()
        result.success = True
        return result

    monkeypatch.setattr(
        "factory.agents.conflict_resolver.run_conflict_resolver",
        fake_resolver,
    )

    async def fake_tests(_wd: str) -> tuple[bool, str]:
        return False, "some test failed"

    monkeypatch.setattr(
        "factory.orchestrator._run_tests_with_check",
        fake_tests,
    )

    ok = await _try_resolve_rebase_conflict(
        wt_dir=str(rebase_conflict_worktree),
        task=_task(),
        task_branch="task",
        rebase_stderr="conflict",
        model=None,
    )
    assert ok is False
    feedback = (rebase_conflict_worktree / "feedback.md").read_text()
    assert "tests failed" in feedback.lower()
