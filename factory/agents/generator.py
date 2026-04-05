"""Generator agent — spawns the Developer to write code."""
from __future__ import annotations

import logging

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import load_prompt
from factory.agents.base import run_agent

LOG = logging.getLogger(__name__)


async def run_generator(
    task_title: str,
    task_description: str,
    acceptance_criteria: list[str],
    round_number: int,
    working_dir: str,
    model: str | None = None,
) -> AgentResult:
    """Spawn the Developer agent to make failing tests pass.

    The Developer reads the spec, reads failing tests, reads any
    feedback from previous rounds, and writes code in src/.
    It CANNOT modify test files.
    """
    system_prompt = load_prompt("generator")
    criteria_text = "\n".join(f"- {c}" for c in acceptance_criteria)

    feedback_note = ""
    if round_number > 1:
        feedback_note = (
            f"\n\n**IMPORTANT**: This is round {round_number}. "
            "Read `feedback.md` for specific issues from the QA Engineer. "
            "Fix every issue mentioned. Delete `feedback.md` when done."
        )

    prompt = (
        f"{system_prompt}\n\n"
        f"---\n\n"
        f"## Your Assignment\n\n"
        f"**Task**: {task_title}\n\n"
        f"**Description**: {task_description}\n\n"
        f"### Acceptance Criteria\n{criteria_text}\n\n"
        f"**Round**: {round_number} of 5\n"
        f"{feedback_note}\n\n"
        f"---\n\n"
        f"1. Read the failing tests in `tests/`\n"
        f"2. Write code in `src/` to make all tests pass\n"
        f"3. Run `make test` to verify\n"
        f"4. Run `make check` to verify lint/types\n"
        f"5. Do NOT modify any files in `tests/`"
    )

    config = AgentConfig(
        role="Developer",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        working_dir=working_dir,
        model=model,
    )

    return await run_agent(config)
