"""Phase 4 stage handlers — decompose `run_job` into YAML-addressable nodes.

Each handler does one stage of a Dark Factory job. All share state
through `JobRuntime` (stored in `PipelineContext.state["job_runtime"]`).
Most delegate to helpers already in `factory.orchestrator` rather than
duplicating code, so the decomposition is a layering change, not a
logic rewrite.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from factory.pipeline.job_runtime import RUNTIME_KEY
from factory.pipeline.job_runtime import JobRuntime
from factory.pipeline.job_runtime import get_runtime
from factory.pipeline.schema import NodeResult

if TYPE_CHECKING:
    from factory.pipeline.engine import PipelineContext
    from factory.pipeline.schema import Node

LOG = logging.getLogger(__name__)


async def job_setup_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Initialize runtime: dashboard, health check, github client, state, issue."""
    from factory.dashboard.emitter import EventEmitter
    from factory.github_client import GitHubClient
    from factory.orchestrator import JobContext
    from factory.orchestrator import _check_claude_cli
    from factory.orchestrator import _ensure_dashboard_running
    from factory.state import JobState
    from factory.state import load_state

    repo_name = node.params["repo_name"]
    issue_number = int(node.params["issue_number"])
    model = node.params.get("model")
    merge_mode = node.params.get("merge_mode", "auto")

    await _ensure_dashboard_running()
    await _check_claude_cli()

    job_id = f"{repo_name}#{issue_number}"
    emitter = EventEmitter(job_id=job_id)
    await emitter.emit_job_started(repo_name, issue_number)

    github = GitHubClient()
    job_ctx = JobContext(repo_name=repo_name, issue_number=issue_number)

    state = load_state(repo_name, issue_number)
    if state and state.working_dir and Path(state.working_dir).exists():
        LOG.info("🔄 Resuming job from saved state")
        job_ctx.working_dir = state.working_dir
        job_ctx.branch = state.branch
        job_ctx.tasks = state.tasks
    else:
        state = JobState(repo_name=repo_name, issue_number=issue_number)

    issue = github.fetch_issue(repo_name, issue_number)
    LOG.info("📋 Fetched issue: %s", issue.title)
    await emitter.emit_log(job_id, f"📋 Fetched issue: {issue.title}")

    runtime = JobRuntime(
        repo_name=repo_name,
        issue_number=issue_number,
        model=model,
        merge_mode=merge_mode,
        github=github,
        emitter=emitter,
        state=state,
        ctx=job_ctx,
        issue=issue,
    )
    ctx.state[RUNTIME_KEY] = runtime
    return NodeResult(
        status="success",
        data={"issue_title": issue.title, "resumed": job_ctx.working_dir != ""},
    )


async def clone_repo_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Clone the target repo and write the security policy."""
    from factory.orchestrator import _clone_repo
    from factory.security import write_security_policy

    r = get_runtime(ctx.state)
    assert r.github and r.ctx and r.state

    if not r.ctx.working_dir:
        r.ctx.working_dir = await _clone_repo(r.github, r.ctx)
        write_security_policy(r.ctx.working_dir)
        r.state.working_dir = r.ctx.working_dir
        from factory.state import save_state

        save_state(r.state)
    return NodeResult(status="success", data={"working_dir": r.ctx.working_dir})


async def preflight_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Run pre-flight guardrails and cleanup orphaned artifacts."""
    from factory.guardrails import format_secret_findings
    from factory.guardrails import run_preflight_checks
    from factory.state import cleanup_stale_state_files

    r = get_runtime(ctx.state)
    assert r.ctx and r.github and r.emitter

    preflight = run_preflight_checks(r.ctx.working_dir)
    if not preflight.passed:
        for reason in preflight.blocking_reasons:
            LOG.error("🚫 Guardrail: %s", reason)
        if preflight.secret_findings:
            LOG.error(
                "Secret scan report:\n%s",
                format_secret_findings(preflight.secret_findings),
            )
        return NodeResult(
            status="failed",
            message="Pre-flight guardrail checks failed",
        )
    r.preflight = preflight

    orphan_count = r.github.cleanup_orphaned_issues(r.repo_name)
    if orphan_count:
        LOG.info("🧹 Cleaned up %d orphaned issue(s)", orphan_count)

    stale_count = cleanup_stale_state_files(r.repo_name, r.issue_number)
    if stale_count:
        LOG.info("🧹 Removed %d stale state file(s)", stale_count)

    pr_count = r.github.cleanup_stale_prs(r.repo_name)
    if pr_count:
        LOG.info("🧹 Closed %d stale PR(s)", pr_count)

    tech_stack = preflight.tech_stack
    LOG.info("🔍 Tech stack: %s", tech_stack.summary())
    job_tag = f"{r.repo_name}#{r.issue_number}"
    await r.emitter.emit_log(job_tag, f"🔍 Tech stack: {tech_stack.summary()}")

    return NodeResult(status="success", data={"tech_stack": tech_stack.summary()})


