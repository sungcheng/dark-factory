"""Evaluator agent — spawns the QA Engineer for tests and review."""

from __future__ import annotations

import logging

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import load_prompt
from factory.agents.base import run_agent
from factory.standards import load_standards_for_role

LOG = logging.getLogger(__name__)


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
    """Spawn QA Engineer for final review after Developer passes tests.

    Verifies that tests actually cover the acceptance criteria and
    aren't just rubber-stamping the implementation.
    """
    system_prompt = load_prompt("evaluator")
    standards = load_standards_for_role(working_dir, "QA Engineer")

    prompt = (
        f"{system_prompt}\n\n"
        f"{standards}\n\n"
        f"---\n\n"
        f"## Your Assignment — Final Review\n\n"
        f"**Task**: {task_title}\n"
        f"**Round**: {round_number} of 5\n\n"
        f"---\n\n"
        f"1. Run `make test` — all tests must pass\n"
        f"2. Run `make check` — lint and types must be clean\n"
        f"3. **Review test quality** — do tests validate the acceptance "
        f"criteria, or just test the implementation? This is your key job.\n"
        f"4. Check code quality, security, no hardcoded secrets\n"
        f"5. If everything good: write `approved.md`\n"
        f"6. If tests don't cover the spec or quality is poor: "
        f"write `feedback.md` with specific issues\n\n"
        f"Do NOT edit source code or test files. "
        f"Only write feedback.md or approved.md."
    )

    config = AgentConfig(
        role="QA Engineer (Review)",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        working_dir=working_dir,
        model=model,
    )

    return await run_agent(config)


async def run_final_review(
    issue_title: str,
    issue_body: str,
    working_dir: str,
    model: str | None = None,
) -> AgentResult:
    """Holistic QA review after all tasks are merged (opus).

    Reads the full codebase against the original issue. Checks for
    code quality, test coverage gaps, bloated tests, missing docs,
    and makes targeted improvements. Auto-reverts if changes break tests.
    """
    standards = load_standards_for_role(working_dir, "QA Lead")

    prompt = (
        "You are the **QA Lead** doing a holistic review of a completed "
        "issue. All tasks have been merged and tests pass. Your job:\n\n"
        f"{standards}\n\n"
        "1. **Read the original issue** (below)\n"
        "2. **Read `ARCHITECTURE.md`** and `CONTEXT.md` files, then "
        "deep-read source where you see issues\n"
        "3. **Review the full implementation** against the spec:\n"
        "   - Does the code satisfy the issue requirements?\n"
        "   - Edge cases the Developer missed?\n"
        "   - Tests validating spec, not just implementation?\n"
        "4. **Make targeted improvements**:\n"
        "   - Fix code smells, anti-patterns, inefficiencies\n"
        "   - Consolidate bloated/duplicate test files\n"
        "   - Add missing error handling at boundaries\n"
        "   - Remove dead code, unused imports\n"
        "5. **Update documentation**:\n"
        "   - Update `ARCHITECTURE.md` if components changed\n"
        "   - Update/create `CONTEXT.md` in modified modules\n"
        "   - Update `CHANGELOG.md`\n"
        "6. Run `make test` and `make check` — must still pass\n\n"
        "Keep changes surgical. If code is good, say so.\n\n"
        f"---\n\n"
        f"## Original Issue\n\n"
        f"**Title**: {issue_title}\n\n"
        f"**Requirements**:\n{issue_body}\n"
    )

    config = AgentConfig(
        role="QA Lead",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        working_dir=working_dir,
        model=model or "opus",
    )

    return await run_agent(config)
