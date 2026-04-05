"""Tests for security hooks."""

from __future__ import annotations

import tempfile
from pathlib import Path

from factory.security import ALLOWED_COMMANDS
from factory.security import BLOCKED_COMMANDS
from factory.security import generate_security_policy
from factory.security import write_security_policy


class TestSecurityPolicy:
    """Tests for security policy generation."""

    def test_no_overlap(self) -> None:
        """Allowed and blocked commands don't overlap."""
        overlap = ALLOWED_COMMANDS & BLOCKED_COMMANDS
        assert overlap == set(), f"Overlap: {overlap}"

    def test_essential_commands_allowed(self) -> None:
        """Essential dev commands are in the allowlist."""
        for cmd in ("python", "make", "git", "pytest", "ruff", "mypy"):
            assert cmd in ALLOWED_COMMANDS

    def test_dangerous_commands_blocked(self) -> None:
        """Dangerous commands are blocked."""
        for cmd in ("sudo", "ssh", "curl", "wget"):
            assert cmd in BLOCKED_COMMANDS

    def test_policy_contains_rules(self) -> None:
        """Generated policy includes key restrictions."""
        policy = generate_security_policy()
        assert "Security Policy (Dark Factory)" in policy
        assert "Allowed Commands" in policy
        assert "Blocked Commands" in policy
        assert "sudo" in policy
        assert "make" in policy


class TestWriteSecurityPolicy:
    """Tests for writing policy to CLAUDE.md."""

    def test_creates_new_claude_md(self) -> None:
        """Creates CLAUDE.md if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            write_security_policy(tmpdir)
            claude_md = Path(tmpdir) / "CLAUDE.md"
            assert claude_md.exists()
            assert "Security Policy" in claude_md.read_text()

    def test_appends_to_existing(self) -> None:
        """Appends policy to existing CLAUDE.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_md = Path(tmpdir) / "CLAUDE.md"
            claude_md.write_text("# My Project\n\nExisting content.\n")
            write_security_policy(tmpdir)
            content = claude_md.read_text()
            assert "My Project" in content
            assert "Security Policy" in content

    def test_no_duplicate_policy(self) -> None:
        """Doesn't write policy twice."""
        with tempfile.TemporaryDirectory() as tmpdir:
            write_security_policy(tmpdir)
            write_security_policy(tmpdir)
            content = (Path(tmpdir) / "CLAUDE.md").read_text()
            assert content.count("Security Policy (Dark Factory)") == 1