async def pre_job_skills_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Run pre-job skills (codebase profile, standards bootstrap, etc.)."""
    from factory.guardrails import count_tests
    from factory.skills.base import SkillContext
    from factory.skills.base import SkillPhase
    from factory.skills.registry import run_phase

    r = get_runtime(ctx.state)
    assert r.ctx and r.emitter

    skill_ctx = SkillContext(
        working_dir=r.ctx.working_dir,
        repo_name=r.repo_name,
        issue_number=r.issue_number,
        model=r.model,
    )
    job_tag = f"{r.repo_name}#{r.issue_number}"
    results = await run_phase(SkillPhase.PRE_JOB, skill_ctx)
    for sr in results:
        if sr.files_created:
            LOG.info("🔧 Skill: %s", sr.message)
            await r.emitter.emit_log(job_tag, f"🔧 {sr.message}")

    r.pre_job_test_count = await count_tests(r.ctx.working_dir)
    return NodeResult(status="success", data={"test_count": r.pre_job_test_count})


async def regression_gate_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Gate new work on the existing test suite passing (when tests exist)."""
    from factory.orchestrator import _has_tests
    from factory.orchestrator import _regression_gate_with_healing

    r = get_runtime(ctx.state)
    assert r.ctx and r.emitter

    job_tag = f"{r.repo_name}#{r.issue_number}"
    r.has_existing_tests = await _has_tests(r.ctx.working_dir)
    if r.has_existing_tests:
        LOG.info("🛡️ Running regression gate...")
        await r.emitter.emit_log(job_tag, "🛡️ Running regression gate...")
        try:
            await _regression_gate_with_healing(r.ctx, r.model)
        except Exception as exc:
            return NodeResult(status="failed", message=str(exc))
        await r.emitter.emit_log(job_tag, "🛡️ Regression gate passed", "success")
    else:
        LOG.info("🛡️ Skipping regression gate — no existing tests")
        await r.emitter.emit_log(
            job_tag,
            "🛡️ Skipping regression gate — no existing tests",
        )

    return NodeResult(
        status="success",
        data={"has_existing_tests": r.has_existing_tests},
    )


