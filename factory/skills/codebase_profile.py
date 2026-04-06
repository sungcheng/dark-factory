"""Codebase Profiling skill — generate ARCHITECTURE.md + CONTEXT.md from code."""

from __future__ import annotations

import logging
from pathlib import Path

from factory.agents.base import AgentConfig
from factory.agents.base import run_agent
from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)


class CodebaseProfile(Skill):
    """Generate ARCHITECTURE.md and per-module CONTEXT.md files.

    Cold-start for repos that don't have them yet. Spawns a haiku
    agent to read the code and produce structured documentation.
    """

    name = "codebase_profile"
    description = "Generate ARCHITECTURE.md and CONTEXT.md from codebase"
    phase = SkillPhase.PRE_JOB

    async def should_run(self, ctx: SkillContext) -> bool:
        """Only run if ARCHITECTURE.md is missing."""
        return not (Path(ctx.working_dir) / "ARCHITECTURE.md").exists()

    async def run(self, ctx: SkillContext) -> SkillResult:
        wd = Path(ctx.working_dir)

        prompt = (
            "You are a senior architect. Read the entire codebase and produce:\n\n"
            "1. **ARCHITECTURE.md** in the project root with:\n"
            "   - Project overview (1-2 sentences)\n"
            "   - Directory structure with descriptions\n"
            "   - Key components and their responsibilities\n"
            "   - Data flow (how requests/data move through the system)\n"
            "   - External dependencies and integrations\n"
            "   - Entry points (main, CLI, API routes)\n\n"
            "2. **CONTEXT.md** in each major source directory "
            "(src/, app/, lib/) with:\n"
            "   - Module purpose (1 sentence)\n"
            "   - Key files and what they do\n"
            "   - Internal dependencies (what this module imports from other modules)\n"
            "   - Public interface (exported functions/classes other modules use)\n\n"
            "Be concise. Each CONTEXT.md should be under 50 lines.\n"
            "ARCHITECTURE.md should be under 150 lines.\n"
            "Do NOT modify any code. Only create documentation files."
        )

        config = AgentConfig(
            role="QA Engineer (Contracts)",  # reuse haiku slot
            prompt=prompt,
            allowed_tools=["Read", "Write", "Glob", "Grep"],
            working_dir=ctx.working_dir,
            model=ctx.model or "haiku",
        )

        await run_agent(config)

        created: list[str] = []
        if (wd / "ARCHITECTURE.md").exists():
            created.append("ARCHITECTURE.md")

        # Find created CONTEXT.md files
        for ctx_file in wd.rglob("CONTEXT.md"):
            rel = str(ctx_file.relative_to(wd))
            created.append(rel)

        if not created:
            return SkillResult(
                success=False,
                message="Agent ran but didn't create documentation files",
            )

        return SkillResult(
            success=True,
            message=f"Generated {len(created)} doc(s): {', '.join(created)}",
            files_created=created,
        )
