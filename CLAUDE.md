# CLAUDE.md

Global instructions for Claude Code when working in this repository.

## Project Overview

Dark Factory is an autonomous AI coding pipeline. The orchestrator spawns Claude Code subprocesses (agents) that handle the full development lifecycle: spec → tasks → tests → code → PR → merge.

## Architecture

- **Orchestrator** (`factory/orchestrator.py`) — dumb Python script, no AI. Manages agent lifecycle, task ordering, and GitHub integration.
- **Agents** (`factory/agents/`) — each agent runs as a fresh `claude -p` subprocess. No shared memory between agents.
- **Prompts** (`factory/prompts/`) — Markdown files that define each agent's personality and hard rules. Changes here affect agent behavior without touching code.
- **State** (`factory/state.py`) — job progress persisted to `~/.dark-factory/state/` for crash recovery.
- **Security** (`factory/security.py`) — command allowlist written to target repos' CLAUDE.md files.

## Build & Test Commands

```bash
make develop        # Install all dependencies (uv sync)
make test           # Run all tests
make test-cov       # Tests with coverage
make check          # Lint (ruff) + type check (mypy)
make format         # Auto-format with ruff
make help           # Show all commands
```

## Python Style

- Python 3.11+, async/await throughout
- Formatter/linter: ruff (line-length 88)
- Type checker: mypy (strict mode)
- Type hints on all functions
- Imports: one per line, sorted by ruff isort
- Use `from __future__ import annotations` in every module
- Dataclasses for data containers
- f-strings for formatting
- Logging: `LOG = logging.getLogger(__name__)` at module level

## Key Conventions

- Orchestrator must stay "dumb" — no AI logic, just subprocess management
- Agents communicate through files (tasks.json, feedback.md, approved.md)
- Never hardcode secrets — use environment variables via python-dotenv
- Tests live in `tests/`, use pytest, prefix with `test_`
- All async functions use `async def` / `await` — no sync subprocess calls in agents or orchestrator
- Agent runners return `AgentResult` — check `.success` before proceeding

## Hard Boundaries (never break these)

- Generator agent CANNOT access test files
- Evaluator agent CANNOT access source files
- Each agent gets a fresh context window — no memory between spawns
- Max 5 red-green rounds per task before escalating to human
- No `git push --force`, no destructive git operations
