# Changelog

## [0.12.2] - 2026-04-16

- docs: attribute StrongDM as inspiration without linking their repo


## [0.12.1] - 2026-04-16

- fix: correct EventEmitter import path in stage handlers


## [0.12.0] - 2026-04-16

- feat: pipeline engine Phase 4 — decompose run_job into 11 stage handlers


## [0.11.0] - 2026-04-16

- feat: pipeline engine Phase 3 — df_job handler + --engine=graph CLI flag


## [0.10.1] - 2026-04-16

- fix: serialize parallel tasks that share target files (closes #42)


## [0.10.0] - 2026-04-16

- feat: pipeline engine Phase 2 — subpipeline, parallel, loop handlers


## [0.9.0] - 2026-04-16

- feat: add Arbiter agent for QA/Dev deadlock resolution; clean up prescriptive prompts
- feat: add YAML pipeline engine (Phase 1)
- refactor: split bump and release back into separate workflows


## [0.8.0] - 2026-04-15

- feat: add YAML pipeline engine (Phase 1)
- refactor: split bump and release back into separate workflows


## [0.7.1] - 2026-04-15

- refactor: merge release.yml into auto-version.yml


## [0.7.0] - 2026-04-15

- fix: break QA↔Dev deadlock loops via explicit disagreement protocol (closes #43)
- fix: remove false-positive skip heuristic (closes #41)
- feat: auto-version DF on every push to main
- Fix ruff E501 in templates/__init__.py
- Fix rebase-loss; require layered architecture for backend services
- Sync fullstack STYLEGUIDE with fastapi
- Propagate cleaned CONVENTIONS.md to all template variants
- Rewrite fastapi template with layered architecture; add shared principles
- Suppress branch protection warning on free plan
- Handle empty-diff PR creation gracefully
- Fix Developer ignoring QA feedback, handle CI check API permissions
- Add auto-versioning skill and CD publish pipeline
- Wait for CI checks to pass before merging PRs
- Fix fastapi template: add missing pydantic-settings dependency
- Fix pre-check skip logic, add DF artifacts to all template gitignores
- Fix template variable substitution and loosen regression scope guard
- Add manual merge mode with 30s polling
- Add cost tracking and context validation
- Clean up dead code and move dynamic imports to top-level
- Add skills system: 12 reusable capabilities across 4 lifecycle phases
- Replace Staff Engineer with QA Lead, add reflection for simple tasks
- Add CI workflow templates for all project types
- Fix CI: install Node.js and dashboard frontend deps
- Inject role-specific standards instead of agents reading full docs
- Fix loose ends: restore pre-check, update Developer description
- Simplify agent flow: Developer writes code + tests, QA only reviews
- Add health report to detect AI degradation on large codebases
- Enforce layered context files (ARCHITECTURE.md, CONTEXT.md)
- Add CONVENTIONS.md — org-wide engineering standards
- Add STYLEGUIDE.md to project templates and wire into all agents
- Prevent DF artifacts from being committed to target repos
- Enforce coding standards and test hygiene in agent prompts
- Add rule: make test must pass after every task
- Auto-cleanup stale PRs on job start and in cleanup command
- Remove since timestamp fallback — job_id scoping is sufficient
- Scope fallback event queries by job created_at timestamp
- Fall back to task_id matching when no events have job_id
- Scope dashboard events by job_id to prevent cross-run collisions
- Fix status bar task counts to only show active job
- Only show events/tasks from active jobs on dashboard
- Fix elapsed time using latest job_started event, not earliest
- Clean up stale state files on job start
- Auto-abandon stale dashboard jobs when new job starts
- Add automatic orphan cleanup on job start and failure
- fix: skip PR creation when task branch has no new commits
- fix: rebase task branch onto origin/main before push in _finalize_task
- fix: use cherry-pick instead of merge when rebase fails in worktrees
- fix: install frontend deps in worktrees, detect missing commands
- fix: rebase worktree branches before merge to avoid 405 conflicts
- fix: clean up stale branches before creating worktrees


## [0.6.0] - 2026-04-15

- fix: remove false-positive skip heuristic (closes #41)
- feat: auto-version DF on every push to main
- Fix ruff E501 in templates/__init__.py
- Fix rebase-loss; require layered architecture for backend services
- Sync fullstack STYLEGUIDE with fastapi
- Propagate cleaned CONVENTIONS.md to all template variants
- Rewrite fastapi template with layered architecture; add shared principles
- Suppress branch protection warning on free plan
- Handle empty-diff PR creation gracefully
- Fix Developer ignoring QA feedback, handle CI check API permissions
- Add auto-versioning skill and CD publish pipeline
- Wait for CI checks to pass before merging PRs
- Fix fastapi template: add missing pydantic-settings dependency
- Fix pre-check skip logic, add DF artifacts to all template gitignores
- Fix template variable substitution and loosen regression scope guard
- Add manual merge mode with 30s polling
- Add cost tracking and context validation
- Clean up dead code and move dynamic imports to top-level
- Add skills system: 12 reusable capabilities across 4 lifecycle phases
- Replace Staff Engineer with QA Lead, add reflection for simple tasks
- Add CI workflow templates for all project types
- Fix CI: install Node.js and dashboard frontend deps
- Inject role-specific standards instead of agents reading full docs
- Fix loose ends: restore pre-check, update Developer description
- Simplify agent flow: Developer writes code + tests, QA only reviews
- Add health report to detect AI degradation on large codebases
- Enforce layered context files (ARCHITECTURE.md, CONTEXT.md)
- Add CONVENTIONS.md — org-wide engineering standards
- Add STYLEGUIDE.md to project templates and wire into all agents
- Prevent DF artifacts from being committed to target repos
- Enforce coding standards and test hygiene in agent prompts
- Add rule: make test must pass after every task
- Auto-cleanup stale PRs on job start and in cleanup command
- Remove since timestamp fallback — job_id scoping is sufficient
- Scope fallback event queries by job created_at timestamp
- Fall back to task_id matching when no events have job_id
- Scope dashboard events by job_id to prevent cross-run collisions
- Fix status bar task counts to only show active job
- Only show events/tasks from active jobs on dashboard
- Fix elapsed time using latest job_started event, not earliest
- Clean up stale state files on job start
- Auto-abandon stale dashboard jobs when new job starts
- Add automatic orphan cleanup on job start and failure
- fix: skip PR creation when task branch has no new commits
- fix: rebase task branch onto origin/main before push in _finalize_task
- fix: use cherry-pick instead of merge when rebase fails in worktrees
- fix: install frontend deps in worktrees, detect missing commands
- fix: rebase worktree branches before merge to avoid 405 conflicts
- fix: clean up stale branches before creating worktrees


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
- **Automatic orphan cleanup** — on job start, closes all open sub-issues whose parent issue is already closed (from previous failed/killed runs). Also cleans up sub-issues on job failure, not just success.

### Changed
- Developer default model changed from opus to sonnet (adaptive model picks per-task based on complexity)
- Batch processing uses worktrees for multi-task batches (true parallelism, not sequential)
- Task finalization (push/PR/merge) extracted into `_finalize_task()` for reuse across sequential and parallel paths
- `TaskInfo` gains `complexity` field (default: "medium")
- Planner prompt updated with complexity tagging guidelines and examples
- `cleanup` CLI command now reuses `GitHubClient.cleanup_orphaned_issues()` instead of duplicating logic

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
