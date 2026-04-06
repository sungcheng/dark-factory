"""Guardrails — pre-flight checks that protect production repos.

Detects existing tech stack, scans for secrets, enforces file
boundaries, validates dependencies, and guards regression scope.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tech Stack Detection
# ---------------------------------------------------------------------------

# File markers → (category, technology)
_TECH_MARKERS: list[tuple[str, str, str]] = [
    # Python
    ("pyproject.toml", "language", "python"),
    ("setup.py", "language", "python"),
    ("requirements.txt", "language", "python"),
    # Go
    ("go.mod", "language", "go"),
    # Rust
    ("Cargo.toml", "language", "rust"),
    # Node / JS / TS
    ("package.json", "language", "node"),
    # Terraform
    ("main.tf", "language", "terraform"),
    # Docker
    ("Dockerfile", "container", "docker"),
    ("docker-compose.yml", "container", "docker-compose"),
    ("docker-compose.yaml", "container", "docker-compose"),
    ("compose.yml", "container", "docker-compose"),
    ("compose.yaml", "container", "docker-compose"),
]

# Content patterns inside key files → (file, pattern, category, technology)
_CONTENT_MARKERS: list[tuple[str, str, str, str]] = [
    ("pyproject.toml", r"fastapi", "python_framework", "fastapi"),
    ("pyproject.toml", r"django", "python_framework", "django"),
    ("pyproject.toml", r"flask", "python_framework", "flask"),
    ("pyproject.toml", r"sqlalchemy", "database_orm", "sqlalchemy"),
    ("pyproject.toml", r"aiosqlite", "database", "sqlite"),
    ("pyproject.toml", r"psycopg|asyncpg", "database", "postgresql"),
    ("pyproject.toml", r"pymongo|motor", "database", "mongodb"),
    ("setup.py", r"fastapi", "python_framework", "fastapi"),
    ("setup.py", r"django", "python_framework", "django"),
    ("setup.py", r"flask", "python_framework", "flask"),
    ("package.json", r'"react"', "frontend_framework", "react"),
    ("package.json", r'"vue"', "frontend_framework", "vue"),
    ("package.json", r'"angular"', "frontend_framework", "angular"),
    ("package.json", r'"svelte"', "frontend_framework", "svelte"),
    ("package.json", r'"vite"', "bundler", "vite"),
    ("package.json", r'"webpack"', "bundler", "webpack"),
    ("package.json", r'"next"', "frontend_framework", "nextjs"),
    ("package.json", r"tailwindcss", "css_framework", "tailwind"),
]


@dataclass
class TechStack:
    """Detected technology stack for a repository."""

    detected: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        """Human-readable summary for agent prompts."""
        if not self.detected:
            return "No existing tech stack detected (new project)."
        lines = [f"- **{cat}**: {tech}" for cat, tech in sorted(self.detected.items())]
        return "\n".join(lines)

    def as_guardrail_prompt(self) -> str:
        """Markdown block to inject into agent prompts."""
        if not self.detected:
            return ""
        return (
            "## Tech Stack Guardrails\n\n"
            "This repo has an established tech stack. "
            "**NEVER migrate, replace, or rewrite** existing "
            "frameworks or languages. Extend what exists.\n\n"
            "### Detected Stack\n"
            f"{self.summary()}\n\n"
            "### Rules\n"
            "- Use the existing framework — do not introduce a competing one "
            "(e.g., do not add Flask to a FastAPI project)\n"
            "- Use the existing ORM / database driver — do not switch\n"
            "- Use the existing bundler and frontend framework — do not switch\n"
            "- Match existing patterns: import style, project layout, naming\n"
            "- If you need a new dependency, check if the existing stack "
            "already provides it\n"
        )

    def as_claude_md_section(self) -> str:
        """Section to append to a project's CLAUDE.md."""
        if not self.detected:
            return ""
        return (
            "\n## Tech Stack (auto-detected by Dark Factory)\n\n"
            f"{self.summary()}\n\n"
            "Do NOT migrate away from the above technologies. "
            "Extend the existing stack.\n"
        )


def detect_tech_stack(working_dir: str) -> TechStack:
    """Scan a repository for technology markers.

    Checks for known config files and parses their contents
    to determine frameworks, languages, and tools in use.
    """
    root = Path(working_dir)
    stack = TechStack()

    # Phase 1: file-existence markers
    for filename, category, technology in _TECH_MARKERS:
        # Check root and common subdirs (backend/, frontend/)
        for search_dir in [root, root / "backend", root / "frontend"]:
            if (search_dir / filename).is_file():
                stack.detected[category] = technology

    # Phase 2: content-based markers
    for filename, pattern, category, technology in _CONTENT_MARKERS:
        for search_dir in [root, root / "backend", root / "frontend"]:
            filepath = search_dir / filename
            if filepath.is_file():
                try:
                    content = filepath.read_text()
                    if re.search(pattern, content, re.IGNORECASE):
                        stack.detected[category] = technology
                except OSError:
                    pass

    if stack.detected:
        LOG.info(
            "Detected tech stack: %s",
            ", ".join(f"{k}={v}" for k, v in sorted(stack.detected.items())),
        )
    else:
        LOG.info("No existing tech stack detected — new project")

    return stack


