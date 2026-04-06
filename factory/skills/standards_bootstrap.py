"""Standards Bootstrap skill — ensures project has CONVENTIONS, STYLEGUIDE, CI."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Files every project should have
REQUIRED_FILES = [
    "CONVENTIONS.md",
    "STYLEGUIDE.md",
]


class StandardsBootstrap(Skill):
    """Create CONVENTIONS.md, STYLEGUIDE.md, and CI workflow if missing.

    Detects the project type (fastapi, fullstack, react) from the tech
    stack and copies the right template files.
    """

    name = "standards_bootstrap"
    description = "Ensure project has standards files and CI workflow"
    phase = SkillPhase.PRE_JOB

    async def run(self, ctx: SkillContext) -> SkillResult:
        wd = Path(ctx.working_dir)
        created: list[str] = []

        # Detect project type from existing files
        project_type = _detect_project_type(wd)
        template_dir = TEMPLATES_DIR / project_type

        if not template_dir.exists():
            template_dir = TEMPLATES_DIR / "fastapi"  # fallback

        # Copy missing standards files
        for filename in REQUIRED_FILES:
            target = wd / filename
            if not target.exists():
                source = template_dir / filename
                if not source.exists():
                    # Try root templates
                    source = TEMPLATES_DIR / filename
                if source.exists():
                    shutil.copy2(source, target)
                    created.append(filename)
                    LOG.info("  📋 Created %s from %s template", filename, project_type)

        # Copy CI workflow if missing
        ci_target = wd / ".github" / "workflows" / "ci.yml"
        if not ci_target.exists():
            ci_source = template_dir / ".github" / "workflows" / "ci.yml"
            if ci_source.exists():
                ci_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ci_source, ci_target)
                created.append(".github/workflows/ci.yml")
                LOG.info("  🔧 Created CI workflow from %s template", project_type)

        if not created:
            return SkillResult(
                success=True,
                message="All standards files already exist",
            )

        return SkillResult(
            success=True,
            message=f"Created {len(created)} file(s): {', '.join(created)}",
            files_created=created,
        )


def _detect_project_type(wd: Path) -> str:
    """Detect project type from directory contents."""
    has_python = (wd / "pyproject.toml").exists() or (wd / "setup.py").exists()
    has_node = (wd / "package.json").exists()

    if has_python and has_node:
        return "fullstack"
    if has_node:
        return "react"
    return "fastapi"
