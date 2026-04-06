"""Version Bump skill — auto-version based on conventional commits."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC
from datetime import datetime
from pathlib import Path

from factory.skills.base import Skill
from factory.skills.base import SkillContext
from factory.skills.base import SkillPhase
from factory.skills.base import SkillResult

LOG = logging.getLogger(__name__)

# Conventional commit patterns
_BREAKING_RE = re.compile(r"^.+!:|BREAKING CHANGE", re.MULTILINE)
_FEAT_RE = re.compile(r"^feat(\(.+\))?:")
_FIX_RE = re.compile(r"^fix(\(.+\))?:")
_PATCH_PREFIXES = ("chore", "docs", "refactor", "style", "perf", "test", "ci")

# Semver pattern for pyproject.toml and package.json
_SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


async def _get_commits_since_last_tag(
    working_dir: str,
) -> list[str]:
    """Return commit messages since the last git tag.

    If no tags exist, returns all commit messages.
    """
    # Try to find the latest tag
    proc = await asyncio.create_subprocess_exec(
        "git",
        "describe",
        "--tags",
        "--abbrev=0",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    last_tag = stdout.decode().strip()

    if last_tag and proc.returncode == 0:
        log_range = f"{last_tag}..HEAD"
    else:
        log_range = "HEAD"

    proc = await asyncio.create_subprocess_exec(
        "git",
        "log",
        log_range,
        "--pretty=format:%s",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    lines = stdout.decode().strip().splitlines()
    return [line.strip() for line in lines if line.strip()]


def _determine_bump(commits: list[str]) -> str:
    """Determine the bump type from conventional commit messages.

    :param commits: List of commit message subject lines.
    :return: One of "major", "minor", or "patch".
    """
    has_feat = False

    for msg in commits:
        if _BREAKING_RE.search(msg):
            return "major"
        if _FEAT_RE.match(msg):
            has_feat = True

    if has_feat:
        return "minor"
    return "patch"


def _apply_bump(version: str, bump_type: str) -> str:
    """Apply a semver bump to a version string.

    :param version: Current version (e.g. "0.1.0").
    :param bump_type: One of "major", "minor", "patch".
    :return: New version string.
    """
    match = _SEMVER_RE.search(version)
    if not match:
        return "0.1.0"

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1

    return f"{major}.{minor}.{patch}"


async def _bump_python_version(
    working_dir: str,
    bump_type: str,
) -> str:
    """Bump version in pyproject.toml and return the new version.

    :param working_dir: Path to the project root.
    :param bump_type: One of "major", "minor", "patch".
    :return: The new version string.
    """
    pyproject = Path(working_dir) / "pyproject.toml"
    content = pyproject.read_text()

    # Find current version
    version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if not version_match:
        raise ValueError("No version found in pyproject.toml")

    old_version = version_match.group(1)
    new_version = _apply_bump(old_version, bump_type)

    # Replace version using simple string replacement
    new_content = content.replace(
        f'version = "{old_version}"',
        f'version = "{new_version}"',
    )
    pyproject.write_text(new_content)
    LOG.info("Bumped pyproject.toml: %s → %s", old_version, new_version)
    return new_version


async def _bump_node_version(
    working_dir: str,
    bump_type: str,
) -> str:
    """Bump version in package.json and return the new version.

    :param working_dir: Path to the project root.
    :param bump_type: One of "major", "minor", "patch".
    :return: The new version string.
    """
    package_json = Path(working_dir) / "package.json"
    content = package_json.read_text()

    version_match = re.search(r'"version"\s*:\s*"([^"]+)"', content)
    if not version_match:
        raise ValueError("No version found in package.json")

    old_version = version_match.group(1)
    new_version = _apply_bump(old_version, bump_type)

    new_content = content.replace(
        f'"version": "{old_version}"',
        f'"version": "{new_version}"',
    )
    package_json.write_text(new_content)
    LOG.info("Bumped package.json: %s → %s", old_version, new_version)
    return new_version


async def _update_changelog(
    working_dir: str,
    version: str,
    commits: list[str],
) -> None:
    """Update CHANGELOG.md with a new version section.

    :param working_dir: Path to the project root.
    :param version: The new version string.
    :param commits: List of commit messages to include.
    """
    changelog = Path(working_dir) / "CHANGELOG.md"
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    entry_lines = [f"## [{version}] - {today}\n\n"]
    for msg in commits:
        entry_lines.append(f"- {msg}\n")
    entry_lines.append("\n")
    new_entry = "".join(entry_lines)

    if changelog.exists():
        existing = changelog.read_text()
        # Insert after the first heading line (# Changelog)
        header_match = re.search(r"^# .+\n", existing)
        if header_match:
            insert_pos = header_match.end()
            content = existing[:insert_pos] + "\n" + new_entry + existing[insert_pos:]
        else:
            content = new_entry + existing
    else:
        content = "# Changelog\n\n" + new_entry

    changelog.write_text(content)
    LOG.info("Updated CHANGELOG.md with version %s", version)


class VersionBump(Skill):
    """Bump version based on conventional commits.

    Reads commit messages since the last tag, determines the bump type
    (major/minor/patch), updates version files, writes to CHANGELOG.md,
    and creates a git tag. Does NOT push the tag.
    """

    name = "version_bump"
    description = "Bump version based on conventional commits"
    phase = SkillPhase.POST_JOB

    async def run(self, ctx: SkillContext) -> SkillResult:
        """Execute the version bump skill."""
        wd = Path(ctx.working_dir)

        # Get commits since last tag
        commits = await _get_commits_since_last_tag(ctx.working_dir)
        if not commits:
            return SkillResult(
                success=True,
                message="No commits to version",
            )

        bump_type = _determine_bump(commits)
        LOG.info("Determined bump type: %s", bump_type)

        # Bump version in the appropriate file
        has_pyproject = (wd / "pyproject.toml").exists()
        has_package = (wd / "package.json").exists()
        new_version = ""
        modified: list[str] = []

        if has_pyproject:
            new_version = await _bump_python_version(
                ctx.working_dir,
                bump_type,
            )
            modified.append("pyproject.toml")

        if has_package:
            new_version = await _bump_node_version(
                ctx.working_dir,
                bump_type,
            )
            modified.append("package.json")

        if not new_version:
            return SkillResult(
                success=False,
                message="No pyproject.toml or package.json found",
            )

        # Update changelog
        await _update_changelog(ctx.working_dir, new_version, commits)
        modified.append("CHANGELOG.md")

        # Create git tag
        tag = f"v{new_version}"
        proc = await asyncio.create_subprocess_exec(
            "git",
            "tag",
            "-a",
            tag,
            "-m",
            f"Release {tag}",
            cwd=ctx.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            LOG.warning("Failed to create tag %s: %s", tag, stderr.decode())
            return SkillResult(
                success=False,
                message=f"Version bumped to {new_version} but tagging failed",
                files_modified=modified,
                data={"version": new_version, "bump_type": bump_type},
            )

        LOG.info("Created tag %s", tag)
        return SkillResult(
            success=True,
            message=f"Bumped to {new_version} ({bump_type}), tagged {tag}",
            files_modified=modified,
            data={
                "version": new_version,
                "tag": tag,
                "bump_type": bump_type,
            },
        )
