"""Cleanup skill — remove orphaned issues, PRs, and state files."""

from __future__ import annotations

import logging

from factory.github_client import GitHubClient
from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult
from factory.state import cleanup_stale_state_files

LOG = logging.getLogger(__name__)


class Cleanup(Skill):
    """Clean up orphaned GitHub issues, stale PRs, and state files.

    Wraps the existing cleanup methods into a single callable skill.
    Can be triggered on-demand or as part of pre-job setup.
    """

    name = "cleanup"
    description = "Clean up orphaned issues, PRs, and state files"
    phase = SkillPhase.ON_DEMAND

    async def run(self, ctx: SkillContext) -> SkillResult:
        github = GitHubClient()
        cleaned: dict[str, int] = {}

        # Orphaned issues
        orphan_count = github.cleanup_orphaned_issues(ctx.repo_name)
        if orphan_count:
            cleaned["orphaned_issues"] = orphan_count

        # Stale PRs
        pr_count = github.cleanup_stale_prs(ctx.repo_name)
        if pr_count:
            cleaned["stale_prs"] = pr_count

        # Stale state files
        state_count = cleanup_stale_state_files(
            ctx.repo_name,
            ctx.issue_number,
        )
        if state_count:
            cleaned["stale_state_files"] = state_count

        if not cleaned:
            return SkillResult(
                success=True,
                message="Nothing to clean up",
            )

        parts = [f"{v} {k.replace('_', ' ')}" for k, v in cleaned.items()]
        return SkillResult(
            success=True,
            message=f"Cleaned: {', '.join(parts)}",
            data={"cleaned": cleaned},
        )