async def architect_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Spawn the Architect (or fast-track for simple issues) to produce tasks."""
    from factory.agents.planner import run_planner
    from factory.github_client import TaskInfo
    from factory.orchestrator import _is_simple_issue
    from factory.orchestrator import _load_tasks
    from factory.state import save_state

    r = get_runtime(ctx.state)
    assert r.ctx and r.github and r.emitter and r.issue and r.state and r.preflight

    job_tag = f"{r.repo_name}#{r.issue_number}"

    # Resuming run — tasks already loaded
    if r.ctx.tasks:
        return NodeResult(status="success", data={"task_count": len(r.ctx.tasks)})

    if _is_simple_issue(r.issue.title, r.issue.body or ""):
        LOG.info("⚡ Simple issue detected — skipping Architect")
        await r.emitter.emit_log(job_tag, "⚡ Simple issue — skipping Architect")
        r.ctx.tasks = [
            TaskInfo(
                id="task-1",
                title=r.issue.title,
                description=r.issue.body or r.issue.title,
                acceptance_criteria=[
                    line.lstrip("- ").lstrip("* ").strip()
                    for line in (r.issue.body or "").split("\n")
                    if line.strip().startswith(("- ", "* "))
                ]
                or [r.issue.title],
                depends_on=[],
            ),
        ]
    else:
        LOG.info("🏗️ Spawning Architect...")
        await r.emitter.emit_log(job_tag, "🏗️ Spawning Architect...")
        planner_result = await run_planner(
            issue_title=r.issue.title,
            issue_body=r.issue.body or "",
            repo_name=r.repo_name,
            working_dir=r.ctx.working_dir,
            model=r.model,
            tech_stack_prompt=r.preflight.tech_stack.as_guardrail_prompt(),
        )
        tasks_path = Path(r.ctx.working_dir) / "tasks.json"
        if not planner_result.success and not tasks_path.exists():
            return NodeResult(status="failed", message="Architect agent failed")
        r.ctx.tasks = _load_tasks(r.ctx.working_dir)

    r.state.tasks = r.ctx.tasks
    save_state(r.state)
    return NodeResult(status="success", data={"task_count": len(r.ctx.tasks)})


async def create_sub_issues_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Create (or reuse) GitHub sub-issues for each task, then reset any failed ones."""
    from factory.state import save_state

    r = get_runtime(ctx.state)
    assert r.ctx and r.github and r.emitter and r.state

    # Dedupe — close stale sub-issues first (Architect path only; skip if tasks
    # look fresh from this run)
    active_titles = [t.title for t in r.ctx.tasks]
    stale = r.github.close_stale_sub_issues(
        r.repo_name,
        r.issue_number,
        active_titles,
    )
    if stale:
        LOG.info("🧹 Closed %d stale sub-issue(s)", stale)

    r.ctx.tasks = r.github.create_sub_issues(
        r.repo_name,
        r.issue_number,
        r.ctx.tasks,
    )
    r.state.tasks = r.ctx.tasks
    save_state(r.state)

    job_tag = f"{r.repo_name}#{r.issue_number}"
    LOG.info("📝 Created %d tasks with GitHub sub-issues", len(r.ctx.tasks))
    await r.emitter.emit_log(
        job_tag,
        f"📝 Created {len(r.ctx.tasks)} tasks with GitHub sub-issues",
    )
    tasks_data = json.dumps(
        [{"id": t.id, "title": t.title, "status": t.status} for t in r.ctx.tasks],
    )
    await r.emitter.update_job_tasks(
        repo=r.repo_name,
        issue_number=r.issue_number,
        task_count=len(r.ctx.tasks),
        completed_task_count=0,
        tasks_json=tasks_data,
    )

    # Reset any failed tasks so retries get fresh rounds
    for task in r.ctx.tasks:
        if task.status == "failed":
            LOG.info("🔄 Resetting failed task '%s'", task.title)
            task.status = "pending"
            for st in task.subtasks:
                if st.status == "failed":
                    st.status = "pending"
            save_state(r.state)

    return NodeResult(status="success")


