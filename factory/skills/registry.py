"""Skill registry — register, discover, and run skills."""

from __future__ import annotations

import logging

from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)

_REGISTRY: dict[str, Skill] = {}


def register_skill(skill: Skill) -> Skill:
    """Register a skill instance in the global registry."""
    if not skill.name:
        raise ValueError(f"Skill {skill.__class__.__name__} has no name")
    _REGISTRY[skill.name] = skill
    LOG.debug("Registered skill: %s (%s)", skill.name, skill.phase.value)
    return skill


def get_skill(name: str) -> Skill | None:
    """Look up a skill by name."""
    return _REGISTRY.get(name)


def list_skills(phase: SkillPhase | None = None) -> list[Skill]:
    """List all registered skills, optionally filtered by phase."""
    skills = list(_REGISTRY.values())
    if phase is not None:
        skills = [s for s in skills if s.phase == phase]
    return sorted(skills, key=lambda s: s.name)


async def run_skill(name: str, ctx: SkillContext) -> SkillResult:
    """Run a skill by name. Returns failure result if not found."""
    skill = _REGISTRY.get(name)
    if not skill:
        return SkillResult(success=False, message=f"Skill '{name}' not found")

    if not await skill.should_run(ctx):
        LOG.info("Skill '%s' skipped (should_run=False)", name)
        return SkillResult(success=True, message=f"Skill '{name}' skipped")

    LOG.info("🔧 Running skill: %s", name)
    try:
        result = await skill.run(ctx)
        LOG.info(
            "  %s skill '%s': %s",
            "✅" if result.success else "❌",
            name,
            result.message[:100],
        )
        return result
    except Exception as exc:
        LOG.error("Skill '%s' crashed: %s", name, exc)
        return SkillResult(success=False, message=f"Skill crashed: {exc}")


async def run_phase(phase: SkillPhase, ctx: SkillContext) -> list[SkillResult]:
    """Run all skills for a given phase. Returns list of results."""
    skills = list_skills(phase)
    results: list[SkillResult] = []
    for skill in skills:
        result = await run_skill(skill.name, ctx)
        results.append(result)
    return results
