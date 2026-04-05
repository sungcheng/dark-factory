"""Tests for session state persistence."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from factory.github_client import TaskInfo
from factory.state import JobState
from factory.state import clear_state
from factory.state import load_state
from factory.state import save_state


class TestJobState:
    """Tests for JobState dataclass."""

    def test_defaults(self) -> None:
        """JobState has sensible defaults."""
        state = JobState(repo_name="test", issue_number=1)
        assert state.status == "in_progress"
        assert state.tasks == []
        assert state.working_dir == ""
        assert state.branch == ""


class TestSaveAndLoad:
    """Tests for state persistence."""

    def test_save_and_load(self) -> None:
        """State survives save/load roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            with patch("factory.state.STATE_DIR", state_dir):
                state = JobState(
                    repo_name="weather-api",
                    issue_number=42,
                    working_dir="/tmp/work",
                    branch="factory/issue-42",
                    status="in_progress",
                    tasks=[
                        TaskInfo(
                            id="t1",
                            title="Setup",
                            description="Do setup",
                            acceptance_criteria=["it works"],
                            depends_on=[],
                            status="completed",
                        ),
                        TaskInfo(
                            id="t2",
                            title="Build",
                            description="Build it",
                            acceptance_criteria=["it builds"],
                            depends_on=["t1"],
                            status="pending",
                        ),
                    ],
                )

                save_state(state)
                loaded = load_state("weather-api", 42)

                assert loaded is not None
                assert loaded.repo_name == "weather-api"
                assert loaded.issue_number == 42
                assert loaded.working_dir == "/tmp/work"
                assert loaded.branch == "factory/issue-42"
                assert len(loaded.tasks) == 2
                assert loaded.tasks[0].status == "completed"
                assert loaded.tasks[1].depends_on == ["t1"]

    def test_load_nonexistent(self) -> None:
        """Loading missing state returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("factory.state.STATE_DIR", Path(tmpdir)):
                result = load_state("nope", 999)
                assert result is None

    def test_load_completed_returns_none(self) -> None:
        """Completed jobs are not resumed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            with patch("factory.state.STATE_DIR", state_dir):
                state = JobState(
                    repo_name="done-repo",
                    issue_number=1,
                    status="completed",
                )
                save_state(state)
                result = load_state("done-repo", 1)
                assert result is None

    def test_load_corrupt_returns_none(self) -> None:
        """Corrupt state file returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            with patch("factory.state.STATE_DIR", state_dir):
                path = state_dir / "bad-repo-1.json"
                state_dir.mkdir(parents=True, exist_ok=True)
                path.write_text("not valid json{{{")
                result = load_state("bad-repo", 1)
                assert result is None

    def test_clear_state(self) -> None:
        """Clearing state deletes the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            with patch("factory.state.STATE_DIR", state_dir):
                state = JobState(repo_name="clear-me", issue_number=5)
                save_state(state)
                clear_state("clear-me", 5)
                result = load_state("clear-me", 5)
                assert result is None
