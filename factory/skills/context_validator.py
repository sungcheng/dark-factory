"""Context Validator skill — verify CONTEXT.md matches actual code."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)


class ContextValidator(Skill):
    """Verify CONTEXT.md files match the actual code they describe.

    Uses ast.parse to extract real function/class names from Python
    source, then checks if CONTEXT.md references match. Flags stale
    docs before agents start working on bad assumptions.
    """

    name = "context_validator"
    description = "Verify CONTEXT.md files match actual code"
    phase = SkillPhase.PRE_JOB

    async def should_run(self, ctx: SkillContext) -> bool:
        """Only run if any CONTEXT.md files exist."""
        return any(Path(ctx.working_dir).rglob("CONTEXT.md"))

    async def run(self, ctx: SkillContext) -> SkillResult:
        wd = Path(ctx.working_dir)
        mismatches: list[str] = []

        for ctx_file in wd.rglob("CONTEXT.md"):
            module_dir = ctx_file.parent
            ctx_text = ctx_file.read_text()
            rel_dir = str(module_dir.relative_to(wd))

            # Extract names claimed in CONTEXT.md
            claimed = _extract_claimed_names(ctx_text)
            if not claimed:
                continue

            # Extract real names from Python source
            real = _extract_real_names(module_dir)
            if not real:
                continue

            # Find mismatches
            missing = claimed - real
            for name in sorted(missing):
                mismatches.append(
                    f"{rel_dir}/CONTEXT.md claims `{name}` "
                    f"but it doesn't exist in source"
                )

        if not mismatches:
            return SkillResult(
                success=True,
                message="All CONTEXT.md files match source code",
            )

        # Write report
        report_path = wd / "context-validation.md"
        report_path.write_text(
            "# Context Validation Report\n\n"
            "Stale references found in CONTEXT.md files:\n\n"
            + "\n".join(f"- {m}" for m in mismatches)
            + "\n\nUpdate these CONTEXT.md files before proceeding.\n"
        )

        LOG.warning(
            "⚠️ %d stale CONTEXT.md reference(s) found",
            len(mismatches),
        )

        return SkillResult(
            success=True,  # Advisory, not blocking
            message=f"{len(mismatches)} stale CONTEXT.md reference(s)",
            files_created=["context-validation.md"],
            data={"mismatches": mismatches},
        )


def _extract_claimed_names(ctx_text: str) -> set[str]:
    """Extract function/class names referenced in CONTEXT.md.

    Looks for backtick-wrapped names like `fetch_weather()`,
    `WeatherService`, `config.py`.
    """
    import re

    names: set[str] = set()
    # Match backtick-wrapped identifiers: `name` or `name()`
    for match in re.finditer(r"`(\w+?)(?:\(\))?`", ctx_text):
        name = match.group(1)
        # Skip common non-code words and filenames
        if (
            name.isupper()  # CONSTANTS, README
            or name.endswith((".py", ".md", ".json", ".yml"))
            or name in _SKIP_WORDS
            or len(name) < 3
        ):
            continue
        names.add(name)
    return names


def _extract_real_names(module_dir: Path) -> set[str]:
    """Extract all function/class/variable names from Python files."""
    names: set[str] = set()

    for py_file in module_dir.glob("*.py"):
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)

    return names


# Common words to skip in CONTEXT.md parsing
_SKIP_WORDS = frozenset(
    {
        "None",
        "True",
        "False",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "Optional",
        "Union",
        "Any",
        "self",
        "cls",
        "async",
        "await",
        "return",
        "import",
        "from",
        "class",
        "def",
        "src",
        "tests",
        "main",
        "app",
        "test",
        "config",
        "utils",
        "models",
        "router",
        "schema",
        "pytest",
        "make",
    }
)
