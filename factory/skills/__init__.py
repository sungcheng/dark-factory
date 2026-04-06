"""Skills — reusable capabilities invoked at specific lifecycle points."""

from __future__ import annotations

from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult
from factory.skills.cleanup import Cleanup

# Auto-register all built-in skills on import
from factory.skills.codebase_profile import CodebaseProfile
from factory.skills.context_validator import ContextValidator
from factory.skills.dead_code_sweep import DeadCodeSweep
from factory.skills.debug_bisect import DebugBisect
from factory.skills.dependency_audit import DependencyAudit
from factory.skills.doc_sync import DocSync
from factory.skills.health_check import HealthCheck
from factory.skills.migration_chain import MigrationChain
from factory.skills.pr_polish import PRPolish
from factory.skills.registry import get_skill
from factory.skills.registry import list_skills
from factory.skills.registry import register_skill
from factory.skills.registry import run_phase
from factory.skills.registry import run_skill
from factory.skills.rollback import Rollback
from factory.skills.scaffold import Scaffold
from factory.skills.standards_bootstrap import StandardsBootstrap
from factory.skills.version_bump import VersionBump

# Register all built-in skills
for _skill_cls in [
    StandardsBootstrap,
    DependencyAudit,
    CodebaseProfile,
    ContextValidator,
    MigrationChain,
    Scaffold,
    DebugBisect,
    DocSync,
    DeadCodeSweep,
    PRPolish,
    HealthCheck,
    Cleanup,
    Rollback,
    VersionBump,
]:
    register_skill(_skill_cls())

__all__ = [
    "Skill",
    "SkillContext",
    "SkillPhase",
    "SkillResult",
    "get_skill",
    "list_skills",
    "register_skill",
    "run_phase",
    "run_skill",
]
