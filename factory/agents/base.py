"""Base agent runner — spawns Claude Code subprocesses."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

LOG = logging.getLogger(__name__)

# Default model assignments per role (cheap for coordination, powerful for coding)
DEFAULT_MODELS: dict[str, str] = {
    "Architect": "opus",
    "QA Engineer (Review)": "sonnet",
    "QA Engineer (Regression)": "haiku",
    "Developer": "sonnet",
    "QA Lead": "opus",
}

# Timeout per role in seconds
DEFAULT_TIMEOUTS: dict[str, int] = {
    "Architect": 1200,  # 20 min
    "Developer": 1800,  # 30 min — heaviest work
    "QA Engineer (Review)": 600,  # 10 min
    "QA Engineer (Regression)": 300,  # 5 min
    "QA Lead": 1800,  # 30 min — reads everything
}


@dataclass
class AgentResult:
    """Result from a Claude Code subprocess."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass
class AgentConfig:
    """Configuration for spawning a Claude Code agent."""

    role: str
    prompt: str
    allowed_tools: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    working_dir: str = "."
    max_turns: int = 50
    model: str | None = None


def load_prompt(prompt_name: str) -> str:
    """Load a prompt template from factory/prompts/."""
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{prompt_name}.md"
    return prompt_path.read_text()


async def run_agent(config: AgentConfig) -> AgentResult:
    """Spawn a Claude Code subprocess with fresh context.

    Each agent gets its own process — no shared memory, no context bleed.
    The orchestrator controls what tools each agent can access.
    """
    model = config.model or DEFAULT_MODELS.get(config.role, "sonnet")
    cmd = [
        "claude",
        "-p",
        config.prompt,
        "--output-format",
        "json",
        "--model",
        model,
    ]

    if config.allowed_tools:
        cmd.extend(["--allowedTools", ",".join(config.allowed_tools)])

    LOG.info("  🤖 Spawning %s (model=%s)", config.role, model)

    import os
    import signal

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=config.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=None,  # Let stderr stream to terminal for visibility
            start_new_session=True,  # Create process group for clean cleanup
        )
        timeout = DEFAULT_TIMEOUTS.get(config.role, 1200)
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
    except TimeoutError:
        timeout = DEFAULT_TIMEOUTS.get(config.role, 1200)
        LOG.error(
            "%s agent timed out after %ds — killing process group",
            config.role,
            timeout,
        )
        # Kill the entire process group (agent + all child processes like pytest)
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            await asyncio.sleep(2)
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return AgentResult(exit_code=1, stdout="", stderr="Agent timed out")

    exit_code = proc.returncode or 1
    stdout_str = stdout_bytes.decode()

    LOG.info("  %s agent exited (code=%d)", config.role, exit_code)

    if exit_code != 0:
        # Parse JSON output to understand the exit
        try:
            data = json.loads(stdout_str)
            reason = data.get("terminal_reason", "unknown")
            denials = data.get("permission_denials", [])
            result_text = data.get("result", "")[:200]
            if reason == "completed" and not denials:
                LOG.info(
                    "  %s completed (exit code 1 is a CLI quirk): %s",
                    config.role,
                    result_text,
                )
            else:
                LOG.warning(
                    "  ⚠️ %s — reason: %s, denials: %d, result: %s",
                    config.role,
                    reason,
                    len(denials),
                    result_text,
                )
        except (json.JSONDecodeError, TypeError):
            LOG.warning("  ⚠️ %s — raw output: %s", config.role, stdout_str[:300])

    return AgentResult(
        exit_code=exit_code,
        stdout=stdout_str,
        stderr="",
    )


def parse_agent_output(result: AgentResult) -> dict[str, object]:
    """Parse JSON output from Claude Code."""
    try:
        data: dict[str, object] = json.loads(result.stdout)
        return data
    except (json.JSONDecodeError, TypeError):
        return {"raw": result.stdout}
