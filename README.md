# Dark Factory

Autonomous AI coding pipeline — you write the spec, AI builds, tests, and deploys it.

## How It Works

1. You create a GitHub Issue with requirements
2. **Architect** agent reads the issue, breaks it into tasks
3. **QA Engineer** agent writes failing tests (RED)
4. **Developer** agent writes code to make tests pass (GREEN)
5. QA reviews — if tests fail, Developer tries again (max 5 rounds)
6. PR opened and auto-merged

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

### Start a job

```bash
# The target repo must exist on GitHub with a main branch
claude-factory start --repo weather-api --issue 1
```

This will:
1. Fetch issue #1 from `sungcheng/weather-api`
2. Clone the repo to a temp directory
3. Run the Architect → QA → Developer pipeline
4. Open a PR and auto-merge when all tasks pass

### Verbose mode

```bash
claude-factory start --repo weather-api --issue 1 -v
```

### Check version

```bash
claude-factory version
```

## Project Structure

```
dark-factory/
├── factory/
│   ├── cli.py              # claude-factory CLI
│   ├── orchestrator.py     # Main loop — task batching, red-green cycle
│   ├── github_client.py    # GitHub API integration
│   ├── agents/
│   │   ├── base.py         # Agent runner (spawns claude subprocesses)
│   │   ├── planner.py      # Architect agent
│   │   ├── evaluator.py    # QA Engineer agent
│   │   └── generator.py    # Developer agent
│   └── prompts/
│       ├── planner.md      # Architect rules & personality
│       ├── evaluator.md    # QA Engineer rules & personality
│       └── generator.md    # Developer rules & personality
├── DESIGN.md               # Full design document
└── diagrams/               # Architecture diagrams
```

## How Tasks Work

The Architect breaks each issue into tasks with dependencies:

```
Batch 1: [Setup project]              → runs first
Batch 2: [Health endpoint, API client] → run in parallel
Batch 3: [Weather endpoint]            → depends on batch 2
```

Tasks in the same batch run in parallel. A task only starts when all its dependencies are complete.

## Hard Rules

| Rule | Why |
|---|---|
| Developer CANNOT edit test files | Prevents weakening tests to pass |
| QA CANNOT edit source files | Clean separation of concerns |
| Each agent gets fresh context | No memory bleed between agents |
| Max 5 red-green rounds per task | Prevents infinite loops |
| Agents communicate through files | Artifacts survive context resets |

## Roadmap

- **Phase 1** — Factory core (orchestrator, agents, CLI) ✅
- **Phase 2** — CI/CD pipeline (Dockerfile, GitHub Actions, Docker Compose)
- **Phase 3** — Mission Control dashboard (real-time monitoring)
- **Phase 4** — Kubernetes (k3d + ArgoCD)

See [DESIGN.md](DESIGN.md) for the full architecture.
