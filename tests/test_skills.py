"""Tests for the skills framework and individual skills."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult
from factory.skills.codebase_profile import CodebaseProfile
from factory.skills.dead_code_sweep import _find_orphaned_tests
from factory.skills.debug_bisect import DebugBisect
from factory.skills.migration_chain import MigrationChain
from factory.skills.registry import _REGISTRY
from factory.skills.registry import get_skill
from factory.skills.registry import list_skills
from factory.skills.registry import register_skill
from factory.skills.registry import run_skill
from factory.skills.scaffold import Scaffold
from factory.skills.standards_bootstrap import StandardsBootstrap
from factory.skills.standards_bootstrap import _detect_project_type


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


class TestSkillBase:
    """Tests for Skill base class."""

    def test_skill_defaults(self) -> None:
        skill = Skill()
        assert skill.name == ""
        assert skill.phase == SkillPhase.ON_DEMAND

    def test_skill_result_defaults(self) -> None:
        result = SkillResult(success=True)
        assert result.message == ""
        assert result.files_created == []
        assert result.files_modified == []
        assert result.data == {}

    def test_skill_context_defaults(self) -> None:
        ctx = SkillContext(working_dir="/tmp")
        assert ctx.repo_name == ""
        assert ctx.issue_number == 0
        assert ctx.model is None
        assert ctx.task_type == ""
        assert ctx.round_number == 0


class TestSkillRegistry:
    """Tests for skill registration and lookup."""

    def test_all_skills_registered(self) -> None:
        expected = {
            "standards_bootstrap",
            "dependency_audit",
            "codebase_profile",
            "migration_chain",
            "scaffold",
            "debug_bisect",
            "doc_sync",
            "dead_code_sweep",
            "pr_polish",
            "health_check",
            "cleanup",
            "rollback",
        }
        actual = set(_REGISTRY.keys())
        assert expected.issubset(actual), f"Missing: {expected - actual}"

    def test_get_skill(self) -> None:
        skill = get_skill("debug_bisect")
        assert skill is not None
        assert skill.name == "debug_bisect"
        assert skill.phase == SkillPhase.PER_TASK

    def test_get_nonexistent_skill(self) -> None:
        assert get_skill("nonexistent_skill_xyz") is None

    def test_list_skills_all(self) -> None:
        skills = list_skills()
        assert len(skills) >= 12
        names = [s.name for s in skills]
        assert names == sorted(names)

    def test_list_skills_by_phase(self) -> None:
        pre_job = list_skills(SkillPhase.PRE_JOB)
        assert len(pre_job) == 3
        assert {s.name for s in pre_job} == {
            "standards_bootstrap",
            "dependency_audit",
            "codebase_profile",
        }

        per_task = list_skills(SkillPhase.PER_TASK)
        assert len(per_task) == 3
        assert {s.name for s in per_task} == {
            "migration_chain",
            "scaffold",
            "debug_bisect",
        }

        post_job = list_skills(SkillPhase.POST_JOB)
        assert len(post_job) == 3
        assert {s.name for s in post_job} == {
            "doc_sync",
            "dead_code_sweep",
            "pr_polish",
        }

        on_demand = list_skills(SkillPhase.ON_DEMAND)
        assert len(on_demand) == 3
        assert {s.name for s in on_demand} == {
            "health_check",
            "cleanup",
            "rollback",
        }

    def test_register_skill_no_name_raises(self) -> None:
        with pytest.raises(ValueError, match="has no name"):
            register_skill(Skill())

    def test_run_nonexistent_skill(self) -> None:
        ctx = SkillContext(working_dir="/tmp")
        result = _run(run_skill("nonexistent_xyz", ctx))
        assert result.success is False
        assert "not found" in result.message


class TestSkillPhases:
    """Tests for SkillPhase enum."""

    def test_phase_values(self) -> None:
        assert SkillPhase.PRE_JOB.value == "pre_job"
        assert SkillPhase.PER_TASK.value == "per_task"
        assert SkillPhase.POST_JOB.value == "post_job"
        assert SkillPhase.ON_DEMAND.value == "on_demand"


class TestStandardsBootstrap:
    """Tests for standards bootstrap skill."""

    def test_creates_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\nname='test'\n")
            skill = StandardsBootstrap()
            ctx = SkillContext(working_dir=tmpdir)
            result = _run(skill.run(ctx))
            assert result.success
            assert len(result.files_created) > 0

    def test_skips_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "CONVENTIONS.md").write_text("existing")
            (Path(tmpdir) / "STYLEGUIDE.md").write_text("existing")
            ci_dir = Path(tmpdir) / ".github" / "workflows"
            ci_dir.mkdir(parents=True)
            (ci_dir / "ci.yml").write_text("name: CI")

            skill = StandardsBootstrap()
            ctx = SkillContext(working_dir=tmpdir)
            result = _run(skill.run(ctx))
            assert result.success
            assert "already exist" in result.message


class TestProjectTypeDetection:
    """Tests for project type detection."""

    def test_detect_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pyproject.toml").write_text("[project]")
            assert _detect_project_type(Path(tmpdir)) == "fastapi"

    def test_detect_react(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "package.json").write_text("{}")
            assert _detect_project_type(Path(tmpdir)) == "react"

    def test_detect_fullstack(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pyproject.toml").write_text("[project]")
            (Path(tmpdir) / "package.json").write_text("{}")
            assert _detect_project_type(Path(tmpdir)) == "fullstack"


class TestDeadCodeSweep:
    """Tests for dead code sweep skill."""

    def test_find_orphaned_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            wd = Path(tmpdir)
            (wd / "tests").mkdir()
            (wd / "src").mkdir()
            (wd / "tests" / "test_orphan.py").write_text("def test_it(): pass")
            (wd / "tests" / "test_real.py").write_text("def test_it(): pass")
            (wd / "src" / "real.py").write_text("def real(): pass")

            orphans = _find_orphaned_tests(wd)
            assert len(orphans) == 1
            assert "test_orphan.py" in orphans[0]


class TestDebugBisect:
    """Tests for debug bisect skill."""

    def test_should_run_threshold(self) -> None:
        skill = DebugBisect()
        assert (
            _run(skill.should_run(SkillContext(working_dir="/tmp", round_number=1)))
            is False
        )
        assert (
            _run(skill.should_run(SkillContext(working_dir="/tmp", round_number=2)))
            is False
        )
        assert (
            _run(skill.should_run(SkillContext(working_dir="/tmp", round_number=3)))
            is True
        )
        assert (
            _run(skill.should_run(SkillContext(working_dir="/tmp", round_number=5)))
            is True
        )


class TestMigrationChain:
    """Tests for migration chain skill."""

    def test_should_run_migration_only(self) -> None:
        skill = MigrationChain()
        assert (
            _run(
                skill.should_run(SkillContext(working_dir="/tmp", task_type="feature"))
            )
            is False
        )
        assert (
            _run(
                skill.should_run(
                    SkillContext(working_dir="/tmp", task_type="migration")
                )
            )
            is True
        )


class TestScaffold:
    """Tests for scaffold skill."""

    def test_should_run_scaffold_types(self) -> None:
        skill = Scaffold()
        for task_type in ("api_route", "model", "component", "service"):
            ctx = SkillContext(working_dir="/tmp", task_type=task_type)
            assert _run(skill.should_run(ctx)) is True
        assert (
            _run(
                skill.should_run(SkillContext(working_dir="/tmp", task_type="feature"))
            )
            is False
        )


class TestCodebaseProfile:
    """Tests for codebase profile skill."""

    def test_should_run_when_no_arch(self) -> None:
        skill = CodebaseProfile()
        with tempfile.TemporaryDirectory() as tmpdir:
            assert _run(skill.should_run(SkillContext(working_dir=tmpdir))) is True

    def test_should_not_run_when_arch_exists(self) -> None:
        skill = CodebaseProfile()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "ARCHITECTURE.md").write_text("# Arch")
            assert _run(skill.should_run(SkillContext(working_dir=tmpdir))) is False
