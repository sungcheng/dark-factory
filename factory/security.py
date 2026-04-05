"""Security hooks — command allowlisting for agent subprocesses.

Agents run bash commands via Claude Code. This module provides
a CLAUDE.md-based security policy that restricts what commands
agents can execute.
"""
from __future__ import annotations

import logging
from pathlib import Path

LOG = logging.getLogger(__name__)

# Commands that are safe for agents to run
ALLOWED_COMMANDS: set[str] = {
    # File operations
    "ls", "cat", "head", "tail", "find", "wc", "diff", "tree",
    # Programming
    "python", "python3", "pip", "uv", "npm", "npx", "node",
    # Build & test
    "make", "pytest", "ruff", "mypy", "bandit",
    # Version control
    "git",
    # Process info (read-only)
    "ps", "which", "env", "printenv", "echo",
    # Docker (for built services)
    "docker", "docker-compose",
}

# Commands that are always blocked
BLOCKED_COMMANDS: set[str] = {
    "curl", "wget",  # No arbitrary network requests
    "ssh", "scp",    # No remote access
    "sudo", "su",    # No privilege escalation
    "shutdown", "reboot",
    "mount", "umount",
    "dd", "mkfs",
    "iptables", "ufw",
}

# Dangerous flags that should be blocked even on allowed commands
BLOCKED_PATTERNS: list[str] = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf $HOME",
    "chmod -R 777",
    "git push --force",
    "> /dev/",
    "| sh",
    "| bash",
    "eval ",
    "exec ",
]


def generate_security_policy() -> str:
    """Generate a CLAUDE.md security section for agent working directories.

    This is written to the target project's CLAUDE.md so Claude Code
    respects the restrictions when running as an agent.
    """
    allowed = ", ".join(sorted(ALLOWED_COMMANDS))
    blocked = ", ".join(sorted(BLOCKED_COMMANDS))

    return f"""
## Security Policy (Dark Factory)

This project is managed by Dark Factory autonomous agents.

### Allowed Commands
Only these commands may be used in bash: {allowed}

### Blocked Commands
Never run: {blocked}

### Rules
- Never run commands that delete system files
- Never make network requests outside of `make test` or `make check`
- Never modify files outside the project directory
- Never install global packages
- Never run `rm -rf` on the project root or any parent directory
- Never use `sudo` or attempt privilege escalation
- Never pipe output to `sh`, `bash`, or `eval`
"""


def write_security_policy(working_dir: str) -> None:
    """Write or append security policy to project CLAUDE.md."""
    claude_md = Path(working_dir) / "CLAUDE.md"
    policy = generate_security_policy()

    if claude_md.exists():
        existing = claude_md.read_text()
        if "Security Policy (Dark Factory)" not in existing:
            claude_md.write_text(existing + "\n" + policy)
    else:
        claude_md.write_text(policy)

    LOG.info("Security policy written to %s", claude_md)
