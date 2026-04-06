"""Health Check skill — on-demand health report."""

from __future__ import annotations

import logging

from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult
from factory.state import load_state

LOG = logging.getLogger(__name__)


class HealthCheck(Skill):
    """Run the health report on-demand for any repo/issue.

    Reads saved state and computes the same A-F grade as the
    post-job report, but can be triggered anytime.
    """

    name = "health_check"
    description = "Generate health report for a completed or in-progress job"
    phase = SkillPhase.ON_DEMAND

    async def run(self, ctx: SkillContext) -> SkillResult:
        state = load_state(ctx.repo_name, ctx.issue_number)
        if not state:
            return SkillResult(
                success=False,
                message=f"No state found for {ctx.repo_name}#{ctx.issue_number}",
            )

        tasks = state.tasks
        if not tasks:
            return SkillResult(
                success=False,
                message="No tasks in saved state",
            )

        completed = [t for t in tasks if t.status in ("completed", "success")]
        failed = [t for t in tasks if t.status == "failed"]
        pending = [t for t in tasks if t.status == "pending"]

        rounds = [t.rounds_used for t in completed if t.rounds_used > 0]
        avg_rounds = sum(rounds) / len(rounds) if rounds else 0
        max_round_tasks = sum(1 for r in rounds if r >= 5)
        struggled = sum(1 for r in rounds if r >= 3)

        # Grade
        if max_round_tasks > 0 or len(failed) > 0:
            grade = "C" if max_round_tasks <= 1 else "F"
        elif avg_rounds > 2.5 or struggled > len(completed) * 0.3:
            grade = "C"
        elif avg_rounds > 1.5 or struggled > 0:
            grade = "B"
        else:
            grade = "A"

        report_lines = [
            f"# Health Report: {ctx.repo_name}#{ctx.issue_number}",
            "",
            f"**Grade**: {grade}",
            f"**Tasks**: {len(completed)} completed, {len(failed)} failed, "
            f"{len(pending)} pending",
            f"**Avg rounds/task**: {avg_rounds:.1f}",
            f"**Max-round tasks**: {max_round_tasks}",
            f"**Struggled (3+)**: {struggled}",
            "",
        ]

        for t in tasks:
            status_icon = {"completed": "✅", "failed": "❌", "pending": "⏳"}.get(
                t.status, "❓"
            )
            rounds_info = f" ({t.rounds_used} rounds)" if t.rounds_used else ""
            report_lines.append(f"- {status_icon} {t.title}{rounds_info}")

        if grade in ("C", "F"):
            report_lines.extend(
                [
                    "",
                    "## Recommendations",
                    "- Break large tasks into smaller subtasks",
                    "- Improve CONTEXT.md files for affected modules",
                    "- Consider simplifying codebase structure",
                ]
            )

        report = "\n".join(report_lines)

        return SkillResult(
            success=True,
            message=f"Grade: {grade} — {len(completed)}/{len(tasks)} tasks complete",
            data={
                "grade": grade,
                "avg_rounds": avg_rounds,
                "completed": len(completed),
                "failed": len(failed),
                "pending": len(pending),
                "report": report,
            },
        )