# ---------------------------------------------------------------------------
# Secret / Credential Scanning
# ---------------------------------------------------------------------------

# Patterns that look like hardcoded secrets
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "AWS Secret Key",
        re.compile(r"""(?:"|')(?:[A-Za-z0-9/+=]{40})(?:"|')"""),
    ),
    (
        "Generic API Key",
        re.compile(
            r"""(?:api[_-]?key|apikey)\s*[:=]\s*"""
            r"""(?:"|')[A-Za-z0-9_\-]{20,}(?:"|')""",
            re.IGNORECASE,
        ),
    ),
    (
        "Generic Secret",
        re.compile(
            r"""(?:secret|password|passwd|token)\s*[:=]\s*"""
            r"""(?:"|')[^\s"']{8,}(?:"|')""",
            re.IGNORECASE,
        ),
    ),
    (
        "Private Key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    ),
    ("GitHub Token", re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}")),
    ("Slack Token", re.compile(r"xox[bpors]-[A-Za-z0-9\-]+")),
    (
        "JWT",
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}"),
    ),
]

# Files to skip when scanning
_SECRET_SKIP_PATTERNS: set[str] = {
    ".env.example",
    "*.md",
    "*.lock",
    "*.svg",
    "*.png",
    "*.jpg",
    "*.gif",
    "*.ico",
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
}


@dataclass
class SecretFinding:
    """A potential hardcoded secret found in a file."""

    file_path: str
    line_number: int
    pattern_name: str
    line_preview: str


def scan_for_secrets(working_dir: str) -> list[SecretFinding]:
    """Scan source files for hardcoded secrets.

    Returns a list of findings. An empty list means clean.
    """
    root = Path(working_dir)
    findings: list[SecretFinding] = []

    for filepath in root.rglob("*"):
        if not filepath.is_file():
            continue
        skip_suffixes = {
            ".png",
            ".jpg",
            ".gif",
            ".ico",
            ".svg",
            ".lock",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
        }
        if filepath.suffix in skip_suffixes:
            continue
        rel = str(filepath.relative_to(root))
        skip_dirs = {
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "venv",
        }
        if any(skip in rel for skip in skip_dirs):
            continue
        if filepath.name == ".env.example":
            continue
        # Only scan .env if it exists (it shouldn't be committed)
        if filepath.name == ".env":
            findings.append(
                SecretFinding(
                    file_path=rel,
                    line_number=0,
                    pattern_name=".env file",
                    line_preview=".env file should not be committed",
                )
            )
            continue

        try:
            content = filepath.read_text(errors="ignore")
        except OSError:
            continue

        for line_num, line in enumerate(content.splitlines(), 1):
            for pattern_name, pattern in _SECRET_PATTERNS:
                if pattern.search(line):
                    # Skip test files and example configs
                    low = rel.lower()
                    if any(
                        s in low
                        for s in (
                            "test",
                            "mock",
                            "fixture",
                        )
                    ):
                        continue
                    preview = line.strip()[:80]
                    findings.append(
                        SecretFinding(
                            file_path=rel,
                            line_number=line_num,
                            pattern_name=pattern_name,
                            line_preview=preview,
                        )
                    )

    if findings:
        LOG.warning(
            "Found %d potential secret(s) in repo",
            len(findings),
        )
    return findings


