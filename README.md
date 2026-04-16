# Dark Factory

Autonomous AI coding pipeline — you write the spec, AI builds, tests, and deploys it.

## How It Works

1. You create a GitHub Issue with requirements
2. **Pre-job skills** run: standards bootstrap, dependency audit, codebase profiling
3. **Architect** (opus) reads the issue, breaks it into typed tasks with dependencies
4. **Developer** writes code + tests, makes them pass (GREEN)
5. **QA Engineer** reviews test quality on medium/complex tasks (simple tasks skip QA)
6. Developer retries on failure (max 5 rounds — debug/bisect triggers at round 3+)
7. Migration tasks use a sequential chain: generate → models → backfill → verify
8. Each completed task gets its own PR, merged to main immediately
9. **Post-job skills** run: doc sync, dead code sweep, PR polish, version bump
10. **QA Lead** (opus) does a holistic review of the full implementation
11. Failed tasks get draft PRs + needs-human issues for retry

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- Claude Max subscription (agents run as `claude -p` subprocesses)
- GitHub account with a [fine-grained PAT](https://github.com/settings/tokens?type=beta) (repo permissions)

## Setup

```bash
# Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repo
git clone https://github.com/sungcheng/dark-factory.git
cd dark-factory

# Install dependencies
uv sync --all-extras

# Configure environment
cp .env.example .env
# Edit .env with your GitHub token and username
```

Your `.env` should look like:

```
GITHUB_TOKEN=ghp_your-real-token
GITHUB_OWNER=sungcheng
```

## Usage

### Create a new project

```bash
dark-factory create-project weather-api                    # bare repo (private)
dark-factory create-project weather-api --public           # public repo
dark-factory create-project weather-api -t fastapi         # with FastAPI template
dark-factory create-project weather-app -t fullstack       # FastAPI + React
dark-factory create-project infra -t terraform             # with Terraform template
dark-factory create-project weather-api -d "Weather API"   # with description
```

Creates a GitHub repo with CLAUDE.md, CI/CD workflow, README, and **main branch protection** (requires PRs, blocks force pushes, enforces linear history). Without `--template`, the Architect scaffolds the project based on the first issue. Available templates: `fastapi`, `fullstack`, `terraform`.

### Create an issue

```bash
dark-factory create-issue --repo weather-api --title "Build weather API" --editor
dark-factory create-issue --repo weather-api --title "Add caching" -b "Cache for 5 min" -l enhancement
```

### Start a job (single issue)

```bash
dark-factory start --repo weather-api --issue 1
```

### Run all open issues in a repo

```bash
dark-factory run --repo weather-api                # parallel by default
dark-factory run --repo weather-api --sequential   # one issue at a time
```

### Retry failed tasks

When a task fails after 5 rounds, the factory creates a `needs-human` issue on GitHub. Comment on it with your guidance, then retry:

```bash
dark-factory retry --repo weather-api --issue 1
```

Your comment gets injected into the Developer's prompt for the retry.

### List your repos

```bash
dark-factory repos
```

Shows all repos grouped by private/public, with language and open issue count.

### Model selection

Override the model for all agents:

```bash
dark-factory start --repo weather-api --issue 1 --model opus
```

Default models: opus for Architect + Staff Engineer, sonnet for Developer + QA, haiku for regression. The Architect tags each task with complexity (simple/medium/complex) which auto-selects the Developer model (haiku/sonnet/opus).

### Verbose mode

```bash
dark-factory start --repo weather-api --issue 1 -v
```

### Makefile shortcuts

```bash
make help                                    # show all commands
make test                                    # run tests (excludes slow/frontend)
make test-all                                # run all tests including frontend
make test-cov                                # tests + coverage
make check                                   # lint + types
make format                                  # auto-format
make repos                                   # list GitHub repos
make start repo=weather-api issue=1          # single job
make run repo=weather-api                    # all open issues (parallel)
make retry repo=weather-api issue=1          # retry failed tasks
make create-project name=weather-api          # create new project repo
make create-issue repo=weather-api title="X" # create issue (opens editor)
make cleanup repo=weather-app                # clean stale issues, state, temp dirs
make cleanup-dry repo=weather-app            # preview cleanup without doing it
make dashboard                               # run dashboard server
make dashboard-dev                           # run dashboard with hot reload
make dashboard-stop                          # stop background dashboard
make clean-state                             # clear saved state
```

## Task Flow

Each task follows this optimized pipeline:

```
1. QA writes contracts + tests, Developer scaffolds (parallel)
   Single QA agent handles both contracts.md and failing tests
   Developer reads contracts and scaffolds stubs simultaneously

2. Red-Green loop (max 5 rounds):
   Developer codes (model selected by task complexity)
   ├── PASS → instant approve, no QA agent needed
   ├── OBVIOUS FAIL → smart analysis writes targeted feedback (no QA spawn)
   └── COMPLEX FAIL → spawn QA for detailed feedback → Developer retries

3. Push → open PR → merge to main
   Independent tasks run in parallel via git worktrees

4. Staff Engineer review (opus)
   Reads full codebase against issue, makes targeted improvements
   Auto-reverts if changes break tests
```

## Per-Task PRs

Each task creates its own branch, PR, and merge — like a real engineer:

```
factory/issue-1/task-1  →  PR #2  →  merge to main
factory/issue-1/task-2  →  PR #3  →  merge to main
factory/issue-1/task-3  →  PR #4  →  merge to main
```

Each task starts from the latest main, so it always has the previous task's code.

## Failure Recovery

When a task fails after 5 red-green rounds, **or** when a parallel-worktree branch cannot rebase cleanly onto main after a sibling task merged first:

1. Opens a **draft PR** with partial work (commits preserved — no silent drop)
2. Creates a **needs-human issue** with failure details and last QA feedback (or merge-conflict diagnostics)
3. Continues with remaining tasks
4. You **comment** on the issue with guidance
5. Run `dark-factory retry` — your comment is injected into the Developer's prompt

Jobs **auto-resume** if they crash. State is saved to `~/.dark-factory/state/`.

## Project Structure

```
dark-factory/
├── factory/
│   ├── __init__.py         # Version (single source of truth)
│   ├── cli.py              # CLI — start, run, retry, repos, create-issue, version
│   ├── orchestrator.py     # Main loop — task batching, red-green cycle
│   ├── github_client.py    # GitHub API — issues, PRs, repos
│   ├── state.py            # Session state persistence for resume
│   ├── security.py         # Command allowlisting for agents
│   ├── guardrails.py       # Pre-flight guardrails (tech stack, secrets, deps, scope)
│   ├── agents/
│   │   ├── base.py         # Agent runner (async subprocess spawning)
│   │   ├── planner.py      # Architect agent
│   │   ├── evaluator.py    # QA Engineer (contracts, red, regression, review)
│   │   └── generator.py    # Developer + Staff Engineer agents
│   ├── project.py          # create-project command (repo + scaffold + CI)
│   ├── templates/
│   │   ├── fastapi/        # FastAPI API scaffold
│   │   ├── fullstack/      # FastAPI + React scaffold
│   │   └── terraform/      # Terraform IaC scaffold
│   └── prompts/
│       ├── _principles.md  # Shared Karpathy-derived principles (prepended to every agent)
│       ├── planner.md      # Architect rules & personality
│       ├── evaluator.md    # QA Engineer rules & personality
│       └── generator.md    # Developer rules & personality
├── tests/                  # Unit tests (408 passing)
├── dashboard/
│   └── frontend/           # React + TypeScript + Tailwind dashboard
├── DESIGN.md               # Full design document
├── CHANGELOG.md            # Version history
└── diagrams/               # Architecture diagrams
```

## Mission Control Dashboard

The dashboard auto-starts when you run the factory. View it at http://localhost:8420/docs (API) or http://localhost:5173 (React UI).

```bash
# API server (auto-starts with factory, or run manually)
make dashboard              # production mode
make dashboard-dev          # with hot reload

# React frontend
cd dashboard/frontend
npm install                 # first time only
npm run dev                 # http://localhost:5173

# Stop background dashboard
make dashboard-stop
```

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/events` | POST | Submit lifecycle events |
| `/api/v1/jobs` | GET | List all jobs |
| `/api/v1/jobs/{id}` | GET | Job detail with tasks |
| `/api/v1/jobs/{id}/log` | GET | Chronological event log |
| `/docs` | GET | Swagger UI |

The orchestrator emits events automatically when `DASHBOARD_URL` is set (defaults to `http://localhost:8420`).

## Performance Optimizations

| Optimization | How |
|---|---|
| **Combined contracts+tests** | Single QA agent writes contracts AND tests (saves one agent spawn per task) |
| **Git worktree parallelism** | Independent tasks/subtasks run in parallel via `git worktree` — true concurrent development |
| **Adaptive model selection** | Architect tags task complexity; simple→haiku, medium→sonnet, complex→opus |
| **Smart failure analysis** | Analyzes test output (import/syntax/type errors) and writes targeted feedback — skips QA review agent for obvious fixes |
| **Staff Engineer review** | After all tasks merge, opus reads full codebase against issue requirements and makes targeted improvements |
| **Smart QA review** | Run `make test + make check` directly — skip QA agent if tests pass |
| **Auto-fix test lint** | Run `ruff fix + format` on QA test files before `make check` |
| **Self-healing regression** | If regression gate fails, spawn Developer to fix before giving up |
| **Post-merge validation** | After all tasks merge, run full check on main — self-heal if needed |
| **Auto npm install** | Detect `package.json` in frontend dirs and install deps automatically |
| **Skip empty regression** | No regression gate when repo has no tests yet |
| **Haiku for simple tasks** | Contracts and regression use haiku (10x faster than sonnet) |
| **Parallel task batches** | Independent tasks run simultaneously via git worktrees |

## Guardrails

Pre-flight and runtime checks that protect production repos (`factory/guardrails.py`):

| Guardrail | What it does |
|---|---|
| **Tech stack detection** | Scans for `pyproject.toml`, `package.json`, `go.mod`, etc. Injects detected stack into all agent prompts. Blocks framework migrations. |
| **Secret scanning** | Pre-flight + post-merge scan for hardcoded API keys, tokens, passwords, private keys, committed `.env` files. Blocks job if secrets found. |
| **File boundary enforcement** | Feature tasks cannot modify config files, Makefile, Dockerfile, CI workflows. Only infra tasks get relaxed boundaries. |
| **Dependency guardrails** | Detects competing packages (e.g., requests + httpx). Tells agents what's already installed. Warns on duplicates. |
| **Regression scope guard** | Blocks regression fixes that touch >5 files or modify infra. Verifies test count doesn't decrease after a job. |

All guardrails run automatically — no configuration needed.

## Security

Agents run with a security policy written to the target repo's CLAUDE.md:
- **Allowed**: python, make, git, pytest, ruff, mypy, docker
- **Blocked**: sudo, ssh, curl, wget, shutdown
- **Rules**: no arbitrary network requests, no privilege escalation, no system file deletion, no hardcoded secrets, no stack migrations

## Hard Rules

| Rule | Why |
|---|---|
| Developer CANNOT edit test files | Prevents weakening tests to pass |
| QA CANNOT edit source files | Clean separation of concerns |
| Each agent gets fresh context | No memory bleed between agents |
| Max 5 red-green rounds per task | Progressive escalation, then auto-retry on re-run |
| Agents communicate through files | Artifacts survive context resets |
| Regression gate before new work | Existing tests must pass first |
| Never migrate tech stack | Agents must extend, not replace |
| No hardcoded secrets | Env vars only, scanned pre and post |
| Developer reads existing code first | Extend, don't duplicate |

## Pipeline Engine

Alongside the legacy `orchestrator.py`, Dark Factory has a YAML-defined graph execution engine. Pipelines are plain YAML files in `pipelines/`; the engine walks nodes through edges and dispatches each node to a handler in `factory/pipeline/handlers/`.

Inspired by StrongDM's dark-factory approach — pipelines expressed as graphs, walked by a deterministic engine, with coding agents as pluggable handlers.

```bash
dark-factory run-pipeline pipelines/demo.yaml
dark-factory run-pipeline pipelines/compose_demo.yaml
```

A pipeline file looks like:

```yaml
name: demo
start: check_git
nodes:
  - id: check_git
    handler: shell
    params: { command: git --version }
  - id: report_ok
    handler: shell
    params: { command: echo "ok" }
edges:
  - from: check_git
    to: report_ok
    when: status == "success"
```

Handlers:
- `agent` — spawn a Claude Code subprocess (Architect, Developer, QA, Arbiter)
- `shell` — run a shell command
- `skill` — run a registered factory skill
- `subpipeline` — invoke another pipeline YAML as one node
- `parallel` — fan out N sub-pipelines concurrently (`wait_for: all|any`)
- `loop` — repeat a body pipeline until `exit_when` matches or `max_iterations` hits
- `df_job` — Phase 3 bridge; wraps the legacy `run_job` in a single node (kept around for comparison testing)
- Phase 4 stage handlers: `job_setup`, `clone_repo`, `preflight`, `pre_job_skills`, `regression_gate`, `architect`, `create_sub_issues`, `process_batches`, `post_merge_validation`, `qa_lead_review`, `post_job_skills`

### Running a DF job through the graph engine

```bash
dark-factory start --repo akkio5 --issue 1 --engine graph
```

`--engine graph` routes through `pipelines/df_job.yaml`, which is now a multi-stage graph: each stage of what `run_job` used to do monolithically is its own node. Stages share state via `JobRuntime` stored in the PipelineContext. To build variants (hotfix that skips `regression_gate`, docs-only that skips `qa_lead_review`), copy the YAML and remove nodes.

Phase 5 flips the default to graph, soaks on real jobs, then deletes the pipeline logic from `orchestrator.py`.

Composition example (Phase 2):

```yaml
- id: red_green
  handler: loop
  params:
    body: pipelines/red_green_body.yaml
    max_iterations: 5
    exit_when: status == "approved"
```

Adding a handler = one file + one registry entry. Adding a pipeline = one YAML file; no Python changes. Phase 3 will migrate DF's full job flow onto a pipeline YAML and retire the legacy orchestrator pipeline logic.

## Release Flow

Dark Factory auto-releases itself when material changes land on `main`:

Two workflows split the work cleanly:

1. **`auto-version.yml`** — on push to main, reads commits since the last `vX.Y.Z` tag, picks a bump (`feat:`→minor, `fix:`/others→patch, `!:`/`BREAKING`→major), updates `factory/__init__.py` + `CHANGELOG.md`, and commits as `chore: bump version to X.Y.Z`. Skips its own bump commits to avoid loops.
2. **`release.yml`** — on push to main, reads `__version__`. If the tag already exists, no-op. Otherwise creates the tag (pointing at the bump commit) and cuts a GitHub Release from the CHANGELOG section.

No manual bumping. To force a specific bump, prefix your commit with the conventional-commit keyword (e.g., `feat: add streaming endpoint` → minor).

## Subtasks

Tasks can optionally contain subtasks for finer-grained parallelism:

```json
{
  "id": "task-1",
  "title": "Backend core",
  "subtasks": [
    {"id": "task-1a", "title": "Models", "depends_on": []},
    {"id": "task-1b", "title": "Config", "depends_on": []},
    {"id": "task-1c", "title": "DB layer", "depends_on": ["task-1a"]}
  ]
}
```

- Subtasks share a single branch and PR but each gets its own red-green cycle and commit
- Independent subtasks within a parent are batched by dependency order
- The Architect decides when to use subtasks vs flat tasks
- Backward compatible — tasks without subtasks work as before

## Roadmap

- **Phase 1** — Factory core (orchestrator, agents, CLI) ✅
- **Phase 2** — CI/CD for dark-factory (GitHub Actions — lint + tests) ✅
- **Phase 3** — Mission Control dashboard (Status API + React frontend) ✅
- **Phase 4** — Deployable projects (Docker Compose staging/prod) ✅
- **Phase 5** — Subtasks, guardrails, smart skip, time estimates ✅
- **Phase 6** — Distributed platform (API service, worker pool, message broker, PostgreSQL, multi-engineer)
- **Phase 7** — Kubernetes (k3d + ArgoCD + autoscaling workers)

See [DESIGN.md](DESIGN.md) for the full architecture.
