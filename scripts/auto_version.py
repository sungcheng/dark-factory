"""Auto-version Dark Factory based on conventional commits since the last tag.

Runs in CI after a push to main. Inspects commit messages since the most
recent `vX.Y.Z` tag, picks a bump type (major/minor/patch), updates
`factory/__init__.py` and `CHANGELOG.md`, and exits 0 so the workflow
can commit + push. Exits with a non-zero signal encoded via stdout only
when there is nothing meaningful to release, so the workflow can skip
the commit step cleanly.

The companion `release.yml` watches for version changes on main and cuts
the actual git tag + GitHub Release — this script does not tag or push.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INIT_FILE = REPO_ROOT / "factory" / "__init__.py"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

_BREAKING_RE = re.compile(r"^.+!:|BREAKING CHANGE", re.MULTILINE)
_FEAT_RE = re.compile(r"^feat(\(.+\))?:", re.IGNORECASE)
_SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_VERSION_LINE_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')


def _run(*args: str) -> str:
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _last_tag() -> str | None:
    tag = _run("git", "describe", "--tags", "--abbrev=0", "--match", "v*")
    return tag or None


def _commits_since(tag: str | None) -> list[str]:
    log_range = f"{tag}..HEAD" if tag else "HEAD"
    raw = _run("git", "log", log_range, "--pretty=format:%s")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _determine_bump(commits: list[str]) -> str:
    has_feat = False
    for msg in commits:
        if _BREAKING_RE.search(msg):
            return "major"
        if _FEAT_RE.match(msg):
            has_feat = True
    return "minor" if has_feat else "patch"


def _apply_bump(version: str, bump_type: str) -> str:
    match = _SEMVER_RE.search(version)
    if not match:
        raise ValueError(f"Cannot parse version: {version}")
    major, minor, patch = (int(g) for g in match.groups())
    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _current_version() -> str:
    match = _VERSION_LINE_RE.search(INIT_FILE.read_text())
    if not match:
        raise RuntimeError("No __version__ found in factory/__init__.py")
    return match.group(1)


def _write_version(new_version: str) -> None:
    content = INIT_FILE.read_text()
    content = _VERSION_LINE_RE.sub(f'__version__ = "{new_version}"', content, count=1)
    INIT_FILE.write_text(content)


def _update_changelog(version: str, commits: list[str]) -> None:
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    entry = [f"## [{version}] - {today}\n\n"]
    entry.extend(f"- {msg}\n" for msg in commits)
    entry.append("\n")
    new_entry = "".join(entry)

    existing = CHANGELOG.read_text() if CHANGELOG.exists() else "# Changelog\n\n"
    header_match = re.search(r"^# .+\n", existing)
    insert_pos = header_match.end() if header_match else 0
    CHANGELOG.write_text(
        existing[:insert_pos] + "\n" + new_entry + existing[insert_pos:],
    )


def main() -> int:
    tag = _last_tag()
    commits = _commits_since(tag)
    commits = [c for c in commits if not c.startswith("chore: bump version to ")]

    if not commits:
        print("SKIP: no commits since last tag")
        return 0

    bump_type = _determine_bump(commits)
    current = _current_version()
    new_version = _apply_bump(current, bump_type)

    if new_version == current:
        print(f"SKIP: version unchanged ({current})")
        return 0

    _write_version(new_version)
    _update_changelog(new_version, commits)
    print(f"BUMPED: {current} -> {new_version} ({bump_type})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
