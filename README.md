# Dark Factory

Autonomous AI coding pipeline — you write the spec, AI builds, tests, and deploys it.

## How It Works

1. You create a GitHub Issue with requirements
2. **Architect** (opus) reads the issue, breaks it into tasks with dependencies
3. **QA Engineer** writes interface contracts, then failing tests (RED)
4. **Developer** (opus) scaffolds from contracts, then makes tests pass (GREEN)
5. Tests run directly — if they pass, instant approve. If they fail, QA writes feedback
6. Developer retries (max 5 rounds per task)
7. Each completed task gets its own PR, merged to main immediately
8. Failed tasks get draft PRs + needs-human issues for retry

No agent grades its own work. The Developer cannot touch test files. The QA Engineer cannot touch source files.

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

### Start a job (single issue)

```bash
dark-factory start --repo weather-api --issue 1
```

### Run all open issues in a repo

```bash
dark-factory run --repo weather-api
dark-factory run --repo weather-api --parallel  # independent issues in parallel
```

### Create an issue

```bash
dark-factory create-issue --repo weather-api --title "Add caching" --editor
dark-factory create-issue --repo weather-api --title "Add caching" -b "Cache for 5 min" -l enhancement
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

Default models: opus for Architect + Developer, sonnet for QA, haiku for contracts + regression.

### Verbose mode

```bash
dark-factory start --repo weather-api --issue 1 -v
```

### Makefile shortcuts

```bash
make help                                    # show all commands
make test                                    # run tests
make test-cov                                # tests + coverage
make check                                   # lint + types
make format                                  # auto-format
make repos                                   # list GitHub repos
make start repo=weather-api issue=1          # single job
make run repo=weather-api                    # all open issues
make retry repo=weather-api issue=1          # retry failed tasks
make create-issue repo=weather-api title="X" # create issue (opens editor)
make clean-state                             # clear saved state
```

## Task Flow

Each task follows this optimized pipeline:

```
1. QA writes contracts.md (haiku — fast)
   Defines function signatures, API routes, types

2. QA writes tests + Developer scaffolds (parallel)
   Both run simultaneously via asyncio.gather

3. Red-Green loop (max 5 rounds):
   Developer codes (opus) → run make test + make check directly
   ├── PASS → instant approve, no QA agent needed
   └── FAIL → spawn QA for detailed feedback → Developer retries

4. Push → open PR → merge to main
   Each task gets its own branch and PR
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

When a task fails after 5 red-green rounds:

1. Opens a **draft PR** with partial work
2. Creates a **needs-human issue** with failure details and last QA feedback
3. Continues with remaining tasks
4. You **comment** on the issue with guidance
5. Run `dark-factory retry` — your comment is injected into the Developer's prompt

Jobs **auto-resume** if they crash. State is saved to `~/.dark-factory/state/`.

## Project Structure

```
dark-factory/
├── factory/
│   ├── cli.py              # CLI — start, run, retry, repos, create-issue, version
│   ├── orchestrator.py     # Main loop — task batching, red-green cycle
│   ├── github_client.py    # GitHub API — issues, PRs, repos
│   ├── state.py            # Session state persistence for resume
│   ├── security.py         # Command allowlisting for agents
│   ├── agents/
│   │   ├── base.py         # Agent runner (async subprocess spawning)
│   │   ├── planner.py      # Architect agent
│   │   ├── evaluator.py    # QA Engineer (contracts, red, regression, review)
│   │   └── generator.py    # Developer agent (scaffold + implementation)
│   └── prompts/
│       ├── planner.md      # Architect rules & personality
│       ├── evaluator.md    # QA Engineer rules & personality
│       └── generator.md    # Developer rules & personality
├── tests/                  # Unit tests (42 passing)
├── DESIGN.md               # Full design document
└── diagrams/               # Architecture diagrams
```

## Performance Optimizations

| Optimization | How |
|---|---|
| **Contracts first** | QA writes interface contracts before tests — Developer scaffolds in parallel |
| **Smart QA review** | Run `make test + make check` directly — skip QA agent if tests pass |
| **Skip empty regression** | No regression gate when repo has no tests yet |
| **Haiku for simple tasks** | Contracts and regression use haiku (10x faster than sonnet) |
| **Parallel task batches** | Independent tasks run simultaneously via asyncio.gather |

## Security

Agents run with a security policy written to the target repo's CLAUDE.md:
- **Allowed**: python, make, git, pytest, ruff, mypy, docker
- **Blocked**: sudo, ssh, curl, wget, shutdown
- **Rules**: no arbitrary network requests, no privilege escalation, no system file deletion

## Hard Rules

| Rule | Why |
|---|---|
| Developer CANNOT edit test files | Prevents weakening tests to pass |
| QA CANNOT edit source files | Clean separation of concerns |
| Each agent gets fresh context | No memory bleed between agents |
| Max 5 red-green rounds per task | Prevents infinite loops |
| Agents communicate through files | Artifacts survive context resets |
| Regression gate before new work | Existing tests must pass first |

## Roadmap

- **Phase 1** — Factory core (orchestrator, agents, CLI) ✅
- **Phase 2** — CI/CD pipeline (Dockerfile, GitHub Actions, Docker Compose)
- **Phase 3** — Mission Control dashboard (real-time monitoring) 🔄
- **Phase 4** — Kubernetes (k3d + ArgoCD)

See [DESIGN.md](DESIGN.md) for the full architecture.
