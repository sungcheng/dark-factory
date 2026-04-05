"""Tests for the orchestrator — task batching and job flow."""
from __future__ import annotations

import pytest

from factory.github_client import TaskInfo
from factory.orchestrator import get_ready_batches


class TestGetReadyBatches:
    """Tests for dependency-aware task batching."""

    def test_single_task_no_deps(self) -> None:
        """A single task with no dependencies yields one batch."""
        tasks = [
            TaskInfo(id="t1", title="Setup", description="", acceptance_criteria=[], depends_on=[]),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 1
        assert [t.id for t in batches[0]] == ["t1"]

    def test_sequential_tasks(self) -> None:
        """Tasks that depend on each other run sequentially."""
        tasks = [
            TaskInfo(id="t1", title="First", description="", acceptance_criteria=[], depends_on=[]),
            TaskInfo(id="t2", title="Second", description="", acceptance_criteria=[], depends_on=["t1"]),
            TaskInfo(id="t3", title="Third", description="", acceptance_criteria=[], depends_on=["t2"]),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 3
        assert [t.id for t in batches[0]] == ["t1"]
        assert [t.id for t in batches[1]] == ["t2"]
        assert [t.id for t in batches[2]] == ["t3"]

    def test_parallel_tasks(self) -> None:
        """Tasks with same dependency run in parallel."""
        tasks = [
            TaskInfo(id="t1", title="Setup", description="", acceptance_criteria=[], depends_on=[]),
            TaskInfo(id="t2", title="Health", description="", acceptance_criteria=[], depends_on=["t1"]),
            TaskInfo(id="t3", title="Client", description="", acceptance_criteria=[], depends_on=["t1"]),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 2
        assert [t.id for t in batches[0]] == ["t1"]
        assert sorted(t.id for t in batches[1]) == ["t2", "t3"]

    def test_diamond_dependency(self) -> None:
        """Diamond pattern: t1 -> t2,t3 -> t4."""
        tasks = [
            TaskInfo(id="t1", title="Setup", description="", acceptance_criteria=[], depends_on=[]),
            TaskInfo(id="t2", title="A", description="", acceptance_criteria=[], depends_on=["t1"]),
            TaskInfo(id="t3", title="B", description="", acceptance_criteria=[], depends_on=["t1"]),
            TaskInfo(id="t4", title="Final", description="", acceptance_criteria=[], depends_on=["t2", "t3"]),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 3
        assert [t.id for t in batches[0]] == ["t1"]
        assert sorted(t.id for t in batches[1]) == ["t2", "t3"]
        assert [t.id for t in batches[2]] == ["t4"]

    def test_all_independent(self) -> None:
        """Tasks with no dependencies all run in one batch."""
        tasks = [
            TaskInfo(id="t1", title="A", description="", acceptance_criteria=[], depends_on=[]),
            TaskInfo(id="t2", title="B", description="", acceptance_criteria=[], depends_on=[]),
            TaskInfo(id="t3", title="C", description="", acceptance_criteria=[], depends_on=[]),
        ]
        batches = list(get_ready_batches(tasks))
        assert len(batches) == 1
        assert sorted(t.id for t in batches[0]) == ["t1", "t2", "t3"]

    def test_deadlock_raises(self) -> None:
        """Circular dependency raises RuntimeError."""
        tasks = [
            TaskInfo(id="t1", title="A", description="", acceptance_criteria=[], depends_on=["t2"]),
            TaskInfo(id="t2", title="B", description="", acceptance_criteria=[], depends_on=["t1"]),
        ]
        with pytest.raises(RuntimeError, match="Deadlock"):
            list(get_ready_batches(tasks))

    def test_empty_tasks(self) -> None:
        """Empty task list yields no batches."""
        batches = list(get_ready_batches([]))
        assert batches == []