def format_secret_findings(findings: list[SecretFinding]) -> str:
    """Format findings as a markdown report for agents or humans."""
    if not findings:
        return ""
    lines = ["## Secret Scan Findings\n"]
    for f in findings:
        lines.append(
            f"- **{f.pattern_name}** in "
            f"`{f.file_path}:{f.line_number}` "
            f"— `{f.line_preview}`"
        )
    lines.append(
        "\n**Action required**: Remove hardcoded secrets. "
        "Use environment variables (via `.env` + `python-dotenv` or similar)."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File Boundary Enforcement
# ---------------------------------------------------------------------------

# Protected files that agents should not modify unless the task is infra
PROTECTED_FILES: set[str] = {
    "CLAUDE.md",
    "Makefile",
    ".github/workflows/ci.yml",
    ".gitignore",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "Dockerfile",
    ".env",
    ".env.example",
}

# Protected config files by extension
PROTECTED_EXTENSIONS: set[str] = {
    ".toml",  # pyproject.toml, etc.
    ".cfg",  # setup.cfg
    ".ini",  # tox.ini, etc.
}


def generate_file_boundary_prompt(task_title: str) -> str:
    """Generate file boundary rules for agent prompts.

    Infrastructure tasks (scaffolding, CI, Docker) get relaxed
    boundaries. Feature tasks get strict boundaries.
    """
    infra_keywords = [
        "scaffold",
        "setup",
        "ci/cd",
        "docker",
        "infrastructure",
        "makefile",
        "config",
        "deploy",
        "initialize",
    ]
    is_infra = any(kw in task_title.lower() for kw in infra_keywords)

    if is_infra:
        return (
            "## File Boundaries\n\n"
            "This is an infrastructure task. You may modify config files, "
            "Makefile, Dockerfile, CI workflows, and pyproject.toml as needed.\n"
        )

    protected = ", ".join(f"`{f}`" for f in sorted(PROTECTED_FILES))
    return (
        "## File Boundaries\n\n"
        "This is a feature task. Do NOT modify these files unless "
        "the task explicitly requires it:\n"
        f"{protected}\n\n"
        "Do NOT modify `pyproject.toml`, `setup.cfg`, or other project "
        "config files. If you need a new dependency, add it to "
        "the appropriate requirements file and note it in your output.\n"
    )


# ---------------------------------------------------------------------------
# Dependency Guardrails
# ---------------------------------------------------------------------------

# Known duplicate / competing packages
_COMPETING_PACKAGES: dict[str, list[str]] = {
    "http_client": ["requests", "httpx", "aiohttp", "urllib3"],
    "web_framework": ["fastapi", "flask", "django", "starlette", "tornado"],
    "orm": ["sqlalchemy", "tortoise-orm", "peewee", "django"],
    "test_framework": ["pytest", "unittest", "nose"],
    "linter": ["ruff", "flake8", "pylint", "pyflakes"],
    "formatter": ["ruff", "black", "autopep8", "yapf"],
}


@dataclass
class DependencyIssue:
    """A dependency guardrail violation."""

    severity: str  # "error" or "warning"
    message: str


def check_dependencies(working_dir: str) -> list[DependencyIssue]:
    """Check for dependency guardrail violations.

    Looks for competing packages, unpinned versions,
    and duplicate functionality.
    """
    root = Path(working_dir)
    issues: list[DependencyIssue] = []

    # Collect all declared dependencies
    declared_deps: set[str] = set()

    # Check pyproject.toml
    dep_pattern = r'"([a-zA-Z0-9_-]+)(?:\[.*?\])?(?:[><=!~].*?)?"'
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        content = pyproject.read_text()
        for match in re.finditer(dep_pattern, content):
            dep = match.group(1).lower().replace("-", "_")
            declared_deps.add(dep)

    # Check package.json
    for search_dir in [root, root / "frontend"]:
        pkg = search_dir / "package.json"
        if pkg.is_file():
            try:
                import json

                data = json.loads(pkg.read_text())
                for section in ("dependencies", "devDependencies"):
                    for dep_name in data.get(section, {}):
                        declared_deps.add(dep_name.lower())
            except (json.JSONDecodeError, OSError):
                pass

    # Check for competing packages
    for category, competitors in _COMPETING_PACKAGES.items():
        found = [c for c in competitors if c.replace("-", "_") in declared_deps]
        if len(found) > 1:
            issues.append(
                DependencyIssue(
                    severity="warning",
                    message=(
                        f"Competing {category} packages detected: "
                        f"{', '.join(found)}. Pick one and remove the others."
                    ),
                )
            )

    return issues


def generate_dependency_prompt(working_dir: str) -> str:
    """Generate dependency guardrail rules for agent prompts."""
    issues = check_dependencies(working_dir)
    root = Path(working_dir)

    # Detect existing deps to tell agents what's available
    existing_deps: list[str] = []
    pyproject = root / "pyproject.toml"
    dep_pat = r'"([a-zA-Z0-9_-]+)(?:\[.*?\])?(?:[><=!~].*?)?"'
    if pyproject.is_file():
        content = pyproject.read_text()
        for match in re.finditer(dep_pat, content):
            existing_deps.append(match.group(1))

    lines = [
        "## Dependency Guardrails\n",
        "- **NEVER** add a package that duplicates functionality already "
        "provided by an existing dependency",
        "- **ALWAYS** pin dependency versions (e.g., `>=1.0,<2.0` not just `*`)",
        "- **PREFER** the existing HTTP client, ORM, and test framework",
    ]

    if existing_deps:
        deps_str = ", ".join(sorted(set(existing_deps[:15])))
        lines.append(f"\n**Existing dependencies**: {deps_str}")

    if issues:
        lines.append("\n### Current Issues")
        for issue in issues:
            lines.append(f"- [{issue.severity.upper()}] {issue.message}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Regression Scope Guard
# ---------------------------------------------------------------------------

MAX_REGRESSION_FIX_FILES = 5
MIN_TEST_COUNT_DELTA = 0  # Tests must not decrease


async def check_regression_scope(
    working_dir: str,
    changed_files: list[str],
) -> tuple[bool, str]:
    """Check if a regression fix is within acceptable scope.

    Returns (ok, reason). If ok is False, the fix should be
    escalated to a human instead of auto-applied.
    """
    if len(changed_files) > MAX_REGRESSION_FIX_FILES:
        return (
            False,
            f"Regression fix touched {len(changed_files)} files "
            f"(max {MAX_REGRESSION_FIX_FILES}). This looks like a "
            f"rewrite, not a fix. Escalating to human.",
        )

    # Check for suspicious patterns — block CI/Docker rewrites,
    # but allow config fixes (pyproject.toml, Makefile) since
    # those are often needed to fix broken test environments.
    blocked_infra = [
        f
        for f in changed_files
        if any(s in f for s in ["Dockerfile", "docker-compose", "ci.yml"])
    ]
    if blocked_infra:
        return (
            False,
            f"Regression fix modified infrastructure files: "
            f"{', '.join(blocked_infra)}. "
            f"This should be reviewed by a human.",
        )

    return True, "Regression fix scope is acceptable."


async def count_tests(working_dir: str) -> int:
    """Count the number of test functions in the repo."""
    import asyncio

    tests_dir = Path(working_dir) / "tests"
    if not tests_dir.exists():
        return 0

    proc = await asyncio.create_subprocess_exec(
        "grep",
        "-r",
        "--count",
        "def test_",
        str(tests_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    total = 0
    for line in stdout.decode().splitlines():
        parts = line.rsplit(":", 1)
        if len(parts) == 2:
            try:
                total += int(parts[1])
            except ValueError:
                pass
    return total


async def verify_test_count_not_decreased(
    working_dir: str,
    previous_count: int,
) -> tuple[bool, str]:
    """Verify that the number of tests has not decreased.

    Returns (ok, reason).
    """
    current = await count_tests(working_dir)
    if current < previous_count:
        return (
            False,
            f"Test count decreased from {previous_count} to {current}. "
            f"Agents are not allowed to remove tests.",
        )
    return True, f"Test count OK ({current} >= {previous_count})."


# ---------------------------------------------------------------------------
# Combined Pre-Flight Check
# ---------------------------------------------------------------------------


@dataclass
class PreFlightResult:
    """Result of all pre-flight guardrail checks."""

    tech_stack: TechStack
    secret_findings: list[SecretFinding]
    dependency_issues: list[DependencyIssue]
    passed: bool
    blocking_reasons: list[str] = field(default_factory=list)


def run_preflight_checks(working_dir: str) -> PreFlightResult:
    """Run all guardrail checks before starting a job.

    Returns a PreFlightResult. If .passed is False, the job
    should not proceed until blocking issues are resolved.
    """
    tech_stack = detect_tech_stack(working_dir)
    secrets = scan_for_secrets(working_dir)
    dep_issues = check_dependencies(working_dir)

    blocking: list[str] = []

    # Secrets are always blocking (except in test files)
    real_secrets = [s for s in secrets if s.pattern_name != ".env file"]
    if real_secrets:
        blocking.append(
            f"Found {len(real_secrets)} potential hardcoded secret(s). "
            f"Remove them before proceeding."
        )

    # .env committed is blocking
    env_files = [s for s in secrets if s.pattern_name == ".env file"]
    if env_files:
        blocking.append(".env file found in repo. Remove it and add to .gitignore.")

    # Dependency errors are blocking, warnings are not
    dep_errors = [d for d in dep_issues if d.severity == "error"]
    if dep_errors:
        for d in dep_errors:
            blocking.append(d.message)

    passed = len(blocking) == 0

    if passed:
        LOG.info("Pre-flight checks passed")
    else:
        LOG.warning(
            "Pre-flight checks FAILED: %s",
            "; ".join(blocking),
        )

    return PreFlightResult(
        tech_stack=tech_stack,
        secret_findings=secrets,
        dependency_issues=dep_issues,
        passed=passed,
        blocking_reasons=blocking,
    )