async def process_batches_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Run every task batch — worktrees when multi-task, sequential otherwise."""
    from factory.orchestrator import _process_batch_with_worktrees
    from factory.orchestrator import _process_single_task_in_batch
    from factory.orchestrator import get_ready_batches

    r = get_runtime(ctx.state)
    assert r.ctx and r.github and r.emitter and r.state

    job_tag = f"{r.repo_name}#{r.issue_number}"
    for batch in get_ready_batches(r.ctx.tasks):
        batch_titles = [t.title for t in batch]
        LOG.info("📦 Processing batch: %s", batch_titles)
        await r.emitter.emit_log(
            job_tag,
            f"📦 Processing batch: {', '.join(batch_titles)}",
        )
        if len(batch) > 1:
            await _process_batch_with_worktrees(
                batch,
                r.ctx,
                r.github,
                r.model,
                r.state,
                r.emitter,
                r.repo_name,
                r.issue_number,
                r.merge_mode,
            )
        else:
            await _process_single_task_in_batch(
                batch[0],
                r.ctx,
                r.github,
                r.model,
                r.state,
                r.emitter,
                r.repo_name,
                r.issue_number,
                r.merge_mode,
            )

    completed = [t for t in r.ctx.tasks if t.status == "completed"]
    failed = [t for t in r.ctx.tasks if t.status == "failed"]
    if failed:
        await r.emitter.emit_job_failed(r.repo_name, r.issue_number)
        LOG.warning(
            "⏸️ Job paused. %d/%d completed, %d failed.",
            len(completed),
            len(r.ctx.tasks),
            len(failed),
        )
    status = "failed" if failed else "success"
    return NodeResult(
        status=status,
        data={"completed": len(completed), "failed": len(failed)},
    )


async def post_merge_validation_handler(
    node: Node,
    ctx: PipelineContext,
) -> NodeResult:
    """Final validation after all tasks merge: main pull, scope guard, secret scan."""
    from factory.guardrails import scan_for_secrets
    from factory.guardrails import verify_test_count_not_decreased
    from factory.orchestrator import _checkout_main
    from factory.orchestrator import _install_frontend_deps
    from factory.orchestrator import _post_merge_validation
    from factory.orchestrator import _pull_latest

    r = get_runtime(ctx.state)
    assert r.ctx and r.emitter

    job_tag = f"{r.repo_name}#{r.issue_number}"
    LOG.info("🔍 Running post-merge validation...")
    await r.emitter.emit_log(job_tag, "🔍 Running post-merge validation...")

    await _checkout_main(r.ctx)
    await _pull_latest(r.ctx)
    await _install_frontend_deps(r.ctx.working_dir)

    ok, msg = await verify_test_count_not_decreased(
        r.ctx.working_dir,
        r.pre_job_test_count,
    )
    if not ok:
        LOG.error("🚫 %s", msg)

    findings = scan_for_secrets(r.ctx.working_dir)
    real_secrets = [s for s in findings if s.pattern_name != ".env file"]
    if real_secrets:
        LOG.warning(
            "⚠️ Post-merge secret scan found %d issue(s).",
            len(real_secrets),
        )

    validation_ok = await _post_merge_validation(r.ctx, r.model)
    return NodeResult(
        status="success" if validation_ok else "failed",
        data={"validation_ok": validation_ok},
    )


async def qa_lead_review_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """QA Lead reviews the full implementation; commits improvements or reverts."""
    from factory.agents.evaluator import run_final_review
    from factory.orchestrator import _cleanup_df_artifacts
    from factory.orchestrator import _push_changes
    from factory.orchestrator import _run_tests_with_check

    r = get_runtime(ctx.state)
    assert r.ctx and r.emitter and r.issue

    job_tag = f"{r.repo_name}#{r.issue_number}"
    await _cleanup_df_artifacts(r.ctx)

    LOG.info("🔍 QA Lead: holistic review...")
    await r.emitter.emit_log(job_tag, "🔍 QA Lead reviewing full implementation...")
    review_result = await run_final_review(
        issue_title=r.issue.title,
        issue_body=r.issue.body or "",
        working_dir=r.ctx.working_dir,
    )
    if not review_result.success:
        return NodeResult(status="failed", message="QA Lead review failed")

    await _git(r.ctx.working_dir, "add", "-A")
    diff_cached = await _git(
        r.ctx.working_dir,
        "diff",
        "--cached",
        "--quiet",
        check=False,
    )
    if diff_cached == 1:  # returncode 1 means there are staged changes
        await _git(
            r.ctx.working_dir,
            "commit",
            "-m",
            "refactor: QA lead review improvements",
        )
        await _push_changes(r.ctx)
        LOG.info("✅ QA Lead committed improvements")
        still_ok, _ = await _run_tests_with_check(r.ctx.working_dir)
        if not still_ok:
            LOG.warning("⚠️ QA Lead broke tests — reverting")
            await _git(r.ctx.working_dir, "revert", "HEAD", "--no-edit")
            await _push_changes(r.ctx)
    else:
        LOG.info("✅ QA Lead: code looks good, no changes")
    return NodeResult(status="success")


async def post_job_skills_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Run post-job skills (doc sync, dead-code sweep, PR polish) and commit updates."""
    from factory.orchestrator import _push_changes
    from factory.skills.base import SkillContext
    from factory.skills.base import SkillPhase
    from factory.skills.registry import run_phase

    r = get_runtime(ctx.state)
    assert r.ctx and r.emitter and r.github and r.state

    job_tag = f"{r.repo_name}#{r.issue_number}"
    skill_ctx = SkillContext(
        working_dir=r.ctx.working_dir,
        repo_name=r.repo_name,
        issue_number=r.issue_number,
        model=r.model,
    )
    results = await run_phase(SkillPhase.POST_JOB, skill_ctx)
    for sr in results:
        if sr.message and sr.message != "No dead code found":
            LOG.info("🔧 Post-job: %s", sr.message)
            await r.emitter.emit_log(job_tag, f"🔧 {sr.message}")

    await _git(r.ctx.working_dir, "add", "-A")
    diff_cached = await _git(
        r.ctx.working_dir,
        "diff",
        "--cached",
        "--quiet",
        check=False,
    )
    if diff_cached == 1:
        await _git(
            r.ctx.working_dir,
            "commit",
            "-m",
            "chore: post-job skill updates (docs, cleanup)",
        )
        await _push_changes(r.ctx)

    await r.emitter.emit_job_completed(r.repo_name, r.issue_number)
    r.github.close_issue(r.repo_name, r.issue_number)
    r.state.status = "completed"
    from factory.state import save_state

    save_state(r.state)
    return NodeResult(status="success")


async def _git(working_dir: str, *args: str, check: bool = True) -> int:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    code = proc.returncode or 0
    if check and code != 0:
        raise RuntimeError(f"git {' '.join(args)} failed (exit {code})")
    return code
