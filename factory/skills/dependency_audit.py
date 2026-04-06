"""Dependency Audit skill — check for outdated/vulnerable deps before work."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)


class DependencyAudit(Skill):
    """Audit project dependencies for known vulnerabilities and outdated versions.

    Runs pip-audit (Python) and npm audit (Node) if applicable.
    Reports findings but does NOT auto-fix (that's the Developer's job).
    """

    name = "dependency_audit"
    description = "Check for vulnerable or outdated dependencies"
    phase = SkillPhase.PRE_JOB

    async def run(self, ctx: SkillContext) -> SkillResult:
        wd = Path(ctx.working_dir)
        findings: list[str] = []
        data: dict[str, object] = {}

        # Python audit
        if (wd / "pyproject.toml").exists() or (wd / "requirements.txt").exists():
            py_result = await _audit_python(wd)
            if py_result:
                findings.extend(py_result)
                data["python_issues"] = len(py_result)

        # Node audit
        if (wd / "package.json").exists():
            node_result = await _audit_node(wd)
            if node_result:
                findings.extend(node_result)
                data["node_issues"] = len(node_result)

        if not findings:
            return SkillResult(
                success=True,
                message="No dependency issues found",
                data=data,
            )

        # Write report
        report_path = wd / "dependency-audit.md"
        report_path.write_text(
            "# Dependency Audit Report\n\n"
            + "\n".join(f"- {f}" for f in findings)
            + "\n"
        )

        return SkillResult(
            success=True,  # Findings are advisory, not blocking
            message=f"Found {len(findings)} dependency issue(s)",
            files_created=["dependency-audit.md"],
            data=data,
        )


async def _audit_python(wd: Path) -> list[str]:
    """Run pip-audit or safety check on Python deps."""
    findings: list[str] = []

    # Try pip-audit first
    proc = await asyncio.create_subprocess_exec(
        "python",
        "-m",
        "pip_audit",
        "--strict",
        "--desc",
        cwd=str(wd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        output = stdout.decode() + stderr.decode()
        # pip-audit not installed is not a finding
        if "No module named" in output:
            LOG.debug("pip-audit not available, skipping Python audit")
            return []
        # Parse actual findings
        for line in output.splitlines():
            line = line.strip()
            if line and not line.startswith(("Name", "---", "Found")):
                findings.append(f"[Python] {line}")

    return findings


async def _audit_node(wd: Path) -> list[str]:
    """Run npm audit on Node deps."""
    findings: list[str] = []

    # Check if node_modules exists (npm audit needs it)
    if not (wd / "node_modules").exists():
        return []

    proc = await asyncio.create_subprocess_exec(
        "npm",
        "audit",
        "--json",
        cwd=str(wd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()

    if proc.returncode != 0:
        try:
            data = json.loads(stdout.decode())
            vulns = data.get("vulnerabilities", {})
            for name, info in vulns.items():
                severity = info.get("severity", "unknown")
                findings.append(f"[Node] {name}: {severity} vulnerability")
        except (json.JSONDecodeError, TypeError):
            findings.append("[Node] npm audit reported issues (unparseable)")

    return findings
