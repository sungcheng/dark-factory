"""Conflict Resolver agent — post-hoc merges parallel worktree conflicts."""

from __future__ import annotations

import logging

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import load_prompt
from factory.agents.base import run_agent

LOG = logging.getLogger(__name__)


async def run_conflict_resolver(
    task_title: str,
    task_description: str,
    conflicted_files: list[str],
    rebase_stderr: str,
    working_dir: str,
    model: str | None = None,
) -> AgentResult:
    """Spawn the Conflict Resolver on a worktree with an in-progress rebase.

    The caller leaves the rebase in the conflicted state (no `--abort`
    beforehand). The agent reads the conflict markers, merges both
    sides, writes resolved files + `resolution.md`. The caller then
    `git add` the resolved files and `git rebase --continue`.
    """
    system_prompt = load_prompt("conflict_resolver")

    files_list = "\n".join(f"- {f}" for f in conflicted_files) or "(none listed)"
    prompt = (
        f"{system_prompt}\n\n"
        f"---\n\n"
        f"## Task Context\n\n"
        f"**This branch's task:** {task_title}\n\n"
        f"**Description:** {task_description}\n\n"
        f"## Conflict Context\n\n"
        f"Files with unresolved conflicts:\n{files_list}\n\n"
        f"Rebase stderr:\n```\n{rebase_stderr}\n```\n\n"
        f"Resolve every conflicted file and write `resolution.md`. "
        f"Do not run `git rebase --continue` — the caller will do that "
        f"after verifying your resolution.\n"
    )

    config = AgentConfig(
        role="Conflict Resolver",
        prompt=prompt,
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        working_dir=working_dir,
        max_turns=30,
        model=model or "sonnet",
    )

    return await run_agent(config)
