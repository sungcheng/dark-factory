"""Debug/Bisect skill — systematic debugging when tests fail repeatedly."""

from __future__ import annotations

import logging
from pathlib import Path

from factory.agents.base import AgentConfig
from factory.agents.base import run_agent
from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)


class DebugBisect(Skill):
    """Systematic debugging when the Developer fails 3+ rounds.

    Instead of "try harder", this skill:
    1. Isolates the failing test(s)
    2. Reads the error trace carefully
    3. Identifies the root cause
    4. Writes a targeted fix plan

    Spawns an opus agent for deeper analysis, then feeds the
    diagnosis back to the Developer.
    """

    name = "debug_bisect"
    description = "Systematic debugging when round 3+ fails"
    phase = SkillPhase.PER_TASK

    async def should_run(self, ctx: SkillContext) -> bool:
        """Trigger on round 3+."""
        return ctx.round_number >= 3

    async def run(self, ctx: SkillContext) -> SkillResult:
        wd = Path(ctx.working_dir)

        # Read the current feedback (test output)
        feedback_path = wd / "feedback.md"
        test_output = ""
        if feedback_path.exists():
            test_output = feedback_path.read_text()

        prompt = (
            "You are a **senior debugger**. The Developer has failed to make "
            "tests pass for 3+ rounds. Your job is to diagnose the ROOT CAUSE.\n\n"
            "## Approach\n"
            "1. Read the failing test output below\n"
            "2. Read the test file(s) that are failing\n"
            "3. Read the source code they're testing\n"
            "4. Identify the EXACT mismatch between test expectations "
            "and code behavior\n"
            "5. Check for common issues:\n"
            "   - Import errors (wrong path, missing module)\n"
            "   - Type mismatches (string vs int, None vs empty)\n"
            "   - Missing dependencies (package not installed)\n"
            "   - Environment issues (missing env var, wrong config)\n"
            "   - Logic bugs (off-by-one, wrong operator, missing edge case)\n"
            "   - Async issues (missing await, event loop conflicts)\n\n"
            "## Output\n"
            "Write `debug-diagnosis.md` with:\n"
            "- **Root cause**: one sentence\n"
            "- **Failing test(s)**: file:line for each\n"
            "- **Expected vs actual**: what the test expects vs what the code does\n"
            "- **Fix plan**: specific changes needed (file, line, what to change)\n\n"
            "Do NOT fix the code. Only diagnose.\n\n"
            f"---\n\n"
            f"## Task: {ctx.task_title}\n\n"
            f"## Round: {ctx.round_number}\n\n"
            f"## Test Output\n\n{test_output}\n"
        )

        config = AgentConfig(
            role="QA Engineer (Review)",  # sonnet for good analysis
            prompt=prompt,
            allowed_tools=["Read", "Glob", "Grep", "Bash"],
            working_dir=ctx.working_dir,
            model=ctx.model or "sonnet",
        )

        await run_agent(config)

        diagnosis_path = wd / "debug-diagnosis.md"
        if not diagnosis_path.exists():
            return SkillResult(
                success=False,
                message="Debug agent ran but didn't produce diagnosis",
            )

        diagnosis = diagnosis_path.read_text()

        # Append diagnosis to feedback so Developer gets it
        if feedback_path.exists():
            current = feedback_path.read_text()
            feedback_path.write_text(
                f"{current}\n\n"
                f"---\n\n"
                f"## 🔬 Debug Diagnosis (Round {ctx.round_number})\n\n"
                f"{diagnosis}\n"
            )
        else:
            feedback_path.write_text(
                f"## 🔬 Debug Diagnosis (Round {ctx.round_number})\n\n{diagnosis}\n"
            )

        return SkillResult(
            success=True,
            message="Diagnosis written to feedback.md for Developer",
            files_modified=["feedback.md"],
            files_created=["debug-diagnosis.md"],
            data={"diagnosis_length": len(diagnosis)},
        )
