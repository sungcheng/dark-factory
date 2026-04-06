# Changelog

All notable changes to Dark Factory will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-04-05

### Added
- **Git worktree parallelism** — independent tasks and subtasks run in parallel via `git worktree`, each in its own directory. Falls back to sequential if worktree creation fails.
- **Staff Engineer review** — after all tasks merge and pass validation, an opus agent reads the full codebase against the original issue and makes targeted code quality improvements. Auto-reverts if changes break tests.
- **Adaptive model selection** — Architect tags tasks with complexity (`simple`/`medium`/`complex`). Developer model auto-selected: haiku for scaffolding, sonnet for standard features, opus for complex logic.
- **Smart failure analysis** — analyzes test output for common errors (ImportError, SyntaxError, TypeError, AttributeError, FileNotFoundError) and writes targeted feedback directly, skipping QA review agent spawn for obvious fixes.
- **Combined contracts+tests** — single QA agent writes both `contracts.md` and failing tests in one spawn, eliminating a separate haiku contracts agent per task.

### Changed
- Developer default model changed from opus to sonnet (adaptive model picks per-task based on complexity)
- Batch processing uses worktrees for multi-task batches (true parallelism, not sequential)
- Task finalization (push/PR/merge) extracted into `_finalize_task()` for reuse across sequential and parallel paths
- `TaskInfo` gains `complexity` field (default: "medium")
- Planner prompt updated with complexity tagging guidelines and examples

## [0.4.0] - 2026-04-05

### Added
- **Parallel by default** — `dark-factory run` now processes all issues concurrently (use `--sequential` for one-at-a-time)
- **Smarter Architect** — audits existing codebase before planning; skips tasks for features/scaffolding that already exist
- **Cleanup command** — `dark-factory cleanup --repo <name>` closes orphaned sub-issues, removes completed state files, cleans temp dirs. Supports `--dry-run`
- **Auto-cleanup on completion** — when a job finishes, automatically closes all sub-issues and needs-human issues for that parent
- **Narrative LiveLog** — emits detailed log lines to dashboard (contracts, scaffolding, round progress, PR creation, merge, validation)
- **Issue filtering** — `run` command skips auto-generated and needs-human issues (only processes real parent issues)

### Changed
- LiveLog panel height increased from h-64 to h-[32rem] for better visibility
- Time estimates use median instead of mean, filter out skipped tasks (<30s), never increase (monotonic floor)
- Task/event IDs namespaced by issue number to prevent cross-issue collisions in dashboard
- Events sorted chronologically after aggregation for correct timing calculations
- Elapsed time uses earliest job_started (total run time), not most recent

### Fixed
- Elapsed time showing minutes instead of hours (was picking newest job_started instead of earliest)
- Avg/task empty in dashboard (task ID collisions across issues causing failed event matching)
- `run` command was picking up sub-issues and needs-human issues as top-level jobs (19 parallel jobs instead of real parents)

## [0.3.0] - 2026-04-05

### Added
- **Subtask support** — tasks can now contain subtasks that share a single branch/PR but each get their own red-green cycle and commit
  - `SubTaskInfo` dataclass for subtask data model
  - `get_ready_subtask_batches()` for intra-task dependency resolution
  - `_process_task_with_subtasks()` orchestrator function
  - Architect prompt updated with subtask documentation and examples
  - Dashboard renders subtasks indented under parent tasks with timing and round indicators
  - State persistence handles subtask serialization/deserialization
  - ID uniqueness validation across tasks and subtasks
- **Smart task skip** — checks if task branch already merged, sub-issue closed, or tests already pass before spawning agents
- **Pre-check after QA writes tests** — runs tests before Developer; if code already exists and passes, skips Developer entirely
- **Developer reads existing code first** — prompt updated to require reading `src/` before writing
- **Job persistence to SQLite** — jobs now persisted to dashboard DB so historical jobs survive state file cleanup
- **Time estimates** — dashboard shows elapsed time, estimated remaining (recalculates as tasks complete), and avg time per task
- **Agent spawn counts** — agent cards show total spawns with category breakdown (contracts, tests, reviews, scaffold, coding)
- **Auto-select active job** — dashboard auto-selects in-progress job on load
- **Job selector dropdown** — replaced table with dropdown for job selection

### Changed
- Dashboard frontend rewritten to use direct fetch + `useEffect` instead of `usePolling` in App.tsx
- LiveLog receives events as props from parent (no independent polling)
- Agent cards infer state from event timestamps (handles missing `agent_exited` events)
- Emitter messages now include specific agent types (e.g., "QA Engineer (Contracts)" not just "QA")

### Fixed
- Emitter now passed to `_process_task` — per-task events flow to dashboard
- Added missing emitter calls for Developer spawning, QA review, and round failures
- Fixed frontend/backend type mismatches (`job_id` vs `id`, `in_progress` vs `running`, flat array vs wrapped)
- Fixed `TimeEstimate` to use most recent `job_started` event (handles restarts)
- Fixed test pollution — dashboard tests now mock `fetch_all_jobs` to isolate from real DB
- Cleaned test data from production SQLite DB

## [0.2.0] - 2026-04-05

### Added
- **Guardrails system** (`factory/guardrails.py`) — centralized pre-flight checks
  - **Tech stack detection**: scans repos for existing frameworks, languages, and tools; injects guardrail prompts into all agents to prevent stack migrations
  - **Secret/credential scanning**: pre-flight and post-merge scans for hardcoded API keys, tokens, passwords, private keys, and committed `.env` files
  - **File boundary enforcement**: feature tasks are blocked from modifying config files, Makefile, Dockerfile, CI workflows unless explicitly infra tasks
  - **Dependency guardrails**: detects competing packages (e.g., requests + httpx), warns on duplicates, tells agents what's already installed
  - **Regression scope guard**: blocks regression fixes that touch more than 5 files or modify infrastructure files; verifies test count doesn't decrease after a job
- **Pre-flight checks** in orchestrator — all guardrails run before any agent spawns; blocks job if secrets found or critical issues detected
- **Post-merge secret scan** — scans final merged state for hardcoded secrets before marking job complete
- **Test count tracking** — counts tests before job starts, verifies count doesn't decrease after all tasks merge
- **Semantic versioning** — single source of truth in `factory/__init__.py`, dynamic version in `pyproject.toml`, `dark-factory version` reads from package
- **CHANGELOG.md** — this file

### Changed
- Planner agent now receives detected tech stack as a guardrail prompt
- Generator agent (scaffold + code) injects tech stack, file boundary, and dependency guardrails into every prompt
- Security policy (`CLAUDE.md`) now includes tech stack guardrails and secret/dependency rules
- `planner.md` prompt updated with "Respecting Existing Tech Stack" section
- `generator.md` prompt updated with rules against competing frameworks, duplicate deps, and `.env` access
- `evaluator.md` prompt updated with secret scanning and dependency checks in review phase

## [0.1.0] - 2026-04-04

### Added
- Core orchestrator with red-green TDD loop
- Architect, Developer, QA Engineer agent roles
- GitHub integration (issues, branches, PRs, auto-merge)
- Smart QA bypass (run tests directly, skip agent if passing)
- Self-healing regression gate
- Post-merge validation with auto-fix
- Crash recovery via state persistence
- Mission Control dashboard (FastAPI + React)
- Project scaffolding (FastAPI, Fullstack, Terraform templates)
- CLI: start, run, retry, create-project, create-issue, repos
- Security policy (command allowlisting)
- Parallel task batching
- Human escalation for failed tasks
