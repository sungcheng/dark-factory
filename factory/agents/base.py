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
    "Architect": "sonnet",
    "QA Engineer (RED)": "sonnet",
    "QA Engineer (Review)": "sonnet",
    "Developer": "sonnet",
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
        "claude", "-p", config.prompt,
        "--output-format", "json",
        "--model", model,
    ]

    if config.allowed_tools:
        cmd.extend(["--allowedTools", ",".join(config.allowed_tools)])

    LOG.info(
        "Spawning %s agent (model=%s) in %s",
        config.role,
        model,
        config.working_dir,
    )

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                cwd=config.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=10,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=600,  # 10 minute timeout per agent
        )
    except asyncio.TimeoutError:
        LOG.error("%s agent timed out after 600s", config.role)
        return AgentResult(exit_code=1, stdout="", stderr="Agent timed out")

    exit_code = proc.returncode or 1

    LOG.info(
        "%s agent exited with code %d",
        config.role,
        exit_code,
    )

    return AgentResult(
        exit_code=exit_code,
        stdout=stdout_bytes.decode(),
        stderr=stderr_bytes.decode(),
    )


def parse_agent_output(result: AgentResult) -> dict:
    """Parse JSON output from Claude Code."""
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {"raw": result.stdout}
