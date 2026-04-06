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
    # Inject guardrails
    tech_stack = detect_tech_stack(working_dir)
    guardrail_context = tech_stack.as_guardrail_prompt()

    prompt = (
        "You are the Developer. **First, read all existing files in `src/`** to "
        "understand what code already exists, what patterns are used, and what you "
        "can build on. Then read `contracts.md` which defines the interface "
        "contracts for this task — function signatures, API routes, types, and "
        "file locations.\n\n"
        "Your job is to **scaffold** the code:\n"
        "1. Read existing `src/` code — do NOT duplicate or overwrite what exists\n"
        "2. Create only NEW files listed in contracts.md that don't already exist\n"
        "3. Write function stubs with correct signatures and type hints\n"
        "4. Create Pydantic models / dataclasses as specified\n"
        "5. Set up API routes with placeholder implementations\n"
        "6. Add imports and basic project wiring\n\n"
        "Do NOT implement full business logic yet — just get the structure right "
        "so the tests have something to import. The red-green cycle will fill in "
        "the real implementation.\n\n"
        "Do NOT modify any files in `tests/`.\n\n"
        f"{guardrail_context}\n\n"
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

    prompt = (
        f"{system_prompt}\n\n"
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


async def run_staff_review(
    issue_title: str,
    issue_body: str,
    working_dir: str,
    model: str | None = None,
) -> AgentResult:
    """Spawn a Staff Engineer to review and optimize the completed codebase.

    Runs after all tasks are merged. Reads the full codebase against
    the original issue requirements and makes targeted improvements:
    code quality, performance, error handling, missing edge cases.
    """
    prompt = (
        "You are a **Staff Engineer** doing a final review of code that was "
        "written by a junior developer. Your job is to:\n\n"
        "1. **Read the original issue** (below) to understand what was requested\n"
        "2. **Read ALL source code** in `src/` — understand the full implementation\n"
        "3. **Read ALL tests** in `tests/` — understand test coverage\n"
        "4. **Make targeted improvements**:\n"
        "   - Fix any code smells, anti-patterns, or inefficiencies\n"
        "   - Add missing error handling at system boundaries\n"
        "   - Improve naming, structure, and readability\n"
        "   - Remove dead code, unused imports, duplicated logic\n"
        "   - Optimize hot paths (DB queries, API calls, loops)\n"
        "   - Add missing type hints\n"
        "5. **Do NOT**: rewrite working code for style preferences, "
        "add unnecessary abstractions, or change the architecture\n"
        "6. Run `make test` and `make check` after changes — "
        "everything must still pass\n\n"
        "Keep changes surgical. If the code is already good, say so and "
        "make no changes. Don't change tests unless they have bugs.\n\n"
        f"---\n\n"
        f"## Original Issue\n\n"
        f"**Title**: {issue_title}\n\n"
        f"**Requirements**:\n{issue_body}\n"
    )

    config = AgentConfig(
        role="Staff Engineer",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        working_dir=working_dir,
        model=model or "opus",
    )

    return await run_agent(config)
