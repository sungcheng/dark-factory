"""Tests for the orchestrator — task batching and job flow."""

from __future__ import annotations

import pytest

from factory.github_client import SubTaskInfo
from factory.github_client import TaskInfo
from factory.orchestrator import get_ready_batches
from factory.orchestrator import get_ready_subtask_batches


class TestGetReadyBatches:
    """Tests for dependency-aware task batching."""

    def test_single_task_no_deps(self) -> None:
        """A single task with no dependencies yields one batch."""
        tasks = [
            TaskInfo(
                id="t1",
                title="Setup",
                description="",
                acceptance_criteria=[],
                depends_on=[],
            ),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 1
        assert [t.id for t in batches[0]] == ["t1"]

    def test_sequential_tasks(self) -> None:
        """Tasks that depend on each other run sequentially."""
        tasks = [
            TaskInfo(
                id="t1",
                title="First",
                description="",
                acceptance_criteria=[],
                depends_on=[],
            ),
            TaskInfo(
                id="t2",
                title="Second",
                description="",
                acceptance_criteria=[],
                depends_on=["t1"],
            ),
            TaskInfo(
                id="t3",
                title="Third",
                description="",
                acceptance_criteria=[],
                depends_on=["t2"],
            ),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 3
        assert [t.id for t in batches[0]] == ["t1"]
        assert [t.id for t in batches[1]] == ["t2"]
        assert [t.id for t in batches[2]] == ["t3"]

    def test_parallel_tasks(self) -> None:
        """Tasks with same dependency run in parallel."""
        tasks = [
            TaskInfo(
                id="t1",
                title="Setup",
                description="",
                acceptance_criteria=[],
                depends_on=[],
            ),
            TaskInfo(
                id="t2",
                title="Health",
                description="",
                acceptance_criteria=[],
                depends_on=["t1"],
            ),
            TaskInfo(
                id="t3",
                title="Client",
                description="",
                acceptance_criteria=[],
                depends_on=["t1"],
            ),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 2
        assert [t.id for t in batches[0]] == ["t1"]
        assert sorted(t.id for t in batches[1]) == ["t2", "t3"]

    def test_diamond_dependency(self) -> None:
        """Diamond pattern: t1 -> t2,t3 -> t4."""
        tasks = [
            TaskInfo(
                id="t1",
                title="Setup",
                description="",
                acceptance_criteria=[],
                depends_on=[],
            ),
            TaskInfo(
                id="t2",
                title="A",
                description="",
                acceptance_criteria=[],
                depends_on=["t1"],
            ),
            TaskInfo(
                id="t3",
                title="B",
                description="",
                acceptance_criteria=[],
                depends_on=["t1"],
            ),
            TaskInfo(
                id="t4",
                title="Final",
                description="",
                acceptance_criteria=[],
                depends_on=["t2", "t3"],
            ),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 3
        assert [t.id for t in batches[0]] == ["t1"]
        assert sorted(t.id for t in batches[1]) == ["t2", "t3"]
        assert [t.id for t in batches[2]] == ["t4"]

    def test_all_independent(self) -> None:
        """Tasks with no dependencies all run in one batch."""
        tasks = [
            TaskInfo(
                id="t1",
                title="A",
                description="",
                acceptance_criteria=[],
                depends_on=[],
            ),
            TaskInfo(
                id="t2",
                title="B",
                description="",
                acceptance_criteria=[],
                depends_on=[],
            ),
            TaskInfo(
                id="t3",
                title="C",
                description="",
                acceptance_criteria=[],
                depends_on=[],
            ),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 1
        assert sorted(t.id for t in batches[0]) == ["t1", "t2", "t3"]

    def test_deadlock_raises(self) -> None:
        """Circular dependency raises RuntimeError."""
        tasks = [
            TaskInfo(
                id="t1",
                title="A",
                description="",
                acceptance_criteria=[],
                depends_on=["t2"],
            ),
            TaskInfo(
                id="t2",
                title="B",
                description="",
                acceptance_criteria=[],
                depends_on=["t1"],
            ),
        ]
        with pytest.raises(RuntimeError, match="Deadlock"):
            list(get_ready_batches(tasks))

    def test_empty_tasks(self) -> None:
        """Empty task list yields no batches."""
        batches = list(get_ready_batches([]))
        assert batches == []

    def test_skip_completed_tasks(self) -> None:
        """Already-completed tasks are skipped when resuming."""
        tasks = [
            TaskInfo(
                id="t1",
                title="Done",
                description="",
                acceptance_criteria=[],
                depends_on=[],
                status="completed",
            ),
            TaskInfo(
                id="t2",
                title="Next",
                description="",
                acceptance_criteria=[],
                depends_on=["t1"],
            ),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 1
        assert [t.id for t in batches[0]] == ["t2"]

    def test_resume_with_mixed_status(self) -> None:
        """Resume with some completed, some pending."""
        tasks = [
            TaskInfo(
                id="t1",
                title="Done1",
                description="",
                acceptance_criteria=[],
                depends_on=[],
                status="completed",
            ),
            TaskInfo(
                id="t2",
                title="Done2",
                description="",
                acceptance_criteria=[],
                depends_on=["t1"],
                status="completed",
            ),
            TaskInfo(
                id="t3",
                title="Pending",
                description="",
                acceptance_criteria=[],
                depends_on=["t2"],
            ),
            TaskInfo(
                id="t4",
                title="Also Pending",
                description="",
                acceptance_criteria=[],
                depends_on=["t2"],
            ),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 1
        assert sorted(t.id for t in batches[0]) == ["t3", "t4"]


class TestGetReadySubtaskBatches:
    """Tests for subtask dependency batching."""

    def _sub(
        self,
        sub_id: str,
        depends_on: list[str] | None = None,
        status: str = "pending",
    ) -> SubTaskInfo:
        return SubTaskInfo(
            id=sub_id,
            title=sub_id,
            description="",
            acceptance_criteria=[],
            depends_on=depends_on or [],
            status=status,
        )

    def test_independent_subtasks_one_batch(self) -> None:
        """Subtasks with no deps yield one batch."""
        subs = [self._sub("s1"), self._sub("s2"), self._sub("s3")]
        batches = list(get_ready_subtask_batches(subs))
        assert len(batches) == 1
        assert sorted(s.id for s in batches[0]) == ["s1", "s2", "s3"]

    def test_sequential_subtasks(self) -> None:
        """Subtasks with chain deps yield sequential batches."""
        subs = [
            self._sub("s1"),
            self._sub("s2", depends_on=["s1"]),
            self._sub("s3", depends_on=["s2"]),
        ]
        batches = list(get_ready_subtask_batches(subs))
        assert len(batches) == 3
        assert [s.id for s in batches[0]] == ["s1"]
        assert [s.id for s in batches[1]] == ["s2"]
        assert [s.id for s in batches[2]] == ["s3"]

    def test_diamond_subtask_deps(self) -> None:
        """Diamond pattern: s1 -> s2,s3 -> s4."""
        subs = [
            self._sub("s1"),
            self._sub("s2", depends_on=["s1"]),
            self._sub("s3", depends_on=["s1"]),
            self._sub("s4", depends_on=["s2", "s3"]),
        ]
        batches = list(get_ready_subtask_batches(subs))
        assert len(batches) == 3
        assert sorted(s.id for s in batches[1]) == ["s2", "s3"]
        assert [s.id for s in batches[2]] == ["s4"]

    def test_skip_completed_subtasks(self) -> None:
        """Completed subtasks are skipped on resume."""
        subs = [
            self._sub("s1", status="completed"),
            self._sub("s2", depends_on=["s1"]),
        ]
        batches = list(get_ready_subtask_batches(subs))
        assert len(batches) == 1
        assert [s.id for s in batches[0]] == ["s2"]

    def test_empty_subtasks(self) -> None:
        """Empty list yields no batches."""
        assert list(get_ready_subtask_batches([])) == []

    def test_deadlock_raises(self) -> None:
        """Circular subtask deps raise RuntimeError."""
        subs = [
            self._sub("s1", depends_on=["s2"]),
            self._sub("s2", depends_on=["s1"]),
        ]
        with pytest.raises(RuntimeError, match="Subtask deadlock"):
            list(get_ready_subtask_batches(subs))


class TestTaskInfoSubtasks:
    """Tests for TaskInfo subtask properties."""

    def test_has_subtasks_false(self) -> None:
        """Task without subtasks returns False."""
        task = TaskInfo(
            id="t1",
            title="",
            description="",
            acceptance_criteria=[],
            depends_on=[],
        )
        assert not task.has_subtasks

    def test_has_subtasks_true(self) -> None:
        """Task with subtasks returns True."""
        task = TaskInfo(
            id="t1",
            title="",
            description="",
            acceptance_criteria=[],
            depends_on=[],
            subtasks=[
                SubTaskInfo(
                    id="s1",
                    title="",
                    description="",
                    acceptance_criteria=[],
                    depends_on=[],
                ),
            ],
        )
        assert task.has_subtasks

    def test_all_subtasks_completed(self) -> None:
        """all_subtasks_completed returns True when all done."""
        task = TaskInfo(
            id="t1",
            title="",
            description="",
            acceptance_criteria=[],
            depends_on=[],
            subtasks=[
                SubTaskInfo(
                    id="s1",
                    title="",
                    description="",
                    acceptance_criteria=[],
                    depends_on=[],
                    status="completed",
                ),
                SubTaskInfo(
                    id="s2",
                    title="",
                    description="",
                    acceptance_criteria=[],
                    depends_on=[],
                    status="completed",
                ),
            ],
        )
        assert task.all_subtasks_completed

    def test_any_subtask_failed(self) -> None:
        """any_subtask_failed returns True when one has failed."""
        task = TaskInfo(
            id="t1",
            title="",
            description="",
            acceptance_criteria=[],
            depends_on=[],
            subtasks=[
                SubTaskInfo(
                    id="s1",
                    title="",
                    description="",
                    acceptance_criteria=[],
                    depends_on=[],
                    status="completed",
                ),
                SubTaskInfo(
                    id="s2",
                    title="",
                    description="",
                    acceptance_criteria=[],
                    depends_on=[],
                    status="failed",
                ),
            ],
        )
        assert task.any_subtask_failed

    def test_backward_compat_no_subtasks(self) -> None:
        """Tasks without subtasks work exactly as before."""
        tasks = [
            TaskInfo(
                id="t1",
                title="A",
                description="",
                acceptance_criteria=[],
                depends_on=[],
            ),
            TaskInfo(
                id="t2",
                title="B",
                description="",
                acceptance_criteria=[],
                depends_on=["t1"],
            ),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 2
        assert not tasks[0].has_subtasks
        assert not tasks[1].has_subtasks
