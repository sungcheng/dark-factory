"""Generator agent — spawns the Developer to write code."""

from __future__ import annotations

import logging

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import load_prompt
from factory.agents.base import run_agent
from factory.guardrails import detect_tech_stack
from factory.guardrails import generate_dependency_prompt
from factory.guardrails import generate_file_boundary_prompt
from factory.standards import load_standards_for_role

LOG = logging.getLogger(__name__)


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

    # Inject guardrails
    tech_stack = detect_tech_stack(working_dir)
    guardrail_sections = "\n\n".join(
        s
        for s in [
            tech_stack.as_guardrail_prompt(),
            generate_file_boundary_prompt(task_title),
            generate_dependency_prompt(working_dir),
        ]
        if s
    )

    # Inject role-specific standards (trimmed from CONVENTIONS + STYLEGUIDE)
    standards = load_standards_for_role(working_dir, "Developer")

    prompt = (
        f"{system_prompt}\n\n"
        f"{standards}\n\n"
        f"---\n\n"
        f"{guardrail_sections}\n\n"
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
        + "1. Read ARCHITECTURE.md and relevant CONTEXT.md files\n"
        "2. Write code in `src/` to implement the feature\n"
        "3. Write tests in `tests/` that validate the acceptance criteria\n"
        "4. Run `make test` to verify all tests pass\n"
        "5. Run `make check` to verify lint/types\n"
        "6. Update CONTEXT.md for any modules you changed"
    )

    config = AgentConfig(
        role="Developer",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        working_dir=working_dir,
        model=model,
    )

    return await run_agent(config)
