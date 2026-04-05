# Dark Factory

Autonomous AI coding pipeline — you write the spec, AI builds, tests, and deploys it.

## How It Works

1. You create a GitHub Issue with requirements
2. **Architect** agent reads the issue, breaks it into tasks
3. **QA Engineer** agent writes failing tests (RED)
4. **Developer** agent writes code to make tests pass (GREEN)
5. QA reviews — if tests fail, Developer tries again (max 5 rounds)
6. If all pass: PR opened and auto-merged
7. If any fail: draft PR opened, needs-human issue created for retry

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
```

Processes all open issues in order by issue number.

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

Options: `haiku`, `sonnet`, `opus`. Default: `sonnet` for all agents.

### Verbose mode

```bash
dark-factory start --repo weather-api --issue 1 -v
```

## Failure Recovery

When a task fails after 5 red-green rounds:

1. Factory **continues** with remaining tasks
2. Opens a **draft PR** with completed work
3. Creates a **needs-human issue** for each failed task with:
   - Link to the original issue and draft PR
   - Task description and acceptance criteria
   - Last QA feedback
4. You **comment** on the issue with guidance ("try X instead", "the endpoint should return 201")
5. Run `dark-factory retry` — your comment is injected into the Developer's prompt
6. If retry passes: draft PR converted to ready, merged, issues closed

Jobs also **auto-resume** if they crash. State is saved to `~/.dark-factory/state/`.

## Project Structure

```
dark-factory/
├── factory/
│   ├── cli.py              # CLI — start, run, retry, repos, version
│   ├── orchestrator.py     # Main loop — task batching, red-green cycle
│   ├── github_client.py    # GitHub API — issues, PRs, repos
│   ├── state.py            # Session state persistence for resume
│   ├── security.py         # Command allowlisting for agents
│   ├── agents/
│   │   ├── base.py         # Agent runner (async subprocess spawning)
│   │   ├── planner.py      # Architect agent
│   │   ├── evaluator.py    # QA Engineer agent (red + regression + review)
│   │   └── generator.py    # Developer agent
│   └── prompts/
│       ├── planner.md      # Architect rules & personality
│       ├── evaluator.md    # QA Engineer rules & personality
│       └── generator.md    # Developer rules & personality
├── tests/                  # Unit tests (41 passing)
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

Tasks in the same batch run in parallel via `asyncio.gather`. A task only starts when all its dependencies are complete.

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
- **Phase 3** — Mission Control dashboard (real-time monitoring)
- **Phase 4** — Kubernetes (k3d + ArgoCD)

See [DESIGN.md](DESIGN.md) for the full architecture.
