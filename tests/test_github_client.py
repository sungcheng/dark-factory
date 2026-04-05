"""Tests for GitHub client data models."""

from __future__ import annotations

from factory.github_client import JobContext
from factory.github_client import TaskInfo


class TestTaskInfo:
    """Tests for TaskInfo dataclass."""

    def test_default_status(self) -> None:
        """New tasks default to pending status."""
        task = TaskInfo(
            id="t1",
            title="Test",
            description="A task",
            acceptance_criteria=["it works"],
            depends_on=[],
        )
        assert task.status == "pending"
        assert task.issue_number is None

    def test_update_status(self) -> None:
        """Task status can be updated."""
        task = TaskInfo(
            id="t1",
            title="Test",
            description="A task",
            acceptance_criteria=[],
            depends_on=[],
        )
        task.status = "completed"
        assert task.status == "completed"

    def test_issue_number_assignment(self) -> None:
        """Issue number can be set after creation."""
        task = TaskInfo(
            id="t1",
            title="Test",
            description="",
            acceptance_criteria=[],
            depends_on=[],
        )
        task.issue_number = 42
        assert task.issue_number == 42


class TestJobContext:
    """Tests for JobContext dataclass."""

    def test_defaults(self) -> None:
        """JobContext has sensible defaults."""
        ctx = JobContext(repo_name="test-repo", issue_number=1)
        assert ctx.repo_name == "test-repo"
        assert ctx.issue_number == 1
        assert ctx.branch == ""
        assert ctx.tasks == []
        assert ctx.working_dir == ""

    def test_tasks_not_shared(self) -> None:
        """Each JobContext gets its own task list."""
        ctx1 = JobContext(repo_name="a", issue_number=1)
        ctx2 = JobContext(repo_name="b", issue_number=2)
        ctx1.tasks.append(
            TaskInfo(
                id="t1",
                title="X",
                description="",
                acceptance_criteria=[],
                depends_on=[],
            )
        )
        assert len(ctx2.tasks) == 0
