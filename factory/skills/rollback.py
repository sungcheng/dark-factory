"""Rollback skill — revert a task's changes and reset state."""

from __future__ import annotations

import asyncio
import logging

from factory.github_client import GitHubClient
from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult
from factory.state import load_state
from factory.state import save_state

LOG = logging.getLogger(__name__)


class Rollback(Skill):
    """Revert a task's changes: close PR, reset branch, re-open task.

    Used when post-merge issues are found and a task needs to be
    rolled back to a clean state for retry.
    """

    name = "rollback"
    description = "Revert a task's changes, close PR, reset state"
    phase = SkillPhase.ON_DEMAND

    async def run(self, ctx: SkillContext) -> SkillResult:
        if not ctx.task_id:
            return SkillResult(
                success=False,
                message="No task_id specified for rollback",
            )

        github = GitHubClient()
        state = load_state(ctx.repo_name, ctx.issue_number)
        if not state:
            return SkillResult(
                success=False,
                message=f"No state for {ctx.repo_name}#{ctx.issue_number}",
            )

        # Find the task
        task = None
        for t in state.tasks:
            if t.id == ctx.task_id:
                task = t
                break

        if not task:
            return SkillResult(
                success=False,
                message=f"Task '{ctx.task_id}' not found in state",
            )

        actions: list[str] = []

        # Close any open PRs for this task's branch
        task_branch = f"factory/issue-{ctx.issue_number}/{ctx.task_id}"
        try:
            repo = github.get_repo(ctx.repo_name)
            head_ref = f"{github.owner}:{task_branch}"
            for pr in repo.get_pulls(state="open", head=head_ref):
                pr.edit(state="closed")
                actions.append(f"Closed PR #{pr.number}")
        except Exception as exc:
            LOG.warning("Could not close PRs for %s: %s", task_branch, exc)

        # Delete the remote branch
        try:
            repo = github.get_repo(ctx.repo_name)
            ref = repo.get_git_ref(f"heads/{task_branch}")
            ref.delete()
            actions.append(f"Deleted branch {task_branch}")
        except Exception:
            LOG.debug("Branch %s may not exist remotely", task_branch)

        # Revert the merge commit on main if it was merged
        if task.status == "completed" and ctx.working_dir:
            revert_result = await _revert_task_on_main(
                ctx.working_dir,
                task.title,
            )
            if revert_result:
                actions.append(revert_result)

        # Reset task state
        task.status = "pending"
        task.rounds_used = 0
        task.failure_issue = None
        save_state(state)
        actions.append(f"Reset task '{ctx.task_id}' to pending")

        # Re-open the sub-issue if it was closed
        if task.issue_number:
            try:
                issue = repo.get_issue(task.issue_number)
                if issue.state == "closed":
                    issue.edit(state="open")
                    actions.append(f"Re-opened issue #{task.issue_number}")
            except Exception as exc:
                LOG.warning("Could not re-open issue: %s", exc)

        return SkillResult(
            success=True,
            message=f"Rolled back task '{ctx.task_id}': {'; '.join(actions)}",
            data={"actions": actions},
        )


async def _revert_task_on_main(working_dir: str, task_title: str) -> str | None:
    """Try to revert the merge commit for a task on main."""
    # Find the merge commit by message
    proc = await asyncio.create_subprocess_exec(
        "git",
        "log",
        "--oneline",
        "--grep",
        task_title,
        "-1",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode().strip()

    if not output:
        return None

    commit_hash = output.split(" ", 1)[0]

    # Revert it
    proc = await asyncio.create_subprocess_exec(
        "git",
        "revert",
        commit_hash,
        "--no-edit",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    if proc.returncode == 0:
        return f"Reverted commit {commit_hash} on main"

    # Revert failed (conflicts) — abort
    await asyncio.create_subprocess_exec(
        "git",
        "revert",
        "--abort",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return None
