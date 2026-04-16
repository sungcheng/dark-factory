"""Arbiter agent — resolves QA/Developer deadlocks with a binding ruling."""

from __future__ import annotations

import logging

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import load_prompt
from factory.agents.base import run_agent

LOG = logging.getLogger(__name__)


async def run_arbiter(
    task_title: str,
    round_number: int,
    working_dir: str,
    model: str | None = None,
) -> AgentResult:
    """Spawn the Arbiter to resolve a QA/Developer disagreement.

    Called by the orchestrator when QA rejects with similar feedback
    for two consecutive rounds. Reads feedback.md, disagreement.md (if
    present), the code, and the test output — then writes arbitration.md
    with a binding ruling.
    """
    system_prompt = load_prompt("arbiter")

    prompt = (
        f"{system_prompt}\n\n"
        f"---\n\n"
        f"## Dispute Context\n\n"
        f"**Task**: {task_title}\n"
        f"**Round**: {round_number}\n\n"
        f"QA and Developer have been going back and forth without resolution. "
        f"Read `feedback.md` for QA's complaint and `disagreement.md` (if it "
        f"exists) for Developer's pushback. Read the relevant source and test "
        f"files. Then write `arbitration.md` with your ruling.\n"
    )

    config = AgentConfig(
        role="Arbiter",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Glob", "Grep", "Bash"],
        working_dir=working_dir,
        max_turns=30,
        model=model or "opus",
    )

    return await run_agent(config)
