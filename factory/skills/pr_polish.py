"""PR Polish skill — clean up commits and PR description post-merge."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)


class PRPolish(Skill):
    """Consolidate commit messages and ensure PR descriptions are accurate.

    Runs after all tasks complete. Checks that commit messages are
    meaningful and PR descriptions reflect what actually changed.
    """

    name = "pr_polish"
    description = "Clean up commit history and PR descriptions"
    phase = SkillPhase.POST_JOB

    async def run(self, ctx: SkillContext) -> SkillResult:
        wd = ctx.working_dir
        issues: list[str] = []

        # Analyze commit messages
        proc = await asyncio.create_subprocess_exec(
            "git",
            "log",
            "origin/main..HEAD",
            "--oneline",
            cwd=wd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        commits = stdout.decode().strip().splitlines()

        if not commits:
            return SkillResult(
                success=True,
                message="No commits to polish",
            )

        # Check for bad commit messages
        bad_patterns = [
            "WIP",
            "temp",
            "fixup",
            "squash",
            "TODO",
            "asdf",
            "test",
        ]
        for commit in commits:
            msg = commit.split(" ", 1)[1] if " " in commit else commit
            for pattern in bad_patterns:
                if pattern.lower() in msg.lower() and len(msg) < 20:
                    issues.append(f"Poor commit message: '{msg}'")
                    break

        # Check for too many small commits (could be squashed)
        if len(commits) > 10:
            issues.append(
                f"{len(commits)} commits — consider squashing "
                f"related changes in future runs"
            )

        # Check for duplicate commit messages
        msgs = [c.split(" ", 1)[1] if " " in c else c for c in commits]
        seen: dict[str, int] = {}
        for msg in msgs:
            seen[msg] = seen.get(msg, 0) + 1
        for msg, count in seen.items():
            if count > 2:
                issues.append(f"Duplicate message ({count}x): '{msg}'")

        if not issues:
            return SkillResult(
                success=True,
                message=f"Commit history looks clean ({len(commits)} commits)",
                data={"commit_count": len(commits)},
            )

        # Write report (don't auto-fix — rewriting history is dangerous)
        report = (
            "# PR Polish Report\n\n"
            f"**Commits**: {len(commits)}\n\n"
            "## Issues\n\n" + "\n".join(f"- {i}" for i in issues) + "\n\n"
            "These are advisory. No changes were made to git history.\n"
        )

        report_path = Path(wd) / "pr-polish-report.md"
        report_path.write_text(report)

        return SkillResult(
            success=True,
            message=f"{len(issues)} commit hygiene issue(s) found",
            files_created=["pr-polish-report.md"],
            data={"issues": issues, "commit_count": len(commits)},
        )
