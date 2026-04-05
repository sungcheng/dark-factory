"""Tests for agent base — config, results, prompt loading."""
from __future__ import annotations

from pathlib import Path

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import load_prompt
from factory.agents.base import parse_agent_output


class TestAgentResult:
    """Tests for AgentResult."""

    def test_success_on_zero_exit(self) -> None:
        """Exit code 0 means success."""
        result = AgentResult(exit_code=0, stdout="ok", stderr="")
        assert result.success is True

    def test_failure_on_nonzero_exit(self) -> None:
        """Non-zero exit code means failure."""
        result = AgentResult(exit_code=1, stdout="", stderr="error")
        assert result.success is False


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_defaults(self) -> None:
        """Config has sensible defaults."""
        config = AgentConfig(role="test", prompt="do something")
        assert config.allowed_tools == []
        assert config.allowed_paths == []
        assert config.working_dir == "."
        assert config.max_turns == 50


class TestLoadPrompt:
    """Tests for prompt loading."""

    def test_load_planner(self) -> None:
        """Planner prompt loads and contains key instructions."""
        prompt = load_prompt("planner")
        assert "Architect" in prompt
        assert "tasks.json" in prompt
        assert "DO NOT write any code" in prompt

    def test_load_evaluator(self) -> None:
        """Evaluator prompt loads and contains key instructions."""
        prompt = load_prompt("evaluator")
        assert "QA Engineer" in prompt
        assert "NEVER edit files in `src/`" in prompt
        assert "feedback.md" in prompt
        assert "approved.md" in prompt

    def test_load_generator(self) -> None:
        """Generator prompt loads and contains key instructions."""
        prompt = load_prompt("generator")
        assert "Developer" in prompt
        assert "NEVER modify test files" in prompt
        assert "make test" in prompt

    def test_load_nonexistent_raises(self) -> None:
        """Loading a missing prompt raises FileNotFoundError."""
        try:
            load_prompt("nonexistent")
            assert False, "Should have raised"
        except FileNotFoundError:
            pass


class TestParseAgentOutput:
    """Tests for parsing Claude CLI JSON output."""

    def test_valid_json(self) -> None:
        """Parses valid JSON output."""
        result = AgentResult(exit_code=0, stdout='{"result": "ok"}', stderr="")
        parsed = parse_agent_output(result)
        assert parsed == {"result": "ok"}

    def test_invalid_json_returns_raw(self) -> None:
        """Non-JSON output is returned as raw string."""
        result = AgentResult(exit_code=0, stdout="not json", stderr="")
        parsed = parse_agent_output(result)
        assert parsed == {"raw": "not json"}

    def test_empty_stdout(self) -> None:
        """Empty output returns raw empty string."""
        result = AgentResult(exit_code=0, stdout="", stderr="")
        parsed = parse_agent_output(result)
        assert parsed == {"raw": ""}
