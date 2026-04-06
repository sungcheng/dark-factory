"""Scaffold skill — generate boilerplate for common patterns."""

from __future__ import annotations

import asyncio
import logging

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import run_agent
from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)


# Scaffold templates per task type
SCAFFOLD_PROMPTS: dict[str, str] = {
    "api_route": (
        "Scaffold a new API route:\n"
        "1. Create the route file in the appropriate router directory\n"
        "2. Add Pydantic request/response models\n"
        "3. Wire the route into the main app router\n"
        "4. Create a test file with basic happy-path test stubs\n"
        "5. Follow existing patterns in the codebase"
    ),
    "model": (
        "Scaffold a new data model:\n"
        "1. Create the ORM model class in the models directory\n"
        "2. Create corresponding Pydantic schemas\n"
        "3. Add migration file (alembic or SQL)\n"
        "4. Create test file with basic CRUD test stubs\n"
        "5. Follow existing model patterns"
    ),
    "component": (
        "Scaffold a new frontend component:\n"
        "1. Create component file with TypeScript types\n"
        "2. Create associated test file\n"
        "3. Export from the nearest index file\n"
        "4. Add basic props interface\n"
        "5. Follow existing component patterns"
    ),
    "service": (
        "Scaffold a new service/module:\n"
        "1. Create the service class/module in src/\n"
        "2. Define the public interface (functions/classes)\n"
        "3. Add __init__.py exports if Python\n"
        "4. Create test file with interface test stubs\n"
        "5. Follow existing service patterns"
    ),
}


class Scaffold(Skill):
    """Generate boilerplate for common patterns (routes, models, components).

    The Architect can reference this skill to reduce prompt complexity.
    Spawns a haiku agent to create the scaffolding quickly.
    """

    name = "scaffold"
    description = "Generate boilerplate for new routes, models, components"
    phase = SkillPhase.PER_TASK

    async def should_run(self, ctx: SkillContext) -> bool:
        """Run for scaffold-type tasks."""
        return ctx.task_type in SCAFFOLD_PROMPTS

    async def run(self, ctx: SkillContext) -> SkillResult:
        scaffold_type = ctx.task_type
        base_prompt = SCAFFOLD_PROMPTS.get(scaffold_type, SCAFFOLD_PROMPTS["service"])

        prompt = (
            f"You are the Developer. {base_prompt}\n\n"
            f"---\n\n"
            f"## Task\n"
            f"**Title**: {ctx.task_title}\n\n"
            f"Read the existing codebase patterns first, then scaffold.\n"
            f"Only create stubs — do NOT implement business logic.\n"
            f"Write TODO comments where implementation goes."
        )

        config = AgentConfig(
            role="QA Engineer (Contracts)",  # haiku — fast scaffolding
            prompt=prompt,
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
            working_dir=ctx.working_dir,
            model=ctx.model or "haiku",
        )

        result: AgentResult = await run_agent(config)

        if not result.success:
            return SkillResult(
                success=False,
                message=f"Scaffold failed for type: {scaffold_type}",
            )

        # Count created files
        created = _find_new_files(ctx.working_dir)

        return SkillResult(
            success=True,
            message=f"Scaffolded {scaffold_type}: {len(created)} file(s) created",
            files_created=created,
            data={"scaffold_type": scaffold_type},
        )


def _find_new_files(working_dir: str) -> list[str]:
    """Find files created by the scaffold agent (untracked by git)."""

    async def _get_untracked() -> list[str]:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "diff",
            "--name-only",
            "--diff-filter=A",
            "HEAD",
            cwd=working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip().splitlines()

    try:
        asyncio.get_running_loop()
        # Already in an async context — return empty
        return []
    except RuntimeError:
        return asyncio.run(_get_untracked())
