# Dark Factory — Full Design Document

## Context

Build an autonomous AI coding pipeline ("dark factory") where AI agents handle the full software development lifecycle — from spec to deployment — with no human code review. The system uses a TDD Red-Green approach with separated agents to ensure quality without human intervention.

---

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

---

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

## 3. Architecture Overview

![Architecture Overview](diagrams/architecture.png)

---

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
| Max 5 red-green rounds | Prevents infinite loops, escalates to human |

---

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

---

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

---

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
│   │   ├── planner.md                 # Architect personality + rules
│   │   ├── evaluator.md               # QA Engineer personality + rules
│   │   └── generator.md               # Developer personality + rules
│   └── templates/
│       ├── __init__.py                # Template engine (apply_template)
│       └── fastapi/                   # FastAPI project scaffold
│
├── tests/                             # Unit tests (42 passing)
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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

## 19. Verification Plan

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
