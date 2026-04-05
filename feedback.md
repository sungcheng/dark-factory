# Feedback — Round 1

## Failing Tests (asyncio backend — 13 failures)

- `TestEnvExample::test_env_example_has_dashboard_url`: `DASHBOARD_URL` key is missing from `.env.example`
- `TestEnvExample::test_env_example_dashboard_url_has_value`: `DASHBOARD_URL` value is missing from `.env.example`
- `TestOrchestratorIntegration::test_orchestrator_imports_event_emitter`: `factory/orchestrator.py` does not import or reference `EventEmitter`
- `TestOrchestratorIntegration::test_orchestrator_calls_emit_job_started`: `orchestrator.py` does not call `emit_job_started`
- `TestOrchestratorIntegration::test_orchestrator_calls_emit_job_completed`: `orchestrator.py` does not call `emit_job_completed`
- `TestOrchestratorIntegration::test_orchestrator_calls_emit_job_failed`: `orchestrator.py` does not call `emit_job_failed`
- `TestOrchestratorIntegration::test_orchestrator_calls_emit_agent_spawned`: `orchestrator.py` does not call `emit_agent_spawned`
- `TestOrchestratorIntegration::test_orchestrator_calls_emit_agent_exited`: `orchestrator.py` does not call `emit_agent_exited`
- `TestOrchestratorIntegration::test_orchestrator_calls_emit_task_started`: `orchestrator.py` does not call `emit_task_started`
- `TestOrchestratorIntegration::test_orchestrator_calls_emit_task_completed`: `orchestrator.py` does not call `emit_task_completed`
- `TestOrchestratorIntegration::test_orchestrator_calls_emit_task_failed`: `orchestrator.py` does not call `emit_task_failed`
- `TestOrchestratorIntegration::test_orchestrator_calls_emit_round_result`: `orchestrator.py` does not call `emit_round_result`
- `TestOrchestratorIntegration::test_orchestrator_creates_emitter_in_run_job`: `orchestrator.py::run_job` does not instantiate `EventEmitter`

## Lint/Format Issues

- `tests/test_emitter.py` — ruff format check fails (`make check` exits non-zero). Run `make format` to fix.

## What to Fix

1. Add `DASHBOARD_URL` to `.env.example` with a placeholder value, e.g.:
   ```
   # Dashboard URL for event emission (leave empty to disable)
   DASHBOARD_URL=http://localhost:8420
   ```

2. Wire `EventEmitter` into `factory/orchestrator.py::run_job`:
   - Import: `from factory.dashboard.emitter import EventEmitter`
   - Instantiate `EventEmitter` at the start of `run_job`
   - Call `await emitter.emit_job_started(repo_name, issue_number)` at job start
   - Call `await emitter.emit_job_completed(...)` on success
   - Call `await emitter.emit_job_failed(...)` on failure
   - Call `await emitter.emit_agent_spawned(task_id, agent_type)` before each agent is spawned
   - Call `await emitter.emit_agent_exited(task_id, agent_type, success=...)` after each agent exits
   - Call `await emitter.emit_task_started(task_id)` / `emit_task_completed` / `emit_task_failed` at appropriate task lifecycle points
   - Call `await emitter.emit_round_result(task_id, round_num, passed=...)` after each red/green round

3. Run `make format` to reformat `tests/test_emitter.py`.

## Notes

- The `EventEmitter` class itself (`factory/dashboard/emitter.py`) is correctly implemented — all unit tests for it pass under asyncio.
- The 43 `[trio]` backend failures are pre-existing issues unrelated to this task (present before this PR).
