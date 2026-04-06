"""Documentation Sync skill — update docs after all tasks merge."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from factory.agents.base import AgentConfig
from factory.agents.base import run_agent
from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)


class DocSync(Skill):
    """Update ARCHITECTURE.md, CONTEXT.md, and CHANGELOG.md post-merge.

    Spawns a haiku agent to read the codebase and update documentation
    to reflect the changes made by all tasks in this job.
    """

    name = "doc_sync"
    description = "Update documentation files after all tasks complete"
    phase = SkillPhase.POST_JOB

    async def run(self, ctx: SkillContext) -> SkillResult:
        wd = Path(ctx.working_dir)

        # Get list of changed files for context
        proc = await asyncio.create_subprocess_exec(
            "git",
            "log",
            "--name-only",
            "--pretty=format:",
            "origin/main..HEAD",
            cwd=ctx.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        changed_files = [f for f in stdout.decode().strip().splitlines() if f.strip()]

        if not changed_files:
            return SkillResult(
                success=True,
                message="No changes to document",
            )

        prompt = (
            "You are a documentation writer. Update the project docs to reflect "
            "recent changes.\n\n"
            "## Changed files\n"
            + "\n".join(f"- {f}" for f in changed_files[:50])
            + "\n\n"
            "## Tasks\n"
            "1. **ARCHITECTURE.md** — update if components were added/removed/renamed. "
            "If it doesn't exist, skip.\n"
            "2. **CONTEXT.md** — update in any directory where source files changed. "
            "If it doesn't exist in that directory, create it.\n"
            "3. **CHANGELOG.md** — add an entry under `## [Unreleased]` describing "
            "what changed. Create the file if it doesn't exist.\n\n"
            "Keep docs concise. CONTEXT.md < 50 lines. ARCHITECTURE.md < 150 lines.\n"
            "Do NOT modify any code files. Only documentation."
        )

        config = AgentConfig(
            role="QA Engineer (Contracts)",  # haiku — fast docs
            prompt=prompt,
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
            working_dir=ctx.working_dir,
            model=ctx.model or "haiku",
        )

        await run_agent(config)

        modified: list[str] = []
        if (wd / "ARCHITECTURE.md").exists():
            modified.append("ARCHITECTURE.md")
        if (wd / "CHANGELOG.md").exists():
            modified.append("CHANGELOG.md")
        for ctx_file in wd.rglob("CONTEXT.md"):
            modified.append(str(ctx_file.relative_to(wd)))

        return SkillResult(
            success=True,
            message=f"Documentation updated: {', '.join(modified) or 'no changes'}",
            files_modified=modified,
        )
