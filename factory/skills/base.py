"""Base skill class and types."""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from dataclasses import field

LOG = logging.getLogger(__name__)


class SkillPhase(enum.Enum):
    """When a skill runs in the job lifecycle."""

    PRE_JOB = "pre_job"  # Before any tasks start
    PER_TASK = "per_task"  # During task processing
    POST_JOB = "post_job"  # After all tasks complete
    ON_DEMAND = "on_demand"  # Triggered manually or by conditions


@dataclass
class SkillContext:
    """Runtime context passed to every skill."""

    working_dir: str
    repo_name: str = ""
    issue_number: int = 0
    model: str | None = None
    task_id: str = ""
    task_title: str = ""
    task_type: str = ""
    round_number: int = 0
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Result from running a skill."""

    success: bool
    message: str = ""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    data: dict[str, object] = field(default_factory=dict)


class Skill:
    """Base class for all skills.

    Subclass and implement ``run()`` to create a skill. Register it
    with ``@register_skill`` or call ``register_skill()`` directly.
    """

    name: str = ""
    description: str = ""
    phase: SkillPhase = SkillPhase.ON_DEMAND

    async def should_run(self, ctx: SkillContext) -> bool:
        """Return True if this skill should activate for the given context.

        Override for conditional execution (e.g., only run migration
        chain when task_type == "migration").
        """
        return True

    async def run(self, ctx: SkillContext) -> SkillResult:
        """Execute the skill. Must be overridden by subclasses."""
        raise NotImplementedError
