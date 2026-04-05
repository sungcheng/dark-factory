"""Generator agent — spawns the Developer to write code."""

from __future__ import annotations

import logging

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import load_prompt
from factory.agents.base import run_agent

LOG = logging.getLogger(__name__)


async def run_generator_scaffold(
    task_title: str,
    task_description: str,
    working_dir: str,
    model: str | None = None,
) -> AgentResult:
    """Spawn the Developer to scaffold code from contracts.

    Reads contracts.md and creates the file structure, function stubs,
    types, and boilerplate. Runs in parallel with QA writing tests.
    """
    prompt = (
        "You are the Developer. Read `contracts.md` which defines the interface "
        "contracts for this task — function signatures, API routes, types, and "
        "file locations.\n\n"
        "Your job is to **scaffold** the code:\n"
        "1. Create all the files listed in contracts.md\n"
        "2. Write function stubs with correct signatures and type hints\n"
        "3. Create Pydantic models / dataclasses as specified\n"
        "4. Set up API routes with placeholder implementations\n"
        "5. Add imports and basic project wiring\n\n"
        "Do NOT implement full business logic yet — just get the structure right "
        "so the tests have something to import. The red-green cycle will fill in "
        "the real implementation.\n\n"
        "Do NOT modify any files in `tests/`.\n\n"
        f"**Task**: {task_title}\n\n"
        f"**Description**: {task_description}\n"
    )

    config = AgentConfig(
        role="Developer",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        working_dir=working_dir,
        model=model,
    )

    return await run_agent(config)


async def run_generator(
    task_title: str,
    task_description: str,
    acceptance_criteria: list[str],
    round_number: int,
    working_dir: str,
    model: str | None = None,
    human_guidance: str = "",
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
        + (
            f"## Human Guidance\n\n"
            f"A human reviewed the previous failure and provided this guidance:\n\n"
            f"{human_guidance}\n\n"
            f"---\n\n"
            if human_guidance
            else ""
        )
        + "1. Read the failing tests in `tests/`\n"
        "2. Write code in `src/` to make all tests pass\n"
        "3. Run `make test` to verify\n"
        "4. Run `make check` to verify lint/types\n"
        "5. Do NOT modify any files in `tests/`"
    )

    config = AgentConfig(
        role="Developer",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        working_dir=working_dir,
        model=model,
    )

    return await run_agent(config)
