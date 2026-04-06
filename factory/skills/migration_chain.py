"""Migration Chain skill — sequential pipeline for database migrations."""

from __future__ import annotations

import logging
from pathlib import Path

from factory.agents.base import AgentConfig
from factory.agents.base import AgentResult
from factory.agents.base import run_agent
from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)

# Migration pipeline steps — each depends on the previous
MIGRATION_STEPS = [
    {
        "name": "generate_migration",
        "prompt": (
            "You are the Developer. Generate a database migration for the task.\n\n"
            "1. Read the task requirements and existing models\n"
            "2. Create the alembic migration file (or equivalent for the ORM)\n"
            "3. The migration MUST be reversible (include downgrade)\n"
            "4. Do NOT modify any model files yet — only create the migration\n"
            "5. Run `alembic upgrade head` (or equivalent) to verify it applies\n\n"
            "If the project doesn't use alembic, create a SQL migration file in "
            "migrations/ with UP and DOWN sections."
        ),
    },
    {
        "name": "update_models",
        "prompt": (
            "You are the Developer. Update the model/schema files to match "
            "the migration that was just created.\n\n"
            "1. Read the migration file in alembic/versions/ (or migrations/)\n"
            "2. Update the ORM model classes to match the new schema\n"
            "3. Update any Pydantic schemas / API models that reference these fields\n"
            "4. Do NOT create new migrations — they already exist\n"
            "5. Run `make test` to verify models are in sync with migration"
        ),
    },
    {
        "name": "write_backfill",
        "prompt": (
            "You are the Developer. Write a backfill script if the migration "
            "adds columns that need data populated from existing records.\n\n"
            "1. Read the migration and updated models\n"
            "2. If new columns have default values or are nullable, skip backfill\n"
            "3. If data needs to be computed/copied, write a script "
            "in scripts/backfill_*.py\n"
            "4. The script must be idempotent (safe to run multiple times)\n"
            "5. Include a --dry-run flag that shows what would change\n"
            "6. If no backfill needed, write `no-backfill-needed.md` and stop"
        ),
    },
    {
        "name": "verify_migration",
        "prompt": (
            "You are the Developer. Verify the complete migration chain works.\n\n"
            "1. Run the full test suite: `make test`\n"
            "2. Verify migration applies cleanly: `alembic upgrade head`\n"
            "3. Verify migration reverses cleanly: `alembic downgrade -1`\n"
            "4. Verify upgrade again after downgrade\n"
            "5. If any step fails, fix the issue\n"
            "6. Write `migration-verified.md` with the test results"
        ),
    },
]


class MigrationChain(Skill):
    """Run a sequential migration pipeline: generate → models → backfill → verify.

    Each step runs as its own agent spawn. Steps are sequential because
    each depends on the artifacts from the previous step.
    """

    name = "migration_chain"
    description = "Sequential pipeline for database migrations"
    phase = SkillPhase.PER_TASK

    async def should_run(self, ctx: SkillContext) -> bool:
        """Only run for migration-type tasks."""
        return ctx.task_type == "migration"

    async def run(self, ctx: SkillContext) -> SkillResult:
        wd = Path(ctx.working_dir)
        completed_steps: list[str] = []

        for step in MIGRATION_STEPS:
            step_name = step["name"]
            LOG.info("  🔗 Migration step: %s", step_name)

            prompt = (
                f"{step['prompt']}\n\n"
                f"---\n\n"
                f"## Task\n"
                f"**Title**: {ctx.task_title}\n\n"
                f"**Previous steps completed**: "
                f"{', '.join(completed_steps) or 'none'}\n"
            )

            config = AgentConfig(
                role="Developer",
                prompt=prompt,
                allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
                working_dir=ctx.working_dir,
                model=ctx.model or "sonnet",
            )

            result: AgentResult = await run_agent(config)

            # Check for skip signal (no-backfill-needed)
            no_backfill = (wd / "no-backfill-needed.md").exists()
            if no_backfill and step_name == "write_backfill":
                LOG.info("  ⏭️ No backfill needed — skipping")
                completed_steps.append(step_name)
                continue

            if not result.success:
                return SkillResult(
                    success=False,
                    message=f"Migration chain failed at step: {step_name}",
                    data={"failed_step": step_name, "completed": completed_steps},
                )

            completed_steps.append(step_name)

        return SkillResult(
            success=True,
            message=f"Migration chain complete: {' → '.join(completed_steps)}",
            data={"steps": completed_steps},
        )
