"""Dead Code Sweep skill — find and remove unused code post-merge."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)


class DeadCodeSweep(Skill):
    """Find unused imports, unreachable code, and orphaned test files.

    Uses ruff (Python) and eslint (JS/TS) to detect dead code.
    Reports findings and optionally auto-fixes safe removals.
    """

    name = "dead_code_sweep"
    description = "Find and remove unused code after refactors"
    phase = SkillPhase.POST_JOB

    async def run(self, ctx: SkillContext) -> SkillResult:
        wd = Path(ctx.working_dir)
        findings: list[str] = []
        fixed: list[str] = []

        # Python: ruff check for unused imports and variables
        if any(wd.rglob("*.py")):
            py_findings, py_fixed = await _sweep_python(wd)
            findings.extend(py_findings)
            fixed.extend(py_fixed)

        # JS/TS: eslint for unused vars (if available)
        if any(wd.rglob("*.ts")) or any(wd.rglob("*.tsx")):
            ts_findings = await _sweep_typescript(wd)
            findings.extend(ts_findings)

        # Orphaned test files (test files with no matching source)
        orphans = _find_orphaned_tests(wd)
        findings.extend(orphans)

        if not findings and not fixed:
            return SkillResult(
                success=True,
                message="No dead code found",
            )

        return SkillResult(
            success=True,
            message=(f"Found {len(findings)} issue(s), auto-fixed {len(fixed)}"),
            files_modified=fixed,
            data={
                "findings": findings[:20],  # Cap for context size
                "auto_fixed": len(fixed),
            },
        )


async def _sweep_python(wd: Path) -> tuple[list[str], list[str]]:
    """Run ruff to find and fix unused imports."""
    findings: list[str] = []
    fixed: list[str] = []

    # Check for unused imports (F401) and unused variables (F841)
    proc = await asyncio.create_subprocess_exec(
        "ruff",
        "check",
        "--select",
        "F401,F841",
        "--no-fix",
        str(wd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()

    if proc.returncode != 0:
        for line in stdout.decode().strip().splitlines():
            if line.strip():
                findings.append(f"[Python] {line.strip()}")

    # Auto-fix unused imports (safe removal)
    if findings:
        proc = await asyncio.create_subprocess_exec(
            "ruff",
            "check",
            "--select",
            "F401",
            "--fix",
            str(wd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode()
        if "Fixed" in output:
            # Parse which files were fixed
            for line in output.splitlines():
                if "Fixed" in line:
                    fixed.append(line.strip())

    return findings, fixed


async def _sweep_typescript(wd: Path) -> list[str]:
    """Run eslint to find unused variables in TypeScript."""
    findings: list[str] = []

    # Check if eslint is available
    proc = await asyncio.create_subprocess_exec(
        "npx",
        "eslint",
        "--no-error-on-unmatched-pattern",
        "--rule",
        '{"no-unused-vars": "warn", "@typescript-eslint/no-unused-vars": "warn"}',
        "--format",
        "compact",
        "src/",
        cwd=str(wd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        output = stdout.decode()
        for line in output.strip().splitlines():
            if "no-unused-vars" in line:
                findings.append(f"[TypeScript] {line.strip()}")

    return findings


def _find_orphaned_tests(wd: Path) -> list[str]:
    """Find test files whose source module no longer exists."""
    orphans: list[str] = []
    tests_dir = wd / "tests"

    if not tests_dir.exists():
        return orphans

    for test_file in tests_dir.glob("test_*.py"):
        # test_foo.py → foo.py should exist somewhere in src/
        module_name = test_file.stem.replace("test_", "", 1)
        src_dir = wd / "src"

        if src_dir.exists():
            matches = list(src_dir.rglob(f"{module_name}.py"))
            if not matches:
                # Also check top-level (non-src) Python files
                if not (wd / f"{module_name}.py").exists():
                    orphans.append(
                        f"[Orphan] {test_file.name} — "
                        f"no matching {module_name}.py in src/"
                    )

    return orphans
