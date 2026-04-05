"""Evaluator agent — spawns the QA Engineer for tests and review."""
from __future__ import annotations

import logging

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import load_prompt
from factory.agents.base import run_agent

LOG = logging.getLogger(__name__)


async def run_evaluator_red(
    task_title: str,
    task_description: str,
    acceptance_criteria: list[str],
    working_dir: str,
    model: str | None = None,
) -> AgentResult:
    """Spawn QA Engineer to write failing tests (RED phase).

    The QA Engineer reads acceptance criteria and writes comprehensive
    failing tests. It CANNOT edit source code files.
    """
    system_prompt = load_prompt("evaluator")
    criteria_text = "\n".join(f"- {c}" for c in acceptance_criteria)

    prompt = (
        f"{system_prompt}\n\n"
        f"---\n\n"
        f"## Your Assignment — Phase 1: Write Failing Tests\n\n"
        f"### Task\n"
        f"**Title**: {task_title}\n\n"
        f"**Description**: {task_description}\n\n"
        f"### Acceptance Criteria\n{criteria_text}\n\n"
        f"---\n\n"
        f"Write failing tests for ALL acceptance criteria above. "
        f"Put tests in the `tests/` directory. "
        f"Run the tests to confirm they fail (RED). "
        f"Do NOT write any source code in `src/`."
    )

    config = AgentConfig(
        role="QA Engineer (RED)",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        working_dir=working_dir,
        model=model,
    )

    return await run_agent(config)


async def run_evaluator_contracts(
    task_title: str,
    task_description: str,
    acceptance_criteria: list[str],
    working_dir: str,
    model: str | None = None,
) -> AgentResult:
    """Spawn QA Engineer to write interface contracts before tests.

    Writes contracts.md with function signatures, API routes, types,
    and schemas. This gives the Developer a head start on scaffolding
    while the full tests are being written.
    """
    criteria_text = "\n".join(f"- {c}" for c in acceptance_criteria)

    prompt = (
        "You are the QA Engineer. Your job is to define the **interface contracts** "
        "for a task BEFORE writing tests. Write a `contracts.md` file with:\n\n"
        "1. **Function signatures** — name, parameters, return types\n"
        "2. **API routes** — method, path, request/response schemas\n"
        "3. **Types/models** — class names, fields, types\n"
        "4. **File locations** — where each module should live\n\n"
        "Be specific and concrete. The Developer will use this to start scaffolding "
        "while you write the full tests.\n\n"
        "Do NOT write tests yet. Do NOT write source code. Only write contracts.md.\n\n"
        f"---\n\n"
        f"## Task\n"
        f"**Title**: {task_title}\n\n"
        f"**Description**: {task_description}\n\n"
        f"### Acceptance Criteria\n{criteria_text}\n"
    )

    config = AgentConfig(
        role="QA Engineer (Contracts)",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        working_dir=working_dir,
        model=model,
    )

    return await run_agent(config)


async def run_evaluator_regression(
    working_dir: str,
    model: str | None = None,
) -> AgentResult:
    """Spawn QA Engineer to run existing tests as a regression gate.

    Must pass BEFORE any new work begins on a task. If existing tests
    fail, the job stops immediately.
    """
    prompt = (
        "You are the QA Engineer. Run the existing test suite with `make test`. "
        "If there are no tests yet, write `regression-pass.md` "
        "with 'No existing tests.' "
        "If all tests pass, write `regression-pass.md` with the test output. "
        "If any tests FAIL, write `regression-fail.md` with the failure details. "
        "Do NOT write any code. Do NOT modify any files except the regression report."
    )

    config = AgentConfig(
        role="QA Engineer (Regression)",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Bash", "Glob"],
        working_dir=working_dir,
        model=model,
    )

    return await run_agent(config)


async def run_evaluator_review(
    task_title: str,
    round_number: int,
    working_dir: str,
    model: str | None = None,
) -> AgentResult:
    """Spawn QA Engineer to run tests and review code (GREEN check).

    The QA Engineer runs all tests, checks code quality, and either
    writes feedback.md (RED) or approved.md (GREEN).
    """
    system_prompt = load_prompt("evaluator")

    prompt = (
        f"{system_prompt}\n\n"
        f"---\n\n"
        f"## Your Assignment — Phase 2: Review & Approve\n\n"
        f"**Task**: {task_title}\n"
        f"**Round**: {round_number} of 5\n\n"
        f"---\n\n"
        f"1. Run `make test` — check if all tests pass\n"
        f"2. Run `make check` — check lint and types\n"
        f"3. Review code quality and security\n"
        f"4. If tests FAIL: write `feedback.md` with specific issues\n"
        f"5. If tests PASS and code is good: write `approved.md`\n\n"
        f"Do NOT edit any source code. Only write feedback.md or approved.md."
    )

    config = AgentConfig(
        role="QA Engineer (Review)",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        working_dir=working_dir,
        model=model,
    )

    return await run_agent(config)
