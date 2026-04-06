"""Orchestrator — the dumb Python script that runs the factory.

No AI here. Just subprocess management, task ordering, and GitHub integration.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Generator
from pathlib import Path

from factory.agents.evaluator import run_evaluator_contracts_and_tests
from factory.agents.evaluator import run_evaluator_regression
from factory.agents.evaluator import run_evaluator_review
from factory.agents.generator import run_generator
from factory.agents.generator import run_generator_scaffold
from factory.agents.generator import run_staff_review
from factory.agents.planner import run_planner
from factory.dashboard.emitter import EventEmitter
from factory.github_client import GitHubClient
from factory.github_client import JobContext
from factory.github_client import SubTaskInfo
from factory.github_client import TaskInfo
from factory.guardrails import check_regression_scope
from factory.guardrails import count_tests
from factory.guardrails import format_secret_findings
from factory.guardrails import run_preflight_checks
from factory.guardrails import verify_test_count_not_decreased
from factory.security import write_security_policy
from factory.state import JobState
from factory.state import load_state
from factory.state import save_state

LOG = logging.getLogger(__name__)

MAX_ROUNDS = 5

# Map task complexity → Developer model (overrides default if no --model flag)
COMPLEXITY_MODELS: dict[str, str] = {
    "simple": "haiku",
    "medium": "sonnet",
    "complex": "opus",
}


async def run_job(
    repo_name: str,
    issue_number: int,
    model: str | None = None,
) -> None:
    """Main orchestrator loop."""
    # Start dashboard if not running
    await _ensure_dashboard_running()

    # Health check — verify claude CLI works before doing anything
    await _check_claude_cli()

    emitter = EventEmitter()
    await emitter.emit_job_started(repo_name, issue_number)

    github = GitHubClient()
    ctx = JobContext(repo_name=repo_name, issue_number=issue_number)

    # Check for resumable state
    state = load_state(repo_name, issue_number)
    if state and state.working_dir and Path(state.working_dir).exists():
        LOG.info("🔄 Resuming job from saved state")
        ctx.working_dir = state.working_dir
        ctx.branch = state.branch
        ctx.tasks = state.tasks
    else:
        state = JobState(repo_name=repo_name, issue_number=issue_number)

    job_tag = f"{repo_name}#{issue_number}"
    LOG.info("🏭 Starting job for %s#%d", repo_name, issue_number)

    # Step 1: Fetch the issue
    issue = github.fetch_issue(repo_name, issue_number)
    LOG.info("📋 Fetched issue: %s", issue.title)
    await emitter.emit_log(job_tag, f"📋 Fetched issue: {issue.title}")

    # Step 2: Clone the repo (if not resuming)
    if not ctx.working_dir:
        ctx.working_dir = await _clone_repo(github, ctx)
        write_security_policy(ctx.working_dir)
        state.working_dir = ctx.working_dir
        save_state(state)

    # Step 2.5: Pre-flight guardrail checks
    preflight = run_preflight_checks(ctx.working_dir)
    if not preflight.passed:
        for reason in preflight.blocking_reasons:
            LOG.error("🚫 Guardrail: %s", reason)
        if preflight.secret_findings:
            LOG.error(
                "Secret scan report:\n%s",
                format_secret_findings(preflight.secret_findings),
            )
        raise RuntimeError(
            "Pre-flight guardrail checks failed. "
            "Fix the issues above before running the factory."
        )

    tech_stack = preflight.tech_stack
    LOG.info("🔍 Tech stack: %s", tech_stack.summary())
    await emitter.emit_log(job_tag, f"🔍 Tech stack: {tech_stack.summary()}")

    # Count tests before any changes (for regression scope guard)
    pre_job_test_count = await count_tests(ctx.working_dir)

    # Step 3: Regression gate — skip on first task (nothing to regress)
    has_existing_tests = await _has_tests(ctx.working_dir)
    if has_existing_tests:
        LOG.info("🛡️ Running regression gate...")
        await emitter.emit_log(job_tag, "🛡️ Running regression gate...")
        await _regression_gate_with_healing(ctx, model)
        await emitter.emit_log(job_tag, "🛡️ Regression gate passed", "success")
    else:
        LOG.info("🛡️ Skipping regression gate — no existing tests")
        await emitter.emit_log(
            job_tag, "🛡️ Skipping regression gate — no existing tests"
        )

    # Step 4: Spawn the Architect or fast-track simple issues
    if not ctx.tasks:
        if _is_simple_issue(issue.title, issue.body or ""):
            # Simple issue — skip Architect, create a single task directly
            LOG.info("⚡ Simple issue detected — skipping Architect")
            await emitter.emit_log(job_tag, "⚡ Simple issue — skipping Architect")
            ctx.tasks = [
                TaskInfo(
                    id="task-1",
                    title=issue.title,
                    description=issue.body or issue.title,
                    acceptance_criteria=[
                        line.lstrip("- ").lstrip("* ").strip()
                        for line in (issue.body or "").split("\n")
                        if line.strip().startswith(("- ", "* "))
                    ]
                    or [issue.title],
                    depends_on=[],
                ),
            ]
            ctx.tasks = github.create_sub_issues(repo_name, issue_number, ctx.tasks)
        else:
            LOG.info("🏗️ Spawning Architect...")
            await emitter.emit_log(job_tag, "🏗️ Spawning Architect...")
            planner_result = await run_planner(
                issue_title=issue.title,
                issue_body=issue.body or "",
                repo_name=repo_name,
                working_dir=ctx.working_dir,
                model=model,
                tech_stack_prompt=tech_stack.as_guardrail_prompt(),
            )

            tasks_path = Path(ctx.working_dir) / "tasks.json"
            if not planner_result.success and not tasks_path.exists():
                LOG.error("Architect failed (stderr): %s", planner_result.stderr)
                LOG.error("Architect failed (stdout): %s", planner_result.stdout[:500])
                raise RuntimeError("Architect agent failed")
            if not planner_result.success:
                LOG.warning(
                    "Architect exited with error but tasks.json exists — continuing"
                )

            ctx.tasks = _load_tasks(ctx.working_dir)

            # Close stale sub-issues from previous runs
            active_titles = [t.title for t in ctx.tasks]
            stale_count = github.close_stale_sub_issues(
                repo_name,
                issue_number,
                active_titles,
            )
            if stale_count:
                LOG.info(
                    "🧹 Closed %d stale sub-issue(s) from previous runs",
                    stale_count,
                )

            # Create or reuse sub-issues (deduplicates by title)
            ctx.tasks = github.create_sub_issues(repo_name, issue_number, ctx.tasks)

        state.tasks = ctx.tasks
        save_state(state)
        LOG.info("📝 Created %d tasks with GitHub sub-issues", len(ctx.tasks))
        await emitter.emit_log(
            job_tag,
            f"📝 Created {len(ctx.tasks)} tasks with GitHub sub-issues",
        )

        # Persist task info to dashboard DB
        import json as _json

        tasks_data = _json.dumps(
            [{"id": t.id, "title": t.title, "status": t.status} for t in ctx.tasks]
        )
        await emitter.update_job_tasks(
            repo=repo_name,
            issue_number=issue_number,
            task_count=len(ctx.tasks),
            completed_task_count=0,
            tasks_json=tasks_data,
        )

    # Step 5: Reset failed tasks so re-runs get a fresh 5 rounds
    for task in ctx.tasks:
        if task.status == "failed":
            LOG.info("🔄 Resetting failed task '%s' for retry", task.title)
            task.status = "pending"
            for st in task.subtasks:
                if st.status == "failed":
                    st.status = "pending"
            save_state(state)

    # Step 6: Process tasks — each task gets its own branch, PR, merge
    for batch in get_ready_batches(ctx.tasks):
        batch_titles = [t.title for t in batch]
        LOG.info("📦 Processing batch: %s", batch_titles)
        await emitter.emit_log(
            job_tag, f"📦 Processing batch: {', '.join(batch_titles)}"
        )

        if len(batch) > 1:
            # Parallel batch: run independent tasks concurrently via worktrees
            await _process_batch_with_worktrees(
                batch, ctx, github, model, state, emitter,
                repo_name, issue_number,
            )
        else:
            # Single task — no worktree overhead
            task = batch[0]
            await _process_single_task_in_batch(
                task, ctx, github, model, state, emitter,
                repo_name, issue_number,
            )

    # Step 7: Finalize
    completed = [t for t in ctx.tasks if t.status == "completed"]
    failed = [t for t in ctx.tasks if t.status == "failed"]

    if failed:
        await emitter.emit_job_failed(repo_name, issue_number)
        LOG.warning(
            "⏸️ Job paused. %d/%d tasks completed, %d failed. "
            "Comment on the needs-human issues and run: "
            "dark-factory retry --repo %s --issue %d",
            len(completed),
            len(ctx.tasks),
            len(failed),
            repo_name,
            issue_number,
        )
    else:
        # Post-merge validation — pull final main, run full check
        LOG.info("🔍 Running post-merge validation...")
        await emitter.emit_log(job_tag, "🔍 Running post-merge validation...")
        await _checkout_main(ctx)
        await _pull_latest(ctx)
        await _install_frontend_deps(ctx.working_dir)

        # Regression scope guard: verify test count didn't decrease
        test_ok, test_msg = await verify_test_count_not_decreased(
            ctx.working_dir,
            pre_job_test_count,
        )
        if not test_ok:
            LOG.error("🚫 %s", test_msg)

        # Secret scan on final state
        from factory.guardrails import scan_for_secrets

        final_secrets = scan_for_secrets(ctx.working_dir)
        real_secrets = [s for s in final_secrets if s.pattern_name != ".env file"]
        if real_secrets:
            LOG.warning(
                "⚠️ Post-merge secret scan found %d issue(s). Review before deploying.",
                len(real_secrets),
            )

        validation_ok = await _post_merge_validation(
            ctx,
            model,
        )
        if validation_ok:
            # Staff Engineer review — opus reads everything and optimizes
            LOG.info("👨‍💻 Staff Engineer reviewing code quality...")
            await emitter.emit_log(
                job_tag,
                "👨‍💻 Staff Engineer reviewing code quality (opus)...",
            )
            staff_result = await run_staff_review(
                issue_title=issue.title,
                issue_body=issue.body or "",
                working_dir=ctx.working_dir,
            )
            if staff_result.success:
                # Commit and push any improvements
                proc = await asyncio.create_subprocess_exec(
                    "git", "add", "-A",
                    cwd=ctx.working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                proc = await asyncio.create_subprocess_exec(
                    "git", "diff", "--cached", "--quiet",
                    cwd=ctx.working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode != 0:
                    # There are staged changes — commit them
                    proc = await asyncio.create_subprocess_exec(
                        "git", "commit", "-m",
                        "refactor: staff engineer code review improvements",
                        cwd=ctx.working_dir,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await proc.communicate()
                    await _push_changes(ctx)
                    LOG.info("✅ Staff Engineer committed improvements")
                    await emitter.emit_log(
                        job_tag,
                        "✅ Staff Engineer improvements committed",
                        "success",
                    )
                    # Re-validate after staff changes
                    still_ok, _ = await _run_tests_with_check(
                        ctx.working_dir,
                    )
                    if not still_ok:
                        LOG.warning(
                            "⚠️ Staff Engineer broke tests — reverting"
                        )
                        proc = await asyncio.create_subprocess_exec(
                            "git", "revert", "HEAD",
                            "--no-edit",
                            cwd=ctx.working_dir,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        await proc.communicate()
                        await _push_changes(ctx)
                else:
                    LOG.info(
                        "✅ Staff Engineer: code looks good, no changes"
                    )
                    await emitter.emit_log(
                        job_tag,
                        "✅ Staff Engineer: code is clean",
                        "success",
                    )

            await emitter.emit_job_completed(repo_name, issue_number)
            github.close_issue(repo_name, issue_number)
            state.status = "completed"
            save_state(state)

            # Auto-cleanup: close all sub-issues for this parent
            _auto_cleanup_sub_issues(
                github, repo_name, issue_number
            )

            await emitter.emit_log(
                job_tag,
                f"✅ All {len(completed)} tasks complete. "
                f"Issue #{issue_number} closed.",
                "success",
            )
            LOG.info(
                "✅ All %d tasks complete. Post-merge validation "
                "passed. Issue #%d closed.",
                len(completed),
                issue_number,
            )
        else:
            await emitter.emit_job_failed(repo_name, issue_number)
            state.status = "failed"
            save_state(state)
            await emitter.emit_log(
                job_tag,
                f"⚠️ Post-merge validation failed. Issue #{issue_number} left open.",
                "failure",
            )
            LOG.warning(
                "⚠️ All tasks merged but post-merge validation "
                "failed. Issue #%d left open for manual review.",
                issue_number,
            )


async def retry_job(
    repo_name: str,
    issue_number: int,
    model: str | None = None,
) -> None:
    """Retry failed tasks using human guidance from GitHub issue comments."""
    github = GitHubClient()

    state = load_state(repo_name, issue_number)
    if not state:
        raise RuntimeError(f"No saved state for {repo_name}#{issue_number}")

    if not state.working_dir or not Path(state.working_dir).exists():
        raise RuntimeError(f"Working directory gone: {state.working_dir}")

    ctx = JobContext(
        repo_name=repo_name,
        issue_number=issue_number,
        working_dir=state.working_dir,
        branch=state.branch,
        tasks=state.tasks,
    )

    LOG.info("🔄 Retrying failed tasks for %s#%d", repo_name, issue_number)

    failed_tasks = [t for t in ctx.tasks if t.status == "failed"]
    if not failed_tasks:
        LOG.info("No failed tasks to retry")
        return

    for task in failed_tasks:
        human_guidance = ""
        if task.failure_issue:
            comments = github.get_issue_comments(repo_name, task.failure_issue)
            if comments:
                human_guidance = "\n\n".join(comments)
                LOG.info("Found human guidance for task '%s'", task.title)
            else:
                LOG.warning(
                    "No comments on failure issue #%d — retrying without guidance",
                    task.failure_issue,
                )

        task.status = "pending"
        await _process_task_with_guidance(
            task, ctx, github, model, state, human_guidance
        )

    still_failed = [t for t in ctx.tasks if t.status == "failed"]

    await _push_changes(ctx)

    if still_failed:
        for task in still_failed:
            feedback = _read_feedback(ctx.working_dir)
            if task.failure_issue:
                repo = github.get_repo(repo_name)
                issue = repo.get_issue(task.failure_issue)
                issue.create_comment(
                    f"Retry failed. Still failing after {MAX_ROUNDS} more rounds.\n\n"
                    f"```\n{feedback}\n```"
                )
        save_state(state)
        LOG.warning(
            "Retry failed. %d task(s) still need human input.",
            len(still_failed),
        )
    else:
        if state.pr_number:
            repo = github.get_repo(repo_name)
            pr = repo.get_pull(state.pr_number)
            completed = [t for t in ctx.tasks if t.status == "completed"]
            pr.edit(  # type: ignore[call-arg]
                title=f"feat: {repo.get_issue(issue_number).title}",
                body=(
                    f"Closes #{issue_number}\n\n"
                    f"Autonomous implementation by Dark Factory.\n\n"
                    f"## Tasks completed\n"
                    + "\n".join(f"- [x] {t.title}" for t in completed)
                ),
                draft=False,
            )
            github.merge_pr(repo_name, state.pr_number)

        for task in ctx.tasks:
            if task.failure_issue:
                github.close_issue(repo_name, task.failure_issue)

        github.close_issue(repo_name, issue_number)
        state.status = "completed"
        save_state(state)
        LOG.info("✅ Retry successful. All tasks complete. PR merged.")


async def _process_task_with_guidance(
    task: TaskInfo,
    ctx: JobContext,
    github: GitHubClient,
    model: str | None,
    state: JobState,
    human_guidance: str,
) -> None:
    """Retry a failed task with human guidance."""
    LOG.info("🔄 Retrying task: %s", task.title)

    for round_num in range(1, MAX_ROUNDS + 1):
        LOG.info("  🔄 Retry round %d/%d", round_num, MAX_ROUNDS)
        _cleanup_artifacts(ctx.working_dir)

        LOG.info("    💻 Developer coding (with human guidance)...")
        await run_generator(
            task_title=task.title,
            task_description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            round_number=round_num,
            working_dir=ctx.working_dir,
            model=model,
            human_guidance=human_guidance,
        )

        # Smart QA: run tests directly first, only spawn agent if needed
        passed, test_output = await _run_tests_with_check(ctx.working_dir)
        if passed:
            LOG.info("  ✅ GREEN — task approved on retry round %d", round_num)
            task.status = "completed"
            await _commit_task(ctx, task)
            if task.issue_number:
                github.close_issue(ctx.repo_name, task.issue_number)
            save_state(state)
            return

        # Tests failed — write feedback directly instead of spawning QA
        feedback_path = Path(ctx.working_dir) / "feedback.md"
        feedback_path.write_text(
            f"# Feedback — Retry Round {round_num}\n\n```\n{test_output}\n```\n"
        )
        LOG.warning("  🔴 RED — retry round %d failed", round_num)

    task.status = "failed"
    save_state(state)
    LOG.error("Task '%s' still failing after retry.", task.title)


def get_ready_batches(
    tasks: list[TaskInfo],
) -> Generator[list[TaskInfo], None, None]:
    """Yield batches of tasks whose dependencies are all complete."""
    completed: set[str] = set()
    remaining = list(tasks)

    for t in remaining[:]:
        if t.status == "completed":
            completed.add(t.id)
            remaining.remove(t)

    while remaining:
        batch = [t for t in remaining if all(d in completed for d in t.depends_on)]

        if not batch:
            pending_ids = [t.id for t in remaining]
            raise RuntimeError(f"Deadlock: no tasks ready. Remaining: {pending_ids}")

        yield batch

        for t in batch:
            completed.add(t.id)
            remaining.remove(t)


def get_ready_subtask_batches(
    subtasks: list[SubTaskInfo],
) -> Generator[list[SubTaskInfo], None, None]:
    """Yield batches of subtasks whose intra-task deps are complete."""
    completed: set[str] = set()
    remaining = list(subtasks)

    for s in remaining[:]:
        if s.status == "completed":
            completed.add(s.id)
            remaining.remove(s)

    while remaining:
        batch = [s for s in remaining if all(d in completed for d in s.depends_on)]

        if not batch:
            pending_ids = [s.id for s in remaining]
            raise RuntimeError(f"Subtask deadlock: {pending_ids}")

        yield batch

        for s in batch:
            completed.add(s.id)
            remaining.remove(s)


async def _process_task_with_subtasks(
    task: TaskInfo,
    ctx: JobContext,
    github: GitHubClient,
    model: str | None,
    state: JobState,
    emitter: EventEmitter | None = None,
) -> None:
    """Process a parent task by running subtasks in parallel via git worktrees."""
    LOG.info("🔧 Task (with subtasks): %s", task.title)
    if emitter:
        await emitter.emit_task_started(task.id)

    for sub_batch in get_ready_subtask_batches(task.subtasks):
        if len(sub_batch) == 1:
            # Single subtask — no worktree overhead needed
            subtask = sub_batch[0]
            LOG.info("  🔹 Subtask: %s", subtask.title)
            pseudo_task = TaskInfo(
                id=subtask.id,
                title=subtask.title,
                description=subtask.description,
                acceptance_criteria=subtask.acceptance_criteria,
                depends_on=subtask.depends_on,
            )
            await _process_task(
                pseudo_task, ctx, github, model, state, emitter,
            )
            subtask.status = pseudo_task.status
            save_state(state)
            if subtask.status == "failed":
                task.status = "failed"
                save_state(state)
                LOG.error(
                    "Subtask '%s' failed — stopping parent '%s'",
                    subtask.title, task.title,
                )
                return
        else:
            # Multiple independent subtasks — run in parallel via worktrees
            LOG.info(
                "  🌳 Running %d subtasks in parallel (worktrees)",
                len(sub_batch),
            )
            if emitter:
                names = ", ".join(s.title for s in sub_batch)
                await emitter.emit_log(
                    task.id,
                    f"🌳 Parallel subtasks via worktrees: {names}",
                )

            results = await _run_subtasks_parallel(
                sub_batch, ctx, github, model, state, emitter,
            )

            # Check results
            for subtask, status in results:
                subtask.status = status
                save_state(state)
                if status == "failed":
                    task.status = "failed"
                    save_state(state)
                    LOG.error(
                        "Subtask '%s' failed — stopping parent '%s'",
                        subtask.title, task.title,
                    )
                    return

    # All subtasks completed
    task.status = "completed"
    if emitter:
        await emitter.emit_task_completed(task.id)
    save_state(state)
    LOG.info("✅ All subtasks complete for '%s'", task.title)


async def _run_subtasks_parallel(
    subtasks: list[SubTaskInfo],
    ctx: JobContext,
    github: GitHubClient,
    model: str | None,
    state: JobState,
    emitter: EventEmitter | None = None,
) -> list[tuple[SubTaskInfo, str]]:
    """Run subtasks in parallel using git worktrees.

    Each subtask gets its own worktree (separate directory, same repo).
    After all complete, merge their changes back to the task branch.
    """
    import shutil
    import tempfile

    worktrees: list[tuple[SubTaskInfo, str, str]] = []  # (subtask, dir, branch)

    # Create a worktree per subtask
    for subtask in subtasks:
        wt_dir = tempfile.mkdtemp(prefix=f"df-wt-{subtask.id}-")
        wt_branch = f"wt-{subtask.id}"

        # Delete stale branch if it exists (from previous runs)
        proc = await asyncio.create_subprocess_exec(
            "git", "branch", "-D", wt_branch,
            cwd=ctx.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        # Create worktree from current branch
        proc = await asyncio.create_subprocess_exec(
            "git", "worktree", "add", "-b", wt_branch, wt_dir,
            cwd=ctx.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode != 0:
            LOG.warning(
                "Failed to create worktree for %s — falling back to sequential",
                subtask.id,
            )
            # Cleanup and fall back
            shutil.rmtree(wt_dir, ignore_errors=True)
            return await _run_subtasks_sequential(
                subtasks, ctx, github, model, state, emitter,
            )

        # Copy CLAUDE.md security policy to worktree
        claude_md = Path(ctx.working_dir) / "CLAUDE.md"
        if claude_md.exists():
            shutil.copy2(claude_md, Path(wt_dir) / "CLAUDE.md")

        # Install frontend deps in worktree if needed
        await _install_frontend_deps(wt_dir)

        worktrees.append((subtask, wt_dir, wt_branch))
        LOG.info("  🌳 Worktree for %s: %s", subtask.id, wt_dir)

    # Run all subtasks in parallel
    async def _run_one(
        subtask: SubTaskInfo, wt_dir: str,
    ) -> tuple[SubTaskInfo, str]:
        LOG.info("  🔹 Subtask (parallel): %s", subtask.title)
        pseudo_task = TaskInfo(
            id=subtask.id,
            title=subtask.title,
            description=subtask.description,
            acceptance_criteria=subtask.acceptance_criteria,
            depends_on=subtask.depends_on,
        )
        # Create a temporary ctx pointing at the worktree
        wt_ctx = JobContext(
            repo_name=ctx.repo_name,
            issue_number=ctx.issue_number,
            working_dir=wt_dir,
            branch=ctx.branch,
            tasks=ctx.tasks,
        )
        await _process_task(
            pseudo_task, wt_ctx, github, model, state, emitter,
        )
        return subtask, pseudo_task.status

    results = await asyncio.gather(
        *[_run_one(st, wt_dir) for st, wt_dir, _ in worktrees]
    )

    # Merge worktree changes back to main working dir
    for subtask, wt_dir, wt_branch in worktrees:
        matched_status = next(
            st_s for st, st_s in results if st.id == subtask.id
        )
        if matched_status == "completed":
            # Cherry-pick commits from worktree branch
            proc = await asyncio.create_subprocess_exec(
                "git", "merge", wt_branch, "--no-edit",
                cwd=ctx.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                LOG.warning(
                    "Merge conflict from worktree %s — attempting auto-resolve",
                    subtask.id,
                )
                # Try to auto-resolve by accepting theirs
                proc = await asyncio.create_subprocess_exec(
                    "git", "merge", "--abort",
                    cwd=ctx.working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                # Fall back: apply their changes with strategy
                proc = await asyncio.create_subprocess_exec(
                    "git", "merge", wt_branch,
                    "-X", "theirs", "--no-edit",
                    cwd=ctx.working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()

        # Cleanup worktree
        proc = await asyncio.create_subprocess_exec(
            "git", "worktree", "remove", wt_dir, "--force",
            cwd=ctx.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        # Delete temp branch
        proc = await asyncio.create_subprocess_exec(
            "git", "branch", "-D", wt_branch,
            cwd=ctx.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        shutil.rmtree(wt_dir, ignore_errors=True)

    return list(results)


async def _run_subtasks_sequential(
    subtasks: list[SubTaskInfo],
    ctx: JobContext,
    github: GitHubClient,
    model: str | None,
    state: JobState,
    emitter: EventEmitter | None = None,
) -> list[tuple[SubTaskInfo, str]]:
    """Fallback: run subtasks sequentially (no worktrees)."""
    results: list[tuple[SubTaskInfo, str]] = []
    for subtask in subtasks:
        pseudo_task = TaskInfo(
            id=subtask.id,
            title=subtask.title,
            description=subtask.description,
            acceptance_criteria=subtask.acceptance_criteria,
            depends_on=subtask.depends_on,
        )
        await _process_task(
            pseudo_task, ctx, github, model, state, emitter,
        )
        subtask.status = pseudo_task.status
        save_state(state)
        results.append((subtask, pseudo_task.status))
        if pseudo_task.status == "failed":
            break
    return results


async def _process_task(
    task: TaskInfo,
    ctx: JobContext,
    github: GitHubClient,
    model: str | None,
    state: JobState,
    emitter: EventEmitter | None = None,
) -> None:
    """Run the full red-green cycle for a single task."""
    # Adaptive model: use complexity-based model if no explicit --model
    effective_model = model or COMPLEXITY_MODELS.get(task.complexity, "sonnet")
    LOG.info(
        "🔧 Task: %s (complexity=%s, model=%s)",
        task.title, task.complexity, effective_model,
    )
    if emitter:
        await emitter.emit_task_started(task.id)

    # Phase 0+1: Combined contracts+tests with parallel scaffold
    # Uses a single QA agent for contracts AND tests (saves one agent spawn)
    LOG.info("  ⚡ QA (contracts+tests) + Developer scaffold (parallel)...")
    if emitter:
        await emitter.emit_log(
            task.id,
            "⚡ QA contracts+tests + Developer scaffold (parallel)",
        )
        await emitter.emit_agent_spawned(task.id, "QA Engineer (RED)")
        await emitter.emit_agent_spawned(task.id, "Developer (scaffold)")
    await asyncio.gather(
        run_evaluator_contracts_and_tests(
            task_title=task.title,
            task_description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            working_dir=ctx.working_dir,
            model=effective_model,
        ),
        run_generator_scaffold(
            task_title=task.title,
            task_description=task.description,
            working_dir=ctx.working_dir,
            model=effective_model,
        ),
    )

    # Pre-check: does the code already satisfy the tests?
    # If someone already implemented this feature (or a previous run
    # was canceled after merging), skip the Developer entirely.
    pre_passed, _ = await _run_tests_with_check(ctx.working_dir)
    if pre_passed:
        LOG.info("  ⏭️ Tests already pass — feature exists, skipping Developer")
        if emitter:
            await emitter.emit_log(
                task.id,
                "⏭️ Tests already pass — skipping Developer",
                "success",
            )
            await emitter.emit_round_result(task.id, 0, passed=True)
            await emitter.emit_task_completed(task.id)
        task.status = "completed"
        await _commit_task(ctx, task)
        if task.issue_number:
            github.close_issue(ctx.repo_name, task.issue_number)
        save_state(state)
        return

    # Phase 2-3: Red-Green loop with smart QA
    for round_num in range(1, MAX_ROUNDS + 1):
        LOG.info("  🔄 Round %d/%d", round_num, MAX_ROUNDS)
        _cleanup_artifacts(ctx.working_dir)

        # Developer writes code
        LOG.info("    💻 Developer coding...")
        if emitter:
            await emitter.emit_log(
                task.id,
                f"🔄 Round {round_num}/{MAX_ROUNDS} — Developer coding...",
            )
            await emitter.emit_agent_spawned(task.id, "Developer")
        await run_generator(
            task_title=task.title,
            task_description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            round_number=round_num,
            working_dir=ctx.working_dir,
            model=effective_model,
        )

        # Smart QA: run tests directly first
        passed, test_output = await _run_tests_with_check(ctx.working_dir)

        if passed:
            # Tests pass — quick approve, no need to spawn QA agent
            LOG.info("  ✅ GREEN — all tests pass on round %d", round_num)
            if emitter:
                await emitter.emit_log(
                    task.id,
                    f"✅ GREEN — all tests pass on round {round_num}",
                    "success",
                )
            if emitter:
                await emitter.emit_round_result(task.id, round_num, passed=True)
                await emitter.emit_task_completed(task.id)
                await emitter.emit_agent_exited(task.id, "Developer", success=True)
            task.status = "completed"
            await _commit_task(ctx, task)
            if task.issue_number:
                github.close_issue(ctx.repo_name, task.issue_number)
            save_state(state)
            return

        # Smart retry: analyze failure to provide targeted feedback
        failure_hint = _analyze_failure(test_output)
        if failure_hint:
            LOG.info("    🧠 Failure analysis: %s", failure_hint[:80])

        # For obvious errors (import, syntax, missing dep), write feedback
        # directly instead of spawning a full QA review agent
        feedback_path = Path(ctx.working_dir) / "feedback.md"
        approved_path = Path(ctx.working_dir) / "approved.md"

        if failure_hint:
            LOG.info("    📝 Writing targeted feedback (skipping QA agent)")
            if emitter:
                await emitter.emit_log(
                    task.id,
                    f"🧠 Smart feedback round {round_num}: {failure_hint[:60]}",
                )
            feedback_path.write_text(
                f"# Feedback — Round {round_num}\n\n"
                f"## Analysis\n{failure_hint}\n\n"
                f"## Raw Output\n```\n{test_output[-1500:]}\n```\n"
            )
        else:
            # Complex failure — spawn QA for detailed review
            LOG.info("    🔍 Tests failed — spawning QA for feedback...")
            if emitter:
                await emitter.emit_log(
                    task.id,
                    f"🔍 Tests failed round {round_num} — QA reviewing...",
                )
                await emitter.emit_agent_spawned(task.id, "QA Engineer (Review)")
            await run_evaluator_review(
                task_title=task.title,
                round_number=round_num,
                working_dir=ctx.working_dir,
                model=effective_model,
            )

        # QA might approve despite test failures (e.g., flaky tests)
        if approved_path.exists():
            LOG.info("  ✅ GREEN — QA approved on round %d", round_num)
            if emitter:
                await emitter.emit_round_result(task.id, round_num, passed=True)
                await emitter.emit_task_completed(task.id)
                await emitter.emit_agent_exited(task.id, "Developer", success=True)
            task.status = "completed"
            await _commit_task(ctx, task)
            if task.issue_number:
                github.close_issue(ctx.repo_name, task.issue_number)
            save_state(state)
            return

        if not feedback_path.exists():
            feedback_path.write_text(
                f"# Feedback — Round {round_num}\n\n"
                f"Test output:\n\n```\n{test_output}\n```\n"
            )

        if emitter:
            await emitter.emit_log(
                task.id,
                f"🔴 RED — round {round_num} failed",
                "failure",
            )
            await emitter.emit_round_result(task.id, round_num, passed=False)
            await emitter.emit_agent_exited(task.id, "QA Engineer", success=False)
        LOG.warning("  🔴 RED — round %d failed", round_num)

    if emitter:
        await emitter.emit_task_failed(task.id)
        await emitter.emit_agent_exited(task.id, "Developer", success=False)
    task.status = "failed"
    save_state(state)
    LOG.error(
        "Task '%s' failed after %d rounds. Will escalate to human.",
        task.title,
        MAX_ROUNDS,
    )


async def _process_batch_parallel(
    batch: list[TaskInfo],
    ctx: JobContext,
    github: GitHubClient,
    model: str | None,
    state: JobState,
) -> None:
    """Process a batch of independent tasks in parallel."""
    coros = [_process_task(task, ctx, github, model, state) for task in batch]
    await asyncio.gather(*coros)


async def _process_single_task_in_batch(
    task: TaskInfo,
    ctx: JobContext,
    github: GitHubClient,
    model: str | None,
    state: JobState,
    emitter: EventEmitter,
    repo_name: str,
    issue_number: int,
) -> None:
    """Process a single task: skip check, red-green cycle, PR, merge."""
    await _checkout_main(ctx)
    await _pull_latest(ctx)

    if await _is_task_already_done(task, ctx, issue_number, github):
        LOG.info("⏭️ Skipping '%s' — already complete", task.title)
        await emitter.emit_log(
            task.id, f"⏭️ Skipping '{task.title}' — already complete"
        )
        task.status = "completed"
        if task.issue_number:
            github.close_issue(ctx.repo_name, task.issue_number)
        save_state(state)
        return

    task_branch = f"factory/issue-{issue_number}/{task.id}"
    await _create_branch_from(ctx, task_branch)

    if task.has_subtasks:
        await _process_task_with_subtasks(
            task, ctx, github, model, state, emitter,
        )
    else:
        await _process_task(
            task, ctx, github, model, state, emitter,
        )

    await _finalize_task(
        task, ctx, github, emitter, state,
        repo_name, issue_number, task_branch,
    )


async def _process_batch_with_worktrees(
    batch: list[TaskInfo],
    ctx: JobContext,
    github: GitHubClient,
    model: str | None,
    state: JobState,
    emitter: EventEmitter,
    repo_name: str,
    issue_number: int,
) -> None:
    """Process a batch of independent tasks in parallel via git worktrees."""
    import shutil
    import tempfile

    LOG.info(
        "🌳 Running %d tasks in parallel (worktrees)", len(batch),
    )
    await emitter.emit_log(
        f"{repo_name}#{issue_number}",
        f"🌳 {len(batch)} tasks in parallel via worktrees",
    )

    # First, check for already-done tasks
    await _checkout_main(ctx)
    await _pull_latest(ctx)

    active_tasks: list[TaskInfo] = []
    for task in batch:
        if await _is_task_already_done(task, ctx, issue_number, github):
            LOG.info("⏭️ Skipping '%s' — already complete", task.title)
            task.status = "completed"
            if task.issue_number:
                github.close_issue(ctx.repo_name, task.issue_number)
            save_state(state)
        else:
            active_tasks.append(task)

    if not active_tasks:
        return

    # Create worktrees for each active task
    worktree_info: list[tuple[TaskInfo, str, str]] = []
    for task in active_tasks:
        wt_dir = tempfile.mkdtemp(prefix=f"df-wt-{task.id}-")
        task_branch = f"factory/issue-{issue_number}/{task.id}"

        # Delete stale branch if it exists (from previous runs)
        proc = await asyncio.create_subprocess_exec(
            "git", "branch", "-D", task_branch,
            cwd=ctx.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()  # ignore errors — branch may not exist

        proc = await asyncio.create_subprocess_exec(
            "git", "worktree", "add", "-b", task_branch, wt_dir,
            cwd=ctx.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode != 0:
            LOG.warning(
                "Failed to create worktree for %s — falling back to sequential",
                task.id,
            )
            shutil.rmtree(wt_dir, ignore_errors=True)
            # Fall back to sequential
            for t in active_tasks:
                await _process_single_task_in_batch(
                    t, ctx, github, model, state, emitter,
                    repo_name, issue_number,
                )
            return

        # Copy CLAUDE.md to worktree
        claude_md = Path(ctx.working_dir) / "CLAUDE.md"
        if claude_md.exists():
            shutil.copy2(claude_md, Path(wt_dir) / "CLAUDE.md")

        # Install frontend deps in worktree if needed
        await _install_frontend_deps(wt_dir)

        worktree_info.append((task, wt_dir, task_branch))

    # Run all tasks in parallel
    async def _run_task_in_worktree(
        task: TaskInfo, wt_dir: str,
    ) -> None:
        wt_ctx = JobContext(
            repo_name=ctx.repo_name,
            issue_number=ctx.issue_number,
            working_dir=wt_dir,
            branch=ctx.branch,
            tasks=ctx.tasks,
        )
        if task.has_subtasks:
            await _process_task_with_subtasks(
                task, wt_ctx, github, model, state, emitter,
            )
        else:
            await _process_task(
                task, wt_ctx, github, model, state, emitter,
            )

    await asyncio.gather(
        *[_run_task_in_worktree(t, wt_dir) for t, wt_dir, _ in worktree_info]
    )

    # Push and merge completed tasks sequentially (each merge
    # changes main, so subsequent tasks must rebase first)
    for task, wt_dir, task_branch in worktree_info:
        # Pull latest main into worktree and rebase task branch
        proc = await asyncio.create_subprocess_exec(
            "git", "fetch", "origin", "main",
            cwd=wt_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        proc = await asyncio.create_subprocess_exec(
            "git", "rebase", "origin/main",
            cwd=wt_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            LOG.warning(
                "Rebase failed for %s — recreating branch from main",
                task_branch,
            )
            await asyncio.create_subprocess_exec(
                "git", "rebase", "--abort",
                cwd=wt_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # Get the task's commits (not on origin/main)
            proc = await asyncio.create_subprocess_exec(
                "git", "log", "origin/main..HEAD",
                "--format=%H", "--reverse",
                cwd=wt_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            commits = stdout.decode().strip().splitlines()

            # Reset to origin/main and cherry-pick commits
            await asyncio.create_subprocess_exec(
                "git", "reset", "--hard", "origin/main",
                cwd=wt_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            for commit_hash in commits:
                proc = await asyncio.create_subprocess_exec(
                    "git", "cherry-pick", commit_hash,
                    cwd=wt_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode != 0:
                    # Skip conflicting commit, accept theirs
                    await asyncio.create_subprocess_exec(
                        "git", "cherry-pick", "--abort",
                        cwd=wt_dir,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    LOG.warning(
                        "Skipped conflicting commit %s for %s",
                        commit_hash[:8], task_branch,
                    )

        wt_ctx = JobContext(
            repo_name=ctx.repo_name,
            issue_number=ctx.issue_number,
            working_dir=wt_dir,
            branch=task_branch,
            tasks=ctx.tasks,
        )
        await _finalize_task(
            task, wt_ctx, github, emitter, state,
            repo_name, issue_number, task_branch,
        )

        # Remove worktree
        proc = await asyncio.create_subprocess_exec(
            "git", "worktree", "remove", wt_dir, "--force",
            cwd=ctx.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        shutil.rmtree(wt_dir, ignore_errors=True)

    # Pull latest after all merges
    await _checkout_main(ctx)
    await _pull_latest(ctx)


async def _finalize_task(
    task: TaskInfo,
    ctx: JobContext,
    github: GitHubClient,
    emitter: EventEmitter,
    state: JobState,
    repo_name: str,
    issue_number: int,
    task_branch: str,
) -> None:
    """Push, PR, and merge a completed task — or create draft PR for failures."""
    if task.status == "completed":
        await _push_branch(ctx, task_branch)
        pr = github.create_pr(
            repo_name=repo_name,
            branch=task_branch,
            title=f"feat: {task.title}",
            body=(
                f"Part of #{issue_number}\n\n"
                f"Task: {task.id}\n\n"
                f"## What this does\n{task.description}"
            ),
        )
        LOG.info("🚀 Opened PR #%d for %s", pr.number, task.title)
        await emitter.emit_log(
            task.id,
            f"🚀 Opened PR #{pr.number} for {task.title}",
        )

        github.merge_pr(repo_name, pr.number)
        LOG.info("✅ Merged PR #%d", pr.number)
        await emitter.emit_log(
            task.id, f"✅ Merged PR #{pr.number}", "success"
        )

        if task.issue_number:
            github.close_issue(repo_name, task.issue_number)
        save_state(state)

    elif task.status == "failed":
        await _push_branch(ctx, task_branch)
        pr = github.create_draft_pr(
            repo_name=repo_name,
            branch=task_branch,
            title=f"draft: {task.title}",
            body=(
                f"Part of #{issue_number}\n\n"
                f"Task: {task.id} — **failed after {MAX_ROUNDS} rounds**\n\n"
                f"## What this does\n{task.description}"
            ),
        )
        feedback = _read_feedback(ctx.working_dir)
        failure_issue = github.create_failure_issue(
            repo_name=repo_name,
            parent_issue=issue_number,
            pr_number=pr.number,
            task=task,
            feedback=feedback,
            round_count=MAX_ROUNDS,
        )
        task.failure_issue = failure_issue.number
        await emitter.emit_log(
            task.id,
            f"⚠️ Task '{task.title}' failed — draft PR #{pr.number}, "
            f"needs-human #{failure_issue.number}",
            "failure",
        )
        LOG.warning(
            "⚠️ Task '%s' failed — draft PR #%d, needs-human issue #%d",
            task.title,
            pr.number,
            failure_issue.number,
        )
        save_state(state)


def _auto_cleanup_sub_issues(
    github: GitHubClient,
    repo_name: str,
    parent_issue: int,
) -> None:
    """Close all sub-issues and needs-human issues for a parent."""
    try:
        repo = github.get_repo(repo_name)
        label = f"issue-{parent_issue}"
        for issue in repo.get_issues(
            state="open", labels=["auto-generated", label]
        ):
            issue.edit(state="closed", state_reason="completed")
        for issue in github.find_needs_human_issues(
            repo_name, parent_issue
        ):
            issue.edit(state="closed", state_reason="completed")
        LOG.info(
            "🧹 Auto-closed sub-issues for #%d", parent_issue
        )
    except Exception as exc:
        LOG.warning(
            "Could not auto-close sub-issues for #%d: %s",
            parent_issue,
            exc,
        )


def _load_tasks(working_dir: str) -> list[TaskInfo]:
    """Load tasks.json written by the Architect."""
    tasks_path = Path(working_dir) / "tasks.json"
    if not tasks_path.exists():
        raise FileNotFoundError(f"Architect didn't create tasks.json in {working_dir}")

    raw = json.loads(tasks_path.read_text())
    all_ids: set[str] = set()
    tasks: list[TaskInfo] = []

    for t in raw:
        task_id = t["id"]
        if task_id in all_ids:
            raise ValueError(f"Duplicate task ID: {task_id}")
        all_ids.add(task_id)

        subtasks: list[SubTaskInfo] = []
        for s in t.get("subtasks", []):
            sub_id = s["id"]
            if sub_id in all_ids:
                raise ValueError(f"Duplicate subtask ID: {sub_id}")
            all_ids.add(sub_id)
            subtasks.append(
                SubTaskInfo(
                    id=sub_id,
                    title=s["title"],
                    description=s.get("description", ""),
                    acceptance_criteria=s.get("acceptance_criteria", []),
                    depends_on=s.get("depends_on", []),
                )
            )

        tasks.append(
            TaskInfo(
                id=task_id,
                title=t["title"],
                description=t.get("description", ""),
                acceptance_criteria=t.get("acceptance_criteria", []),
                depends_on=t.get("depends_on", []),
                subtasks=subtasks,
                complexity=t.get("complexity", "medium"),
            )
        )

    return tasks


def _read_feedback(working_dir: str) -> str:
    """Read feedback.md if it exists."""
    path = Path(working_dir) / "feedback.md"
    if path.exists():
        return path.read_text()
    return "No feedback file found."


async def _post_merge_validation(
    ctx: JobContext,
    model: str | None = None,
    max_fix_attempts: int = 2,
) -> bool:
    """Run make test + make check on final merged main.

    If validation fails, spawn Developer to fix cross-task issues
    (missing deps, import errors, lint). Commits fixes directly
    to main.
    """
    for attempt in range(1, max_fix_attempts + 1):
        passed, output = await _run_tests_with_check(ctx.working_dir)
        if passed:
            if attempt > 1:
                LOG.info(
                    "🩹 Post-merge self-healed after %d attempt(s)",
                    attempt - 1,
                )
            return True

        if attempt < max_fix_attempts:
            LOG.warning(
                "🩹 Post-merge validation failed — "
                "spawning Developer to fix (attempt %d/%d)",
                attempt,
                max_fix_attempts - 1,
            )
            await run_generator(
                task_title="Fix post-merge validation failures",
                task_description=(
                    "All tasks were merged but the final "
                    "make test + make check fails. "
                    "Fix the issues below. You MAY edit any "
                    "file — tests, source, config, deps.\n\n"
                    f"## Failure Output\n\n```\n{output}\n```"
                ),
                acceptance_criteria=[
                    "make test passes",
                    "make check passes",
                ],
                round_number=1,
                working_dir=ctx.working_dir,
                model=model,
            )
            # Commit and push the fix
            proc = await asyncio.create_subprocess_exec(
                "git",
                "add",
                "-A",
                cwd=ctx.working_dir,
            )
            await proc.wait()
            proc = await asyncio.create_subprocess_exec(
                "git",
                "commit",
                "-m",
                "fix: post-merge validation — auto-heal",
                "--allow-empty",
                cwd=ctx.working_dir,
            )
            await proc.wait()
            await _push_changes(ctx)
        else:
            LOG.error(
                "💥 Post-merge validation still failing after %d fix attempt(s)",
                max_fix_attempts - 1,
            )
            return False

    return False


def _is_simple_issue(title: str, body: str) -> bool:
    """Detect if an issue is simple enough to skip the Architect.

    Simple issues: bug fixes, single endpoints, config changes,
    small features that don't need task decomposition.
    """
    simple_keywords = [
        "fix",
        "bug",
        "typo",
        "rename",
        "update",
        "add endpoint",
        "remove",
        "bump",
    ]
    text = f"{title} {body}".lower()

    # Short body = simple issue
    if len(body) < 200:
        for keyword in simple_keywords:
            if keyword in text:
                return True

    return False


async def _has_tests(working_dir: str) -> bool:
    """Check if the repo has existing test files."""
    tests_dir = Path(working_dir) / "tests"
    if not tests_dir.exists():
        return False
    test_files = list(tests_dir.glob("test_*.py"))
    return len(test_files) > 0


async def _regression_gate_with_healing(
    ctx: JobContext,
    model: str | None = None,
    max_heal_attempts: int = 2,
) -> None:
    """Run regression gate. If it fails, spawn Developer to fix.

    Self-healing: instead of dying on broken tests, give the
    Developer a chance to fix them (missing deps, dirs, imports).
    """
    for attempt in range(1, max_heal_attempts + 1):
        await run_evaluator_regression(
            working_dir=ctx.working_dir,
            model="haiku",
        )
        regression_fail = Path(ctx.working_dir) / "regression-fail.md"
        if not regression_fail.exists():
            _cleanup_file(ctx.working_dir, "regression-pass.md")
            if attempt > 1:
                LOG.info(
                    "🩹 Self-healed after %d attempt(s)",
                    attempt - 1,
                )
            return  # Tests pass — continue

        if attempt < max_heal_attempts:
            feedback = regression_fail.read_text()
            LOG.warning(
                "🩹 Regression gate failed — "
                "spawning Developer to self-heal (attempt %d/%d)",
                attempt,
                max_heal_attempts - 1,
            )
            _cleanup_file(ctx.working_dir, "regression-fail.md")
            await run_generator(
                task_title="Fix broken regression tests",
                task_description=(
                    "The regression gate found broken tests. "
                    "Fix the issues described below. "
                    "You MAY fix test files, source files, "
                    "config files, or add missing deps.\n\n"
                    f"## Failure Details\n\n{feedback}"
                ),
                acceptance_criteria=[
                    "All existing tests pass",
                    "make test exits with code 0",
                ],
                round_number=1,
                working_dir=ctx.working_dir,
                model=model,
            )

            # Regression scope guard: check what the fix touched
            changed = await _get_changed_files(ctx.working_dir)
            scope_ok, scope_reason = await check_regression_scope(
                ctx.working_dir,
                changed,
            )
            if not scope_ok:
                LOG.error("🚫 Regression scope guard: %s", scope_reason)
                raise RuntimeError(
                    f"Regression fix exceeded scope limits. {scope_reason}"
                )

            # Commit the fix
            proc = await asyncio.create_subprocess_exec(
                "git",
                "add",
                "-A",
                cwd=ctx.working_dir,
            )
            await proc.wait()
            proc = await asyncio.create_subprocess_exec(
                "git",
                "commit",
                "-m",
                "fix: self-heal broken regression tests",
                cwd=ctx.working_dir,
            )
            await proc.wait()
        else:
            LOG.error(
                "💥 Regression gate FAILED after %d heal attempt(s)",
                max_heal_attempts - 1,
            )
            raise RuntimeError(
                "Regression gate failed. "
                "Fix existing tests before adding "
                "new features. "
                f"See: {regression_fail}"
            )


async def _run_tests_with_check(
    working_dir: str,
    test_file: str | None = None,
) -> tuple[bool, str]:
    """Run tests + lint directly. Returns (passed, output).

    If test_file is provided, only run that file first for speed.
    If it passes, run the full suite to catch regressions.
    """
    # Run targeted tests first (fast)
    if test_file:
        test_path = Path(working_dir) / test_file
        if test_path.exists():
            proc = await asyncio.create_subprocess_exec(
                "uv",
                "run",
                "pytest",
                test_file,
                "-v",
                "--tb=short",
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                return False, stdout.decode()[-2000:]

    # Run full test suite
    test_proc = await asyncio.create_subprocess_exec(
        "make",
        "test",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    test_stdout, _ = await asyncio.wait_for(test_proc.communicate(), timeout=120)
    test_output = test_stdout.decode()[-2000:]

    if test_proc.returncode != 0:
        return False, test_output

    # Auto-fix lint in test files before checking.
    # QA writes tests and sometimes introduces lint errors
    # that the Developer cannot fix (test files are off-limits).
    await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "ruff",
        "check",
        "--fix",
        "tests/",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "ruff",
        "format",
        "tests/",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    # Run check (lint + types)
    check_proc = await asyncio.create_subprocess_exec(
        "make",
        "check",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    check_stdout, _ = await asyncio.wait_for(
        check_proc.communicate(),
        timeout=120,
    )
    check_output = check_stdout.decode()[-2000:]

    if check_proc.returncode != 0:
        return (
            False,
            f"Tests passed but lint/type check failed:\n{check_output}",
        )

    return True, test_output


async def _install_frontend_deps(working_dir: str) -> None:
    """Find any package.json files and run npm install.

    Searches common frontend locations. Skips if npm is not
    installed or if node_modules already exists.
    """
    import shutil

    if not shutil.which("npm"):
        return

    search_dirs = [
        Path(working_dir),
        Path(working_dir) / "dashboard" / "frontend",
        Path(working_dir) / "frontend",
    ]

    for d in search_dirs:
        pkg = d / "package.json"
        modules = d / "node_modules"
        if pkg.exists() and not modules.exists():
            LOG.info("📦 Installing npm deps in %s", d.name)
            proc = await asyncio.create_subprocess_exec(
                "npm",
                "install",
                cwd=str(d),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(
                proc.communicate(),
                timeout=120,
            )
            if proc.returncode == 0:
                LOG.info("📦 npm install complete in %s", d.name)
            else:
                LOG.warning(
                    "⚠️ npm install failed in %s (exit %d)",
                    d.name,
                    proc.returncode or -1,
                )


async def _clone_repo(github: GitHubClient, ctx: JobContext) -> str:
    """Clone the target repo into a temp directory."""
    import tempfile

    work_dir = tempfile.mkdtemp(prefix="dark-factory-")
    clone_url = f"https://{github.token}@github.com/{github.owner}/{ctx.repo_name}.git"

    proc = await asyncio.create_subprocess_exec(
        "git",
        "clone",
        clone_url,
        work_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to clone {ctx.repo_name}")

    LOG.info("Cloned %s to %s", ctx.repo_name, work_dir)

    # Install frontend deps if a package.json exists
    await _install_frontend_deps(work_dir)

    return work_dir


async def _checkout_main(ctx: JobContext) -> None:
    """Switch back to main branch."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "checkout",
        "main",
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _pull_latest(ctx: JobContext) -> None:
    """Pull latest changes from origin main."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "pull",
        "origin",
        "main",
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _create_branch_from(ctx: JobContext, branch_name: str) -> None:
    """Create and checkout a new branch from current HEAD."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "checkout",
        "-b",
        branch_name,
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _push_branch(ctx: JobContext, branch_name: str) -> None:
    """Push a specific branch to origin."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "push",
        "-u",
        "origin",
        branch_name,
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _commit_task(ctx: JobContext, task: TaskInfo) -> None:
    """Commit all changes for a completed task."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "add",
        "-A",
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    proc = await asyncio.create_subprocess_exec(
        "git",
        "commit",
        "-m",
        f"feat: {task.title}\n\nTask: {task.id}",
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _push_changes(ctx: JobContext) -> None:
    """Push the feature branch to origin."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "push",
        "-u",
        "origin",
        ctx.branch,
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _is_task_already_done(
    task: TaskInfo,
    ctx: JobContext,
    issue_number: int,
    github: GitHubClient,
) -> bool:
    """Check if a task is already complete before running it.

    Two checks:
    1. Git: was the task branch already merged to main?
    2. Tests: do existing tests already pass on current main?

    Returns True if the task can be safely skipped.
    """
    # Check 1: was the task branch already merged?
    branch_name = f"factory/issue-{issue_number}/{task.id}"
    proc = await asyncio.create_subprocess_exec(
        "git",
        "branch",
        "-r",
        "--merged",
        "main",
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    merged_branches = stdout.decode()
    if f"origin/{branch_name}" in merged_branches:
        LOG.info(
            "  Branch %s already merged to main",
            branch_name,
        )
        return True

    # Check 2: was the corresponding GitHub sub-issue already closed?
    if task.issue_number:
        try:
            repo = github.get_repo(ctx.repo_name)
            issue = repo.get_issue(task.issue_number)
            if issue.state == "closed":
                LOG.info(
                    "  Sub-issue #%d already closed",
                    task.issue_number,
                )
                return True
        except Exception:
            pass  # If we can't check, don't skip

    # Check 3: do existing tests pass? (only meaningful if tests exist
    # for this task — check if test files reference the task's feature)
    tests_dir = Path(ctx.working_dir) / "tests"
    if tests_dir.exists():
        # Look for test files that might be related to this task
        task_keywords = task.title.lower().split()
        related_tests = []
        for test_file in tests_dir.glob("test_*.py"):
            name = test_file.name.lower()
            if any(kw in name for kw in task_keywords if len(kw) > 3):
                related_tests.append(str(test_file))

        if related_tests:
            # Run just the related tests — if they pass, task is done
            passed, _ = await _run_tests_with_check(ctx.working_dir)
            if passed:
                LOG.info(
                    "  All tests pass on main — task already satisfied",
                )
                return True

    return False


async def _get_changed_files(working_dir: str) -> list[str]:
    """Get list of files changed in the working directory (staged + unstaged)."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "diff",
        "--name-only",
        "HEAD",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    # Also include untracked files
    proc2 = await asyncio.create_subprocess_exec(
        "git",
        "ls-files",
        "--others",
        "--exclude-standard",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout2, _ = await proc2.communicate()
    files = stdout.decode().splitlines() + stdout2.decode().splitlines()
    return [f for f in files if f.strip()]


def _analyze_failure(test_output: str) -> str | None:
    """Analyze test failure output and return a targeted fix hint.

    Returns None for complex failures that need full QA review.
    Returns a specific hint string for obvious/mechanical failures.
    """
    output_lower = test_output.lower()

    # Import errors — most common, easy to fix
    if "importerror" in output_lower or "modulenotfounderror" in output_lower:
        # Extract the module name
        import re

        match = re.search(
            r"(?:ImportError|ModuleNotFoundError): (?:No module named |"
            r"cannot import name )[\'\"]?([^\'\"\n]+)",
            test_output,
        )
        module = match.group(1) if match else "unknown"
        return (
            f"Import error: module '{module}' not found. "
            f"Check: 1) Is it installed in pyproject.toml? "
            f"2) Is the module path correct? "
            f"3) Is __init__.py missing?"
        )

    # Syntax errors
    if "syntaxerror" in output_lower:
        return (
            "Syntax error in source code. Check for: "
            "unclosed brackets, missing colons, invalid indentation, "
            "or f-string issues."
        )

    # Type errors (wrong args, missing params)
    if "typeerror" in output_lower:
        import re

        match = re.search(
            r"TypeError: ([^\n]+)", test_output,
        )
        detail = match.group(1) if match else ""
        return f"Type error: {detail}. Check function signatures match contracts.md."

    # Attribute errors (wrong method/property name)
    if "attributeerror" in output_lower:
        import re

        match = re.search(
            r"AttributeError: ([^\n]+)", test_output,
        )
        detail = match.group(1) if match else ""
        return f"Attribute error: {detail}. Check class/module API matches contracts."

    # File not found
    if "filenotfounderror" in output_lower:
        return (
            "File not found error. Check that all required files exist "
            "and paths are correct."
        )

    # Lint/type check failures (not test failures)
    if "make check" in output_lower and "error:" in output_lower:
        if "mypy" in output_lower:
            return (
                "mypy type check failures. Add missing type "
                "annotations or fix type mismatches."
            )
        if "ruff" in output_lower:
            return "ruff lint failures. Run 'ruff check --fix' patterns."

    # Missing commands / environment issues
    if "command not found" in output_lower or "not found" in output_lower:
        return (
            "Environment issue: a required command or package is missing. "
            "Check that all dependencies are installed (npm install, "
            "uv sync, etc.)."
        )

    # Complex failure — let QA handle it
    return None


def _cleanup_artifacts(working_dir: str) -> None:
    """Remove feedback.md and approved.md between rounds."""
    for name in ("feedback.md", "approved.md", "contracts.md"):
        _cleanup_file(working_dir, name)


def _cleanup_file(working_dir: str, filename: str) -> None:
    """Remove a single file if it exists."""
    path = Path(working_dir) / filename
    if path.exists():
        path.unlink()


async def _ensure_dashboard_running() -> None:
    """Start the dashboard server if it's not already running.

    Checks if port 8420 (or DASHBOARD_PORT) is responding.
    If not, starts uvicorn in the background. The dashboard
    stays running after the factory finishes.
    """
    import os
    import socket

    port = int(os.environ.get("DASHBOARD_PORT", "8420"))
    dashboard_url = os.environ.get("DASHBOARD_URL", "")

    # If DASHBOARD_URL is not set, configure it
    if not dashboard_url:
        os.environ["DASHBOARD_URL"] = f"http://localhost:{port}"

    # Check if already running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", port))
        if result == 0:
            LOG.info(
                "📊 Dashboard already running on port %d",
                port,
            )
            return
    finally:
        sock.close()

    # Start dashboard in background
    LOG.info("📊 Starting dashboard on port %d...", port)
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "uvicorn",
        "factory.dashboard.app:app",
        "--port",
        str(port),
        "--log-level",
        "warning",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,  # Survives parent exit
    )
    # Give it a moment to start
    await asyncio.sleep(1)
    if proc.returncode is not None:
        LOG.warning(
            "⚠️ Dashboard failed to start (exit %d) — continuing without it",
            proc.returncode,
        )
    else:
        LOG.info(
            "📊 Dashboard running at http://localhost:%d/docs",
            port,
        )


async def _check_claude_cli() -> None:
    """Verify claude CLI is installed and working before starting a job."""
    LOG.info("🏥 Running health check...")
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "-p",
            "Reply with OK",
            "--output-format",
            "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except FileNotFoundError:
        raise RuntimeError(
            "claude CLI not found. Install it: https://docs.anthropic.com/en/docs/claude-code"
        )
    except TimeoutError:
        raise RuntimeError("claude CLI health check timed out after 30s")

    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI returned exit code {proc.returncode}. "
            f"Make sure you're authenticated (run 'claude' to log in)."
        )

    LOG.info("✅ Health check passed — claude CLI is working")
