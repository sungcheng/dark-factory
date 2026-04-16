# Dark Factory — Full Design Document

## Context

Build an autonomous AI coding pipeline ("dark factory") where AI agents handle the full software development lifecycle — from spec to deployment — with no human code review. The system uses a TDD Red-Green approach with separated agents to ensure quality without human intervention.

## 1. Vision

```
┌─────────────────────────────────────────────────────────────┐
│                      DARK FACTORY                           │
│                                                             │
│   "You write the spec. AI builds, tests, and deploys it."   │
│                                                             │
│   Human input: GitHub Issue with requirements               │
│   Human output: Working software in production              │
│   Everything in between: autonomous                         │
└─────────────────────────────────────────────────────────────┘
```

## 2. Key Design Principles

> Inspired by Anthropic's own research:
> - [Harness Design for Long-Running Apps](https://www.anthropic.com/engineering/harness-design-long-running-apps)
> - [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

1. **Separate generation from evaluation** — never let the coder grade its own work
2. **TDD Red-Green** — QA writes tests first, Developer makes them pass
3. **Fresh context per agent** — no memory bleed, no context rot
4. **Communicate through files** — artifacts survive context resets
5. **Orchestrator is dumb** — just a Python script, no AI in the coordinator
6. **Hard permission boundaries** — Generator can't touch tests, Evaluator can't touch source
7. **Max iteration cap** — 5 rounds then escalate to human
8. **Start simple, remove complexity** — as models improve, delete harness code
9. **Shared principles prepended to every agent** — `factory/prompts/_principles.md` (derived from Andrej Karpathy's observations on LLM coding failure modes) is loaded by `load_prompt()` and injected before each role prompt, so every agent inherits the same guidelines: think before doing, simplicity first, surgical changes, goal-driven execution

## 3. Architecture Overview

![Architecture Overview](diagrams/architecture.png)

## 4. The Agent Loop — TDD Red-Green

The core innovation: **the QA Engineer writes tests first, the Developer makes them pass.** No agent grades its own work.

![Agent Loop - TDD Red-Green](diagrams/agent-loop.png)

### The Red-Green Loop in Action

```
Round 1:
  QA Engineer: writes 12 tests             → all RED
  Developer:   writes code                  → 8 GREEN, 4 RED
  
Round 2:
  QA Engineer: "4 still fail because X, Y"
  Developer:   fixes                        → 11 GREEN, 1 RED
  
Round 3:
  Developer:   fixes last test              → 12 GREEN
  QA Engineer: reviews code quality         → APPROVED ✅
  
Auto-merge → CI/CD → Deploy
```

### Hard Rules

| Rule | Why |
|---|---|
| Generator CANNOT edit test files | Prevents cheating — can't weaken tests to pass |
| Evaluator CANNOT edit source files | Clean separation of concerns |
| Each agent gets fresh context | No memory bleed, no context rot |
| Agents communicate through files | Artifacts survive context resets |
| Max 5 red-green rounds | Prevents infinite loops, escalates with progressive strategy |

### Progressive Escalation Strategy

Not all failures are equal. The orchestrator escalates through increasingly aggressive strategies:

| Round | Strategy | Why |
|---|---|---|
| 1-3 | Normal red-green | Developer gets QA feedback, iterates |
| 4 | Enhanced feedback | QA includes full tracebacks, root cause analysis, explicit "don't repeat X" |
| 5 | Fresh approach | Developer prompted to try a fundamentally different approach, not patch the previous one |
| Re-run | Auto-reset | Failed tasks reset to pending with fresh 5 rounds — re-running the job retries automatically |

### Architect Guidelines

The Architect's `planner.md` enforces:

- **Layered architecture for any backend service** — task-1 scaffolds `app/routers/`, `app/services/`, `app/repositories/`, `models.py`, `schemas.py`, `deps.py`. Every folder gets an `__init__.py`. This is a hard rule, not a judgment call: DF produces production code and the cost of an empty folder is zero, while the cost of flat-on-something-that-grows is duplicate modules from parallel worktrees.
- **Name target files for parallel worktrees** — when multiple tasks in a batch run in parallel, the task description must specify the module each should edit (e.g., "add `search_movies` to `app/routers/movies.py` via `app/services/movie_service.py`"), so worktrees don't independently invent overlapping filenames.

The QA Engineer's `evaluator.md` adds:

- **Realistic fixtures** — when the change processes user-supplied data (CSV, JSON, uploads), tests must include realistic fixtures, not only developer-chosen toy inputs. Toy inputs miss edge cases that only appear in real data.

### Common Failure Modes

| Failure Mode | Root Cause | How Agents Handle It |
|---|---|---|
| **Vague QA feedback** | QA says "test failed" without specifics | QA prompt requires exact file:line references, full error output, and root cause analysis |
| **Developer repeats same mistake** | Doesn't read feedback carefully | Developer prompt: if Round 2+, must try a different approach. QA calls out repeated failures explicitly |
| **Environment/dependency issue** | Wrong import path, missing package, version mismatch | QA must distinguish code bugs from environment issues. Developer checks project structure before changing logic |
| **Impossible test** | Test expects behavior that conflicts with requirements | QA notes suspected test issues in feedback (but never modifies tests). Escalates to human via needs-human issue |

## 5. How Agents Run

The orchestrator is a **dumb Python script** — it doesn't use AI. It just spawns Claude Code subprocesses in the right order.

![Orchestrator Flow](diagrams/orchestrator.png)

Each agent is a Claude Code subprocess with its own fresh context window. The orchestrator controls which tools each agent can access — this is how we enforce the hard boundaries (Generator can't touch tests, Evaluator can't touch source).

```python
# factory/orchestrator.py (pseudocode — actual code is async)

async def run_job(repo_name, issue_number):
    """Main orchestrator loop — no AI, just subprocess management."""

    # Step 0: Regression gate — existing tests must pass
    await run_evaluator_regression(working_dir)

    # Step 1: Spawn the Architect
    await run_planner(issue_body, working_dir)
    tasks = load_tasks("tasks.json")

    # Step 2: Process tasks in dependency order
    for batch in get_ready_batches(tasks):
        # Tasks in same batch run in parallel
        await asyncio.gather(*[
            _process_task(task, ctx) for task in batch
        ])

async def _process_task(task, ctx):
    """Per-task pipeline: contracts → parallel(tests+scaffold) → red-green."""

    # Create per-task branch from latest main
    branch = f"factory/issue-{issue}/task-{task.id}"

    # Step 1: QA writes interface contracts (haiku — fast)
    await run_evaluator_contracts(task, working_dir)

    # Step 2: QA writes tests + Developer scaffolds (parallel)
    await asyncio.gather(
        run_evaluator_red(task, working_dir),
        run_generator_scaffold(task, working_dir),
    )

    # Step 3: Red-Green loop (max 5 rounds)
    for round in range(1, 6):
        await run_generator(task, working_dir)  # Developer writes code

        # Smart QA: run tests directly first
        test_passed = await _run_tests_with_check(working_dir)
        if test_passed:
            break  # GREEN — skip QA agent entirely

        # Tests failed — spawn QA for detailed feedback
        await run_evaluator_review(task, working_dir)

    # Step 4: Push → PR → merge to main
    github.create_pr(branch, title=f"feat: {task.title}")
    github.merge_pr(pr_number)
```

### Per-Role Model and Timeout Selection

```python
DEFAULT_MODELS = {
    "Architect": "opus",           # Complex planning
    "Developer": "opus",           # Complex coding
    "QA Engineer (RED)": "sonnet", # Test writing
    "QA Engineer (Review)": "sonnet",
    "QA Engineer (Contracts)": "haiku",   # Fast
    "QA Engineer (Regression)": "haiku",  # Fast
}

DEFAULT_TIMEOUTS = {
    "Architect": 1200,             # 20 min
    "Developer": 1800,             # 30 min
    "QA Engineer (RED)": 1200,     # 20 min
    "QA Engineer (Review)": 600,   # 10 min
    "QA Engineer (Contracts)": 300,# 5 min
    "QA Engineer (Regression)": 300,# 5 min
}
```

## 6. Tech Stack

```
┌─────────────────────────────────────────────────────────────┐
│                        TECH STACK                            │
├──────────────────┬──────────────────────────────────────────┤
│                  │                                          │
│  FACTORY         │  Python                                  │
│  (your machine)  │  ├── Orchestrator (subprocess mgmt)      │
│                  │  ├── Claude Code CLI (agent runtime)     │
│                  │  └── GitHub API (PyGithub)               │
│                  │                                          │
├──────────────────┼──────────────────────────────────────────┤
│                  │                                          │
│  BACKEND         │  Python + FastAPI                        │
│                  │  ├── Status API (agent monitoring)       │
│                  │  ├── Service APIs (what factory builds)  │
│                  │  ├── WebSocket (live dashboard updates)  │
│                  │  └── PostgreSQL (Supabase free tier)     │
│                  │                                          │
├──────────────────┼──────────────────────────────────────────┤
│                  │                                          │
│  FRONTEND        │  React + TypeScript                      │
│                  │  ├── Mission Control dashboard           │
│                  │  ├── Vite (build tool)                   │
│                  │  └── TailwindCSS (styling)               │
│                  │                                          │
├──────────────────┼──────────────────────────────────────────┤
│                  │                                          │
│  TESTING         │  pytest (unit + integration)             │
│                  │  Playwright (E2E browser tests)          │
│                  │  Both free, open source                  │
│                  │                                          │
├──────────────────┼──────────────────────────────────────────┤
│                  │                                          │
│  CI/CD           │  GitHub Actions (build + test)           │
│                  │  Docker (containerization)               │
│                  │  Docker Compose (local staging/prod)     │
│                  │                                          │
├──────────────────┼──────────────────────────────────────────┤
│                  │                                          │
│  INFRASTRUCTURE  │  Docker Compose (Phase 1-3)              │
│  (future)        │  k3d + ArgoCD (Phase 4)                  │
│                  │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

## 7. Project Structure

```
dark-factory/
├── CLAUDE.md                          # Global agent rules + coding standards
├── README.md
├── pyproject.toml                     # uv + hatchling build config
├── Makefile                           # Dev shortcuts (test, check, format)
│
├── factory/                           # The orchestrator
│   ├── __init__.py
│   ├── cli.py                         # CLI — start, run, retry, repos, create-issue
│   ├── orchestrator.py                # Main loop — task batching, red-green cycle
│   ├── github_client.py               # GitHub API — issues, PRs, repos
│   ├── state.py                       # Session state persistence (~/.dark-factory/)
│   ├── security.py                    # Command allowlisting for target repos
│   ├── agents/
│   │   ├── base.py                    # Agent runner (async subprocess spawning)
│   │   ├── planner.py                 # Spawns Architect
│   │   ├── evaluator.py               # Spawns QA (contracts, red, review, regression)
│   │   └── generator.py               # Spawns Developer (scaffold + implementation)
│   ├── prompts/
│   │   ├── _principles.md             # Karpathy-derived principles, prepended to every agent
│   │   ├── planner.md                 # Architect personality + rules
│   │   ├── evaluator.md               # QA Engineer personality + rules
│   │   └── generator.md               # Developer personality + rules
│   └── templates/
│       ├── __init__.py                # Template engine (apply_template)
│       ├── fastapi/                   # FastAPI project scaffold — layered app/ (routers, services, repositories)
│       ├── fullstack/                 # FastAPI + React scaffold
│       └── terraform/                 # Terraform IaC scaffold
│
├── tests/                             # Unit tests (408 passing)
│   ├── test_orchestrator.py
│   ├── test_agents.py
│   ├── test_github_client.py
│   ├── test_state.py
│   └── test_security.py
│
├── diagrams/                          # Architecture diagrams
│
└── .github/
    └── workflows/
        └── ci.yml                     # Lint + format + tests
```

## 8. Coding Standards

Every service the factory builds follows the same standards. The Architect bakes these into the project from the start.

### Makefile (every service gets one)

```makefile
.PHONY: develop test fast-test check format lint clean

develop:                ## Create virtualenv with dev dependencies
	python -m venv .venv && .venv/bin/pip install -e ".[dev]"

test:                   ## Run all tests
	pytest tests/ -v --tb=short

fast-test:              ## Run tests excluding slow markers
	pytest tests/ -v --tb=short -m "not slow"

check:                  ## Full lint suite
	make lint
	make typecheck
	make security

lint:                   ## Flake8 + Ruff
	ruff check src/ tests/
	ruff format --check src/ tests/

typecheck:              ## Type checking
	mypy src/

security:               ## Security analysis
	bandit -r src/ -ll

format:                 ## Auto-format
	ruff format src/ tests/
	ruff check --fix src/ tests/

clean:                  ## Remove build artifacts
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache dist *.egg-info

docker-build:           ## Build Docker image
	docker build -t $(SERVICE_NAME):latest .

docker-run:             ## Run Docker container
	docker run -p 8000:8000 $(SERVICE_NAME):latest
```

### Standards Enforced by QA Engineer

The Evaluator agent prompt includes these rules:

| Standard | Enforcement |
|---|---|
| **Makefile exists** | QA checks for Makefile in project root |
| **`make test` passes** | QA runs `make test` as part of review |
| **`make check` passes** | QA runs full lint suite before approving |
| **Test coverage > 80%** | QA runs `pytest --cov` and checks threshold |
| **Dockerfile exists** | QA verifies containerization |
| **No secrets in code** | QA runs `bandit` + checks for hardcoded keys |
| **Type hints** | QA runs `mypy` — no errors |
| **Docstrings** | QA checks public functions have docstrings |

### CI/CD Pipeline Standards (every repo)

```yaml
# .github/workflows/ci.yml (auto-generated by Architect)
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: make develop
      - run: make check
      - run: make test

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
```

## 9. Secrets & Configuration Management

Secrets (API keys, database credentials, tokens) are never stored in code or git.

### Strategy by Environment

| Environment | Secrets Storage | How It Works |
|---|---|---|
| **Local dev** | `.env` files (git-ignored) | Developer creates `.env` from `.env.example` |
| **CI/CD** | GitHub Actions Secrets | Stored in repo settings, injected as env vars |
| **Staging/Prod** | Docker Compose `.env` | Per-environment env files, git-ignored |
| **Future (K8s)** | HashiCorp Vault or K8s Secrets | Vault agent injects secrets at runtime |

### What Gets Stored as Secrets

| Secret | Used By |
|---|---|
| `GITHUB_TOKEN` | Orchestrator (create repos, issues, PRs) |
| `OPENWEATHERMAP_API_KEY` | Example: weather-api service |
| `DATABASE_URL` | Service database connections |
| `SENTRY_DSN` | Error tracking |
| `SLACK_WEBHOOK_URL` | Notifications |
| `SUPABASE_URL` / `SUPABASE_KEY` | Database access |

### How the Factory Handles Secrets

The Architect creates a `.env.example` in every new repo with placeholder values:

```
# .env.example (committed to git)
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
SENTRY_DSN=https://key@sentry.io/project
API_KEY=your-api-key-here
```

The actual `.env` file is in `.gitignore` and never committed. The QA Engineer checks for hardcoded secrets using `bandit` during review.

### Future: HashiCorp Vault

When moving to Kubernetes (Phase 4), secrets migrate to Vault:
- Vault runs as a container in the k3d cluster
- Services authenticate via Kubernetes service accounts
- Secrets are injected as environment variables at pod startup
- Automatic secret rotation
- Audit log of all secret access
- Free and open source

## 10. Security

### Threat Model

In a dark factory, AI agents have write access to repos, can create infrastructure, and auto-deploy code. Security must be layered.

### Code Security

| Layer | How It's Enforced |
|---|---|
| **No hardcoded secrets** | QA Engineer runs `bandit` on every PR. Fails if secrets detected. |
| **Dependency scanning** | GitHub Dependabot alerts on vulnerable packages. CI fails on critical CVEs. |
| **SAST (Static Analysis)** | `bandit` (Python security linter) runs in CI and QA review |
| **Input validation** | QA Engineer writes tests for injection attacks, malformed input |
| **SQL injection prevention** | FastAPI + SQLAlchemy use parameterized queries by default |
| **CORS configuration** | Explicitly configured per service — no wildcard `*` in production |
| **Rate limiting** | Every public API gets rate limiting as a standard requirement |

### Agent Security

| Risk | Mitigation |
|---|---|
| Agent writes malicious code | Evaluator (separate agent, fresh context) reviews all code |
| Agent modifies test files to cheat | Hard boundary: Generator CANNOT edit test files |
| Agent accesses unauthorized repos | GitHub token scoped to specific repos only |
| Agent creates public repos | Architect prompt explicitly requires private repos |
| Agent deploys broken code | CI must pass + staging health checks before prod |
| Infinite loop / runaway costs | Max 5 rounds per task, max tasks per job, token budget per agent |
| Agent leaks secrets in logs | Structured logging with secret-scrubbing middleware |

### Infrastructure Security

| Layer | Implementation |
|---|---|
| **Secrets storage** | See Section 9 — `.env` files (local), GitHub Secrets (CI), Vault (future) |
| **Container security** | Non-root Docker images, read-only filesystems where possible |
| **Network isolation** | Docker Compose networks isolate staging from production |
| **HTTPS** | All external endpoints served over TLS |
| **Authentication** | API keys for service-to-service, JWT for user-facing endpoints |
| **GitHub permissions** | Fine-grained PAT — only repos the factory needs, no admin access |
| **Branch protection** | Main branch protected by default — requires PRs, blocks force pushes, enforces linear history |
| **Audit trail** | Every agent action logged to PostgreSQL event store with timestamps |

### Security Checklist (enforced by QA Engineer)

The Evaluator agent prompt includes these security checks on every PR:

1. No secrets in source code (`bandit -r src/`)
2. No `*` CORS origins in production config
3. All user inputs validated and sanitized
4. SQL queries use parameterized statements (no f-strings in queries)
5. Authentication on all non-public endpoints
6. Rate limiting configured
7. Error responses don't leak internal details (no stack traces in prod)
8. Dependencies pinned to specific versions
9. Docker image uses non-root user

## 10.5. Guardrails (`factory/guardrails.py`)

Pre-flight and runtime checks that protect production repos from agent mistakes.

### Tech Stack Detection

Before any agent spawns, the orchestrator scans the repo for technology markers:
- **File markers**: `pyproject.toml` (Python), `package.json` (Node), `go.mod` (Go), `main.tf` (Terraform), etc.
- **Content markers**: parses config files for framework names (FastAPI, React, SQLAlchemy, Tailwind, etc.)

The detected stack is injected into every agent's prompt as a guardrail block:
- Planner: "Never plan a migration to a different framework"
- Developer: "Use the existing framework — do not introduce a competing one"
- QA: "Check that no competing frameworks were introduced"

### Secret Scanning

Scans all source files for hardcoded credentials:
- AWS keys, GitHub tokens, Slack tokens, JWTs, private keys
- Generic patterns: `api_key = "..."`, `secret = "..."`, `password = "..."`
- Committed `.env` files

Runs at two points:
1. **Pre-flight**: blocks the job if secrets found
2. **Post-merge**: warns if secrets appeared during development

### File Boundary Enforcement

Feature tasks are restricted from modifying:
- `CLAUDE.md`, `Makefile`, `.gitignore`
- CI workflows (`.github/workflows/`)
- Docker files (`Dockerfile`, `docker-compose.yml`)
- Config files (`pyproject.toml`, `setup.cfg`, `.ini`)

Infrastructure tasks (scaffolding, CI, Docker) get relaxed boundaries.

### Dependency Guardrails

- Detects competing packages (e.g., `requests` + `httpx`, `Flask` + `FastAPI`)
- Tells agents what dependencies are already installed
- Warns on overlapping functionality

### Regression Scope Guard

- Blocks regression fixes that touch more than 5 files (likely a rewrite, not a fix)
- Blocks fixes that modify infrastructure files
- Tracks test count before/after a job — blocks if tests decrease

### Pre-Flight Flow

```
Clone repo → detect tech stack → scan for secrets → check dependencies
    │              │                    │                    │
    │              ▼                    ▼                    ▼
    │         inject into          block if found      warn on issues
    │         agent prompts
    ▼
Run regression gate → start tasks
```

## 10.6. Skills System (`factory/skills/`)

Reusable capabilities invoked at specific lifecycle points. Each skill is a class with `should_run()` (conditional) and `run()` (execution).

### Skill Phases

| Phase | When | Skills |
|---|---|---|
| **PRE_JOB** | Before any tasks start | Standards Bootstrap, Dependency Audit, Codebase Profile |
| **PER_TASK** | During task processing | Migration Chain, Scaffold, Debug/Bisect |
| **POST_JOB** | After all tasks complete | Doc Sync, Dead Code Sweep, PR Polish, Version Bump |
| **ON_DEMAND** | Triggered manually | Health Check, Cleanup, Rollback |

### Pre-Job Skills
- **Standards Bootstrap** — creates CONVENTIONS.md, STYLEGUIDE.md, CI workflow if missing. Detects project type (Python/React/fullstack) and copies the right templates.
- **Dependency Audit** — runs pip-audit (Python) and npm audit (Node) to flag vulnerabilities. Advisory only, doesn't block.
- **Codebase Profile** — spawns haiku agent to generate ARCHITECTURE.md and per-module CONTEXT.md. Only runs on cold-start (no existing ARCHITECTURE.md).

### Per-Task Skills
- **Migration Chain** — sequential pipeline: generate migration → update models → write backfill → verify. Triggered when `task_type == "migration"`. Replaces the normal red-green loop.
- **Scaffold** — generates boilerplate for `api_route`, `model`, `component`, `service` task types. Haiku agent reads existing patterns and creates stubs before the Developer starts.
- **Debug/Bisect** — triggers at round 3+ when Developer keeps failing. Spawns a sonnet agent to diagnose root cause systematically instead of "try harder". Writes diagnosis to feedback.md.

### Post-Job Skills
- **Doc Sync** — updates ARCHITECTURE.md, CONTEXT.md, CHANGELOG.md after all tasks merge. Haiku agent reads changed files and updates docs.
- **Dead Code Sweep** — runs ruff (Python) and eslint (TS) for unused imports/variables. Auto-fixes F401 (unused imports). Finds orphaned test files.
- **PR Polish** — analyzes commit history for bad messages, duplicates, excessive commits. Advisory report only (no history rewriting).
- **Version Bump** — reads conventional commit messages since the last tag, determines bump type (major/minor/patch), updates version in pyproject.toml or package.json, writes CHANGELOG.md entry, and creates a git tag. Does not push.

### On-Demand Skills
- **Health Check** — generates A-F health report from saved state. Same grading as post-job report but callable anytime.
- **Cleanup** — wraps existing orphan issue/PR/state cleanup into one callable unit.
- **Rollback** — reverts a task: closes PRs, deletes branch, reverts merge commit, resets task state to pending.

### Task Types

The Architect tags each task with a `type` field that determines execution strategy:

| Type | Strategy |
|---|---|
| `feature` (default) | Normal red-green loop |
| `migration` | Migration chain skill |
| `api_route`, `model`, `component`, `service` | Scaffold first, then red-green |
| `refactor` | Normal red-green loop |

## 11. Multi-Project Strategy

The dark-factory repo is the **mother ship**. Each project it builds gets its own repo.

![Multi-Project Strategy](diagrams/multi-project.png)

### How It Works

1. **You create a GitHub Issue** on dark-factory repo: "Build a weather API that returns forecasts by zip code"
2. **Architect reads the issue** — creates new private repo `weather-api`, sets up project structure (Dockerfile, CI/CD, README), creates GitHub Issues on the new repo for each task
3. **QA + Developer work on the new repo** — QA writes tests, Developer writes code, CI/CD runs on the new repo
4. **Dark-factory dashboard monitors ALL projects**

### Inspiration

Architecture inspired by [coleam00/your-claude-engineer](https://github.com/coleam00/your-claude-engineer) — a harness built on the Claude Agent SDK that uses sub-agents for project management, code implementation, and version control. Key ideas borrowed:

- Sub-agent architecture with an orchestrator coordinator
- External tool integration (GitHub, notifications)
- Markdown-defined agent behaviors (changeable without code)
- Multi-model support (cheap model for simple tasks, powerful model for coding)

## 12. Mission Control Dashboard

A real-time dashboard to monitor what every agent is doing.

![Mission Control Dashboard](diagrams/dashboard.png)

### Key Dashboard Features

| Feature | How it works |
|---|---|
| Agent status cards | Orchestrator POSTs agent state changes |
| Task progress | GitHub Issues API + orchestrator events |
| Live agent log | WebSocket stream from FastAPI |
| Red-green rounds | Orchestrator reports test results per round |
| Pipeline status | GitHub Actions API |
| Environment health | Health check endpoints on staging/prod |
| Deploy to prod | Triggers GitHub Actions workflow_dispatch |
| Job history | PostgreSQL event log |

## 13. Observability

### Overview

![Observability Stack](diagrams/observability.png)

### What We Monitor

**Factory Metrics** (the orchestrator itself):

| Metric | What it tells you |
|---|---|
| `factory_jobs_total` | Total jobs run |
| `factory_jobs_success` | Jobs that completed successfully |
| `factory_jobs_failed` | Jobs that failed (hit max rounds) |
| `factory_rounds_per_task` | How many red-green rounds per task (efficiency) |
| `factory_agent_duration_seconds` | How long each agent takes |
| `factory_tokens_used` | Token consumption per agent |
| `factory_tasks_per_job` | How many tasks the Architect creates |

**Service Metrics** (what the factory builds):

| Metric | What it tells you |
|---|---|
| `http_requests_total` | Request count by endpoint, method, status |
| `http_request_duration_seconds` | Latency (p50, p95, p99) |
| `http_errors_total` | Error rate |
| `db_query_duration_seconds` | Database performance |
| `app_uptime_seconds` | How long the service has been running |

**Infrastructure Metrics**:

| Metric | What it tells you |
|---|---|
| Container CPU / memory usage | Resource consumption |
| Docker container restarts | Stability |
| Health check status | Is it alive |

### Logging

Structured JSON logs from every service:

```json
{
  "timestamp": "2026-04-04T22:30:01Z",
  "level": "INFO",
  "service": "weather-api",
  "message": "Request completed",
  "method": "GET",
  "path": "/weather/90210",
  "status": 200,
  "duration_ms": 45,
  "request_id": "abc-123"
}
```

Factory agent logs:

```json
{
  "timestamp": "2026-04-04T22:30:01Z",
  "level": "INFO",
  "component": "factory",
  "agent": "qa-engineer",
  "job_id": "job-42",
  "task_id": 3,
  "round": 2,
  "message": "Running tests",
  "tests_passed": 8,
  "tests_failed": 4
}
```

Loki collects all logs. Grafana queries them. You can search across all services and factory runs in one place.

### Error Tracking — Sentry

Free tier: 5,000 errors/month, 1 user.

```python
# Every service gets this in main.py
import sentry_sdk
sentry_sdk.init(dsn="your-sentry-dsn", traces_sample_rate=0.1)
```

Sentry catches:
- Unhandled exceptions with full stack traces
- Context (which request, which user, which deployment)
- Groups duplicates automatically
- Alerts you on new errors

### Grafana Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  DARK FACTORY — Observability                        Grafana │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Factory Performance (last 24h)                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Jobs Run: 12 │ │ Success: 10  │ │ Avg Rounds/Task: 2.1 │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
│                                                              │
│  Agent Duration (avg)                                        │
│  Architect:    45s  ████░░░░░░                               │
│  QA Engineer:  2m   ████████░░                               │
│  Developer:    4m   ████████████████                         │
│                                                              │
│  Service Health                                              │
│  ┌──────────────────┐ ┌────────────────┐ ┌────────────────┐ │
│  │ weather-api      │ │ auth-service   │ │ client-portal  │ │
│  │ ✅ 99.9% uptime  │ │ ✅ 100% uptime │ │ ⚠️ 98.2%       │ │
│  │ p95: 52ms        │ │ p95: 23ms      │ │ p95: 180ms     │ │
│  │ 0 errors         │ │ 0 errors       │ │ 3 errors       │ │
│  └──────────────────┘ └────────────────┘ └────────────────┘ │
│                                                              │
│  Recent Errors (Sentry)                                      │
│  ⚠️ client-portal: TypeError in UserProfile.tsx (3 events)   │
│  ✅ No other errors in last 24h                               │
└─────────────────────────────────────────────────────────────┘
```

### Cost

| Tool | Cost |
|---|---|
| Prometheus | Free, open source |
| Grafana | Free, open source (self-hosted) |
| Loki | Free, open source |
| Sentry | Free tier (5K errors/mo) |
| **Total** | **$0** |

## 14. Notifications

Don't check the dashboard — let the factory come to you.

### Notification Channels

```
┌─────────────────────────────────────────────────────────────┐
│                     NOTIFICATIONS                            │
│                                                              │
│  SLACK (recommended)                                         │
│  ├── #dark-factory channel                                   │
│  ├── Job started: "Starting issue #42: Weather API"          │
│  ├── Task progress: "Task 3/7 complete (round 1)"           │
│  ├── Job done: "✅ weather-api v1.0.0 deployed to staging"  │
│  ├── Job failed: "❌ Issue #42 failed at task 5 (round 5)"  │
│  └── Prod deploy: "🚀 weather-api v1.0.0 → production"     │
│                                                              │
│  DESKTOP NOTIFICATIONS (macOS)                               │
│  ├── Uses osascript / terminal-notifier                      │
│  └── Pops up when job completes or fails                     │
│                                                              │
│  GITHUB NOTIFICATIONS (built-in)                             │
│  ├── PR opened → you get notified                            │
│  ├── PR merged → you get notified                            │
│  └── Issue closed → you get notified                         │
│                                                              │
│  EMAIL (via GitHub or Sentry)                                │
│  ├── GitHub sends email on PR activity                       │
│  └── Sentry sends email on new errors                        │
│                                                              │
│  GRAFANA ALERTS                                              │
│  ├── Service down → Slack + email alert                      │
│  ├── Error rate spike → Slack alert                          │
│  └── Factory failure rate > 30% → Slack alert                │
└─────────────────────────────────────────────────────────────┘
```

### Slack Integration (free)

Slack incoming webhook — free, no bot needed:

```python
# In the orchestrator
import requests

def notify(message):
    requests.post(SLACK_WEBHOOK_URL, json={"text": message})

# Usage
notify("✅ weather-api v1.0.0 deployed to staging")
notify("❌ Issue #42 failed at task 5 after 5 rounds")
```

### Desktop Notifications (macOS)

```python
import subprocess

def desktop_notify(title, message):
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "{title}"'
    ])

# Usage
desktop_notify("Dark Factory", "Job complete: weather-api deployed to staging")
```

### What Triggers Notifications

| Event | Slack | Desktop | GitHub |
|---|---|---|---|
| Job started | ✅ | | |
| Task completed | ✅ | | |
| Red-green round > 3 | ✅ | | |
| Job complete (success) | ✅ | ✅ | ✅ (PR) |
| Job failed (max rounds) | ✅ | ✅ | ✅ (issue comment) |
| Deployed to staging | ✅ | ✅ | |
| Deployed to production | ✅ | ✅ | |
| Service error (Sentry) | ✅ | | ✅ (email) |
| Service down | ✅ | ✅ | |

## 15. Environments

```
┌─────────────────────────────────────────────┐
│              Docker Compose                  │
│                                              │
│  ┌───────────────────────────────────────┐  │
│  │           STAGING                      │  │
│  │                                        │  │
│  │  ┌─────────┐ ┌──────┐ ┌───────────┐  │  │
│  │  │ Service │ │  DB  │ │ Dashboard │  │  │
│  │  │ :8001   │ │:5433 │ │ :3001     │  │  │
│  │  └─────────┘ └──────┘ └───────────┘  │  │
│  └───────────────────────────────────────┘  │
│                                              │
│  ┌───────────────────────────────────────┐  │
│  │           PRODUCTION                   │  │
│  │                                        │  │
│  │  ┌─────────┐ ┌──────┐ ┌───────────┐  │  │
│  │  │ Service │ │  DB  │ │ Dashboard │  │  │
│  │  │ :8000   │ │:5432 │ │ :3000     │  │  │
│  │  └─────────┘ └──────┘ └───────────┘  │  │
│  └───────────────────────────────────────┘  │
│                                              │
└─────────────────────────────────────────────┘

Phase 4 (future): Replace with k3d + ArgoCD
├── staging namespace
└── production namespace
```

## 16. CI/CD & Build Phases

```
PHASE 1 — Factory Core ✅ COMPLETE
├── Orchestrator (async, task batching, red-green cycle)
├── Agent prompts (planner.md, evaluator.md, generator.md)
├── GitHub Issues integration (sub-issues, PRs, auto-merge)
├── dark-factory CLI (start, run, retry, repos, create-issue)
├── Contracts approach (parallel test writing + scaffolding)
├── Per-task branches and PRs (like a real engineer)
├── Smart QA (direct test running, skip agent on pass)
├── Session state persistence for crash recovery
├── Security policy (command allowlisting)
├── Project templates (FastAPI scaffold)
├── CI/CD for dark-factory itself (GitHub Actions)
├── 42 unit tests passing
└── Deliverable: factory builds APIs from GitHub Issues

PHASE 2 — CI/CD Pipeline
├── Dockerfile for services
├── GitHub Actions workflow (test → build → push)
├── Docker Compose for staging + production
├── Auto-deploy to staging on merge
├── Manual deploy to production (GitHub button)
└── Deliverable: merge → auto-deploy to staging works

PHASE 3 — Mission Control Dashboard 🔄 IN PROGRESS
├── Status API (FastAPI + SQLite)
├── React dashboard
├── Live agent monitoring (WebSocket)
├── Agent status cards
├── Task progress view
├── Pipeline + environment status
├── Deploy to prod button
└── Deliverable: full visibility into factory operations

PHASE 4 — Kubernetes (Future)
├── k3d cluster setup
├── ArgoCD installation
├── Staging + production namespaces
├── Helm charts or K8s manifests
├── Auto-rollback on health check failure
└── Deliverable: GitOps deployment pipeline
```

### Pipeline Engine

The `orchestrator.py` is the current production path — a Python-defined pipeline with fixed stages (Architect → Developer → QA). A parallel **graph-based engine** lives in `factory/pipeline/` and is being built out so future pipelines (hotfix, docs-only, security audit) can compose cleanly without growing the orchestrator.

**Architecture:**

| Piece | Role |
|---|---|
| `factory/pipeline/schema.py` | Pydantic models for `Pipeline`, `Node`, `Edge`, `NodeResult`, `RetryPolicy` |
| `factory/pipeline/engine.py` | Walks the graph, evaluates `when` conditions on edges, handles retries, dispatches to handlers. Returns the last NodeResult for composition. |
| `factory/pipeline/handlers/` | Pluggable handler registry. Each handler is `async (node, ctx) -> NodeResult`. Today: `agent`, `shell`, `skill`, `subpipeline`, `parallel`, `loop`. |
| `pipelines/*.yaml` | Pipeline definitions. Each is a graph of nodes + edges; nodes reference handlers by name |

**Core design decisions:**

1. **Config over code** — pipelines are data, not Python. Adding a new pipeline = new YAML file; the engine never changes.
2. **Handler registry as the boundary** — `HANDLERS` dict in `factory/pipeline/handlers/__init__.py` maps name → function. YAML names handlers by string; handlers implement the work.
3. **Edge routing before retry escalation** — a failed node first tries outgoing edges for handling; only if no edge matches does `retry.on_exhausted` fire. This lets pipelines model "on failure, go to cleanup node" cleanly.
4. **Per-node retry with configurable exhaustion policy** — `abort` (raise), `continue` (pass through), `escalate` (for future human-gate).
5. **Composition handlers share context** — `subpipeline`, `parallel`, and `loop` all run child pipelines through the same `PipelineContext`. Children propagate their final NodeResult to the parent for edge routing. Loops tolerate child aborts by treating them as failed iterations.

**Phase plan:**

- **Phase 1:** engine + standalone pipeline execution (shipped).
- **Phase 2:** composition — `subpipeline`, `parallel`, `loop` (shipped).
- **Phase 3:** migrate DF's own job flow onto a pipeline YAML; delete the pipeline logic from `orchestrator.py`.

### GitHub Actions Workflows (for the dark-factory repo itself)

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | push / PR to `main` | Runs `ruff check`, `ruff format --check`, `pytest tests/` |
| `auto-version.yml` | push to `main` | Parses commits since last `v*` tag, bumps `__version__` + CHANGELOG, commits as `chore: bump version to X.Y.Z`. Skips its own bump commits via an `if:` guard to avoid loops. |
| `release.yml` | push to `main` | Reads `__version__`, no-ops if `vX.Y.Z` tag already exists, otherwise creates the tag and cuts a GitHub Release from the matching CHANGELOG section. Fires on the bump commit so the tag points at it directly. |

Two workflows kept separate so release logic (signing, artifact publishing, etc.) can grow independently of the bump logic. The bump script lives in `scripts/auto_version.py` (stateless Python, no async), distinct from `factory/skills/version_bump.py` (which is the POST_JOB skill that bumps *target* repos during DF jobs). Conventional commits drive the bump type: `feat:` → minor, `fix:`/other → patch, `!:` or `BREAKING CHANGE` → major.

## 17. Cost Breakdown

### Monthly Costs

```
┌────────────────────────────────────────────────────────┐
│                   MONTHLY COSTS                         │
├────────────────────────────┬───────────────────────────┤
│ Claude Code Max            │ $200.00 (already paying)  │
├────────────────────────────┼───────────────────────────┤
│ GitHub (free tier)         │ $0.00                     │
│ GitHub Actions (2000 min)  │ $0.00                     │
│ Supabase Postgres (free)   │ $0.00                     │
│ Docker                     │ $0.00                     │
│ Playwright                 │ $0.00                     │
│ Prometheus (metrics)       │ $0.00                     │
│ Grafana (dashboards)       │ $0.00                     │
│ Loki (logs)                │ $0.00                     │
│ Sentry (errors, free tier) │ $0.00                     │
│ ArgoCD                     │ $0.00                     │
│ k3d                        │ $0.00                     │
├────────────────────────────┼───────────────────────────┤
│ TOTAL                      │ $200.00/mo                │
│ (extra beyond Claude Max)  │ $0.00                     │
└────────────────────────────┴───────────────────────────┘
```

### If You Scale Later

| Addition | Cost |
|---|---|
| Cloud hosting (VPS for staging/prod) | $6-12/mo |
| Supabase Pro (if you exceed free tier) | $25/mo |
| Domain name | $1/mo |
| Claude API (if moving to 24/7 autonomous) | $20-100/mo |
| Sentry Team (if you exceed 5K errors/mo) | $26/mo |
| Grafana Cloud (if you don't want to self-host) | $0-29/mo |
| Linear (if you switch from GitHub Issues) | $0-10/mo |

## 18. End-to-End Example: Building a Weather API

A complete walkthrough of how you'd use the dark factory.

### Step 1: You Write the Spec (GitHub Issue on dark-factory repo)

```
Title: Build a weather API service

Description:
Build a REST API that returns weather forecasts by zip code.

Requirements:
- GET /weather/{zip_code} returns current temperature, conditions, description
- GET /weather/{zip_code}/forecast returns 5-day forecast
- GET /health returns service status
- Use OpenWeatherMap free API as data source
- Rate limiting: 60 requests/minute per IP
- Cache responses for 10 minutes (Redis or in-memory)
- Return proper error codes (400 for invalid zip, 502 for upstream failure)
```

### Step 2: Orchestrator Picks It Up

```bash
$ claude-factory start --issue 7

[Factory] Fetching issue #7 from dark-factory repo...
[Factory] Spawning Architect...
```

### Step 3: Architect Creates the Project

```
[Architect] Reading issue #7: "Build a weather API service"
[Architect] Creating private repo: weather-api
[Architect] Setting up project structure:

weather-api/
├── CLAUDE.md
├── Makefile                    ← coding standards enforced
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── setup.py
├── src/
│   └── weather_api/
│       ├── __init__.py
│       ├── main.py
│       ├── routes.py
│       ├── weather_client.py
│       └── config.py
├── tests/
│   ├── __init__.py
│   ├── test_routes.py
│   ├── test_weather_client.py
│   └── conftest.py
└── .github/
    └── workflows/
        └── ci.yml

[Architect] Creating GitHub Issues on weather-api repo:

  Issue #1: "Project setup — Makefile, Dockerfile, CI"
            depends_on: none
            
  Issue #2: "GET /health endpoint"
            depends_on: #1
            Acceptance: returns {"status": "healthy"}, 200 OK
            
  Issue #3: "OpenWeatherMap client wrapper"
            depends_on: #1
            Acceptance: fetches weather by zip, handles errors,
            returns typed response
            
  Issue #4: "GET /weather/{zip_code} endpoint"
            depends_on: #2, #3
            Acceptance: returns temp, conditions, description;
            400 for invalid zip; 502 for upstream failure
            
  Issue #5: "GET /weather/{zip_code}/forecast endpoint"
            depends_on: #4
            Acceptance: returns 5-day forecast array
            
  Issue #6: "Rate limiting — 60 req/min per IP"
            depends_on: #4
            Acceptance: returns 429 after 60 requests
            
  Issue #7: "Response caching — 10 min TTL"
            depends_on: #4
            Acceptance: second identical request within 10 min
            returns cached response (verify via response time)

[Architect] Writing tasks.json with dependency order...
[Architect] Done. 7 tasks created.
```

### Step 4: Task Ordering (Dependencies)

GitHub Issues doesn't have native dependency ordering. The **orchestrator enforces it** via `tasks.json`:

```json
{
  "project": "weather-api",
  "tasks": [
    {"id": 1, "title": "Project setup", "depends_on": [], "status": "pending"},
    {"id": 2, "title": "Health endpoint", "depends_on": [1], "status": "pending"},
    {"id": 3, "title": "Weather client", "depends_on": [1], "status": "pending"},
    {"id": 4, "title": "Weather endpoint", "depends_on": [2, 3], "status": "pending"},
    {"id": 5, "title": "Forecast endpoint", "depends_on": [4], "status": "pending"},
    {"id": 6, "title": "Rate limiting", "depends_on": [4], "status": "pending"},
    {"id": 7, "title": "Caching", "depends_on": [4], "status": "pending"}
  ]
}
```

The orchestrator reads `depends_on` and only starts a task when its dependencies are complete:

- **Batch 1**: Task 1 (setup) — no dependencies
- **Batch 2**: Task 2 (health) + Task 3 (client) — both depend on 1, run in parallel
- **Batch 3**: Task 4 (weather endpoint) — depends on 2 + 3
- **Batch 4**: Task 5 (forecast) + Task 6 (rate limit) + Task 7 (caching) — all depend on 4, run in parallel

### Step 5: QA → Developer Loop (per task)

```
[Factory] Starting Task #2: "GET /health endpoint"

[QA Engineer] Reading acceptance criteria...
[QA Engineer] Writing tests/test_health.py:

  def test_health_returns_200(client):
      response = client.get("/health")
      assert response.status_code == 200

  def test_health_returns_status(client):
      response = client.get("/health")
      assert response.json()["status"] == "healthy"

[QA Engineer] Committed tests. All RED (2 failing).

[Developer] Reading spec + failing tests...
[Developer] Writing src/weather_api/routes.py:

  @app.get("/health")
  def health():
      return {"status": "healthy"}

[Developer] Committed code.

[QA Engineer] Running tests... 2/2 GREEN ✅
[QA Engineer] Code review: clean, follows standards. APPROVED.

[Factory] Task #2 complete. Updating GitHub Issue.
[Factory] Starting Task #3 (parallel eligible)...
```

### Step 6: Auto-merge and Deploy

```
[Factory] All 7 tasks complete.
[Factory] Opening PR on weather-api: "feat: complete weather API"
[Factory] All tests passing. Auto-merging.

[GitHub Actions] Tests passed. Building Docker image.
[GitHub Actions] Pushed to ghcr.io/sungcheng/weather-api:v1.0.0

[Docker Compose] Deploying to staging...
[Health Check] staging:8001/health → 200 OK ✅

[Notification] "weather-api v1.0.0 deployed to staging"
```

## 19. Distributed Architecture (Phase 6)

The current Dark Factory runs locally on a single machine. Phase 6 transforms it into a multi-engineer platform where the factory runs as a centralized service.

### Vision

```
Engineers write specs → GitHub Issues → Factory Service builds it → PRs ready for review
```

Engineers stop writing code. They write specs. The factory handles everything else.

### System Architecture

![Distributed Architecture](diagrams/distributed-flow.png)

### Components

#### Factory API (FastAPI)
The central entry point. Receives GitHub webhooks when issues are created or labeled. Exposes REST endpoints for job management, status, and manual triggers.

- `POST /api/v1/jobs` — submit a job (repo + issue number)
- `GET /api/v1/jobs` — list all jobs across all engineers
- `GET /api/v1/jobs/{id}` — job detail with tasks and subtasks
- `POST /api/v1/webhooks/github` — GitHub webhook receiver
- Auth: API keys per engineer, GitHub webhook secret

#### Job Scheduler
Manages the job queue with priority and concurrency control.

- Priority queue (urgent bugs > features > tech debt)
- Concurrency limit per repo (prevent conflicting PRs)
- Fair scheduling across engineers (round-robin within priority)
- Dead letter queue for permanently failed jobs
- Backed by Redis sorted sets or PostgreSQL `FOR UPDATE SKIP LOCKED`

#### Worker Pool
Stateless orchestrator instances that pull jobs from the queue. Each worker runs the existing `run_job()` logic but stores state in PostgreSQL instead of local files.

- Horizontally scalable — add workers as load increases
- Stateless — any worker can resume any job (state in DB)
- Health-checked — auto-restart on crash
- Resource-limited — max concurrent agents per worker
- Runs as Kubernetes pods or Docker Compose services

#### Message Broker (Redis / NATS)
All events flow through the broker instead of direct HTTP calls.

- Workers publish events (agent_spawned, task_completed, round_result)
- Dashboard subscribes for real-time updates (WebSocket fan-out)
- PostgreSQL consumer persists events durably
- Enables replay — new dashboard instances catch up from DB
- Decouples workers from dashboard (dashboard down ≠ factory stuck)

#### PostgreSQL
Replaces SQLite and local state files.

Tables:
- `jobs` — job metadata, status, owner
- `tasks` — task + subtask records with status
- `events` — all lifecycle events (append-only)
- `state` — working directory paths, branch names, PR numbers
- `engineers` — API keys, preferences, quotas

#### Object Store (S3 / MinIO)
Stores artifacts that don't belong in the DB.

- Agent stdout/stderr logs (can be large)
- Test output (for debugging failed rounds)
- Working directory snapshots (for crash recovery)

#### Mission Control Dashboard
Same React UI, but deployed centrally. Shows all jobs across all engineers.

- Real-time updates via WebSocket (subscribed to broker)
- Filter by engineer, repo, status
- Global view: how many jobs running, queue depth, agent utilization
- Per-engineer view: my jobs, my repos, my PRs

### What Changes from Current Architecture

| Component | Current (Local) | Distributed |
|---|---|---|
| Entry point | CLI (`dark-factory start`) | API + GitHub webhooks |
| State storage | `~/.dark-factory/state/*.json` | PostgreSQL `jobs` + `state` tables |
| Event delivery | HTTP POST to localhost | Message broker (Redis/NATS) |
| Dashboard DB | SQLite file | PostgreSQL |
| Agent execution | Local `claude -p` subprocess | Same, but on worker machines |
| Concurrency | One job at a time | Multiple workers, queue-based |
| Auth | GitHub PAT in `.env` | Per-engineer API keys + PATs |
| Working dirs | `/tmp/dark-factory-*` | Persistent volumes or ephemeral with S3 backup |

### Migration Path

The migration is incremental — each step works standalone:

**Step 1: PostgreSQL** — Swap SQLite → Postgres. Update `factory/dashboard/db.py`. Deploy Postgres (Docker Compose or managed). Everything else stays the same.

**Step 2: API Server** — Add webhook receiver and job submission endpoints. The CLI becomes a thin client that calls the API instead of running `run_job()` directly.

**Step 3: Message Broker** — Replace direct HTTP event posting with broker publish. Dashboard subscribes via WebSocket. Add event persistence consumer.

**Step 4: Worker Pool** — Extract orchestrator into a worker process that pulls from the queue. Deploy multiple workers. State moves fully to Postgres.

**Step 5: Multi-tenant** — Add engineer accounts, API keys, quotas, and per-engineer dashboard views. Rate limiting per engineer/repo.

**Step 6: Kubernetes** — Deploy on k8s with autoscaling workers, managed Postgres, and Redis cluster.

### New Repo Structure

```
dark-factory/
├── factory/                    # Core (shared by CLI + workers)
│   ├── orchestrator.py
│   ├── agents/
│   ├── guardrails.py
│   └── prompts/
├── api/                        # NEW: Factory API server
│   ├── app.py                  # FastAPI app
│   ├── routers/
│   │   ├── jobs.py             # Job CRUD
│   │   ├── webhooks.py         # GitHub webhook receiver
│   │   └── engineers.py        # Auth + quotas
│   ├── scheduler.py            # Job queue management
│   └── worker.py               # Worker process (pulls from queue)
├── broker/                     # NEW: Event broker integration
│   ├── publisher.py            # Replaces EventEmitter HTTP calls
│   ├── consumer.py             # Persists events to DB
│   └── websocket.py            # Fan-out to dashboard clients
├── dashboard/                  # Existing, updated for multi-tenant
│   ├── api/                    # Dashboard read API
│   └── frontend/               # React UI
├── infra/                      # NEW: Deployment configs
│   ├── docker-compose.yml      # Local multi-service dev
│   ├── docker-compose.prod.yml
│   ├── k8s/                    # Kubernetes manifests
│   └── terraform/              # Cloud infrastructure
└── cli/                        # Thin CLI client
    └── main.py                 # Calls Factory API
```

### Cost Model (Multi-Engineer)

| Engineers | Concurrent Jobs | Workers | Estimated Monthly Cost |
|---|---|---|---|
| 1-3 | 1-2 | 1 | ~$50 (Postgres + VM) |
| 5-10 | 3-5 | 3 | ~$200 |
| 10-25 | 5-10 | 5 | ~$500 |
| 25+ | 10+ | 10+ | ~$1000+ |

API token costs (Claude) are separate and scale with job volume, not infra.

## 20. Verification Plan

### Phase 1 Test
1. Create a GitHub Issue: "Build a hello world API with GET /health endpoint"
2. Run `claude-factory start --issue <number>`
3. Verify: Architect creates tasks, QA writes tests, Developer writes code
4. Verify: Tests pass, PR opened, auto-merged

### Phase 2 Test
1. Merge triggers GitHub Actions
2. Docker image builds successfully
3. Docker Compose spins up staging
4. Health check passes on staging
5. Manual trigger deploys to production

### Phase 3 Test
1. Dashboard shows live agent activity during a factory run
2. WebSocket streams events in real time
3. Task progress updates as agents complete work
4. Deploy button triggers production deployment
