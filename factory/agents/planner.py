"""Planner agent — spawns the Architect to break issues into tasks."""
from __future__ import annotations

import logging

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import load_prompt
from factory.agents.base import run_agent

LOG = logging.getLogger(__name__)


def run_planner(
    issue_title: str,
    issue_body: str,
    repo_name: str,
    working_dir: str,
) -> AgentResult:
    """Spawn the Architect agent to create tasks.json from a GitHub issue.

    The Architect reads the issue, designs the solution, and writes
    tasks.json with dependency-ordered tasks. It does NOT write any code.
    """
    system_prompt = load_prompt("planner")

    prompt = (
        f"{system_prompt}\n\n"
        f"---\n\n"
        f"## Your Assignment\n\n"
        f"You are working on the repo: `{repo_name}`\n\n"
        f"### GitHub Issue\n\n"
        f"**Title**: {issue_title}\n\n"
        f"**Description**:\n{issue_body}\n\n"
        f"---\n\n"
        f"Now break this issue into tasks. Write `tasks.json` in the project root. "
        f"Make sure each task has clear, testable acceptance criteria."
    )

    config = AgentConfig(
        role="Architect",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Glob", "Grep", "Bash"],
        working_dir=working_dir,
    )

    return run_agent(config)
