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

## Rules — Always Follow

### Testing
- Every new feature or module MUST have tests
- Run `make test` before committing — all tests must pass
- Run `make check` before committing — lint and types must be clean
- Test edge cases: empty input, invalid input, error paths
- Use pytest fixtures for setup/teardown
- Aim for >80% test coverage on new code

### Security
- NEVER hardcode secrets, tokens, API keys, or passwords in code
- All secrets come from environment variables via python-dotenv
- NEVER log secrets — scrub sensitive data from log output
- NEVER commit `.env` files — only `.env.example` with placeholders
- Run `bandit -r factory/` to check for security issues when touching security-sensitive code
- Validate all external input at system boundaries

### API Standards
- All APIs must be versioned: `/api/v1/resource` not `/api/resource`
- Use FastAPI routers with version prefix: `router = APIRouter(prefix="/api/v1")`
- Pydantic models for all request/response schemas
- Proper HTTP status codes (201 for created, 404 for not found, 422 for validation)
- Include OpenAPI docs (FastAPI auto-generates these)

### Code Quality
- Always validate your changes compile and pass tests before returning
- Abstract repeated patterns into shared modules when used 3+ times
- Keep functions small and focused — one function, one job
- Use descriptive names — avoid abbreviations except well-known ones (URL, API, PR)
- Handle errors explicitly — no bare `except:`, no silently swallowed exceptions
- Log meaningful messages — include context (repo name, issue number, task id)

### Python Style
- Python 3.11+, async/await throughout
- Formatter/linter: ruff (line-length 88)
- Type checker: mypy (strict mode)
- Type hints on ALL functions (parameters and return types)
- Imports: one per line, sorted by ruff isort
- Use `from __future__ import annotations` in every module
- Dataclasses for data containers
- f-strings for formatting
- Logging: `LOG = logging.getLogger(__name__)` at module level

### Architecture
- Orchestrator must stay "dumb" — no AI logic, just subprocess management
- Agents communicate through files (tasks.json, feedback.md, approved.md)
- All async functions use `async def` / `await` — no sync subprocess calls
- Agent runners return `AgentResult` — check `.success` before proceeding
- New features should follow existing patterns — look at how similar things are done before adding something new
- Keep dependencies minimal — don't add a library for something the stdlib handles

## Documentation

- Always update README.md and DESIGN.md after making code changes (new features, commands, templates, config)
- Do not wait for the user to ask — docs should stay in sync with code automatically
- Include doc updates in the same commit or as a follow-up in the same session

## Hard Boundaries (never break these)

- Generator agent CANNOT access test files
- Evaluator agent CANNOT access source files
- Each agent gets a fresh context window — no memory between spawns
- Max 5 red-green rounds per task before escalating to human
- No `git push --force`, no destructive git operations
- No secrets in source code, logs, or commit messages


## Security Policy (Dark Factory)

This project is managed by Dark Factory autonomous agents.

### Allowed Commands
Only these commands may be used in bash: bandit, cat, diff, docker, docker-compose, echo, env, find, git, head, ls, make, mypy, node, npm, npx, pip, printenv, ps, pytest, python, python3, ruff, tail, tree, uv, wc, which

### Blocked Commands
Never run: curl, dd, iptables, mkfs, mount, reboot, scp, shutdown, ssh, su, sudo, ufw, umount, wget

### Rules
- Never run commands that delete system files
- Never make network requests outside of `make test` or `make check`
- Never modify files outside the project directory
- Never install global packages
- Never run `rm -rf` on the project root or any parent directory
- Never use `sudo` or attempt privilege escalation
- Never pipe output to `sh`, `bash`, or `eval`
