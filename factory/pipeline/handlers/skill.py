"""Skill handler — runs a registered Dark Factory skill."""

from __future__ import annotations

from typing import TYPE_CHECKING

from factory.pipeline.schema import NodeResult
from factory.skills.base import SkillContext
from factory.skills.registry import get_skill

if TYPE_CHECKING:
    from factory.pipeline.engine import PipelineContext
    from factory.pipeline.schema import Node


async def skill_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Invoke a factory skill by name.

    Expected params:
        name: str — skill name as registered in factory.skills.registry
    """
    name = node.params["name"]
    skill = get_skill(name)
    if skill is None:
        return NodeResult(
            status="failed",
            message=f"Unknown skill: {name!r}",
        )

    skill_ctx = SkillContext(
        working_dir=ctx.working_dir,
        repo_name=ctx.repo_name,
        issue_number=ctx.issue_number,
    )
    result = await skill.run(skill_ctx)
    return NodeResult(
        status="success" if result.success else "failed",
        message=result.message,
        data={"files_modified": list(result.files_modified or [])},
    )
