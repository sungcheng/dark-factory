"""Orchestrator — the dumb Python script that runs the factory.

No AI here. Just subprocess management, task ordering, and GitHub integration.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from factory.agents.evaluator import run_evaluator_contracts
from factory.agents.evaluator import run_evaluator_red
from factory.agents.evaluator import run_evaluator_regression
from factory.agents.evaluator import run_evaluator_review
from factory.agents.generator import run_generator
from factory.agents.generator import run_generator_scaffold
from factory.agents.planner import run_planner
from factory.github_client import GitHubClient
from factory.github_client import JobContext
from factory.github_client import TaskInfo
from factory.security import write_security_policy
from factory.state import JobState
from factory.state import load_state
from factory.state import save_state

LOG = logging.getLogger(__name__)

MAX_ROUNDS = 5


async def run_job(
    repo_name: str,
    issue_number: int,
    model: str | None = None,
) -> None:
    """Main orchestrator loop.

    1. Fetch issue from GitHub
    2. Spawn Architect to create tasks
    3. Run regression gate on existing tests
    4. Process tasks in dependency order (parallel where possible)
    5. For each task: QA writes tests -> Developer codes -> QA reviews
    6. If all pass: open PR and merge
    7. If any fail: open draft PR + create needs-human issues
    """
    # Health check — verify claude CLI works before doing anything
    await _check_claude_cli()

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

    LOG.info("🏭 Starting job for %s#%d", repo_name, issue_number)

    # Step 1: Fetch the issue
    issue = github.fetch_issue(repo_name, issue_number)
    LOG.info("📋 Fetched issue: %s", issue.title)

    # Step 2: Clone the repo (if not resuming)
    if not ctx.working_dir:
        ctx.working_dir = await _clone_repo(github, ctx)
        write_security_policy(ctx.working_dir)
        state.working_dir = ctx.working_dir
        save_state(state)

    # Step 3: Regression gate — verify existing tests pass
    LOG.info("🛡️ Running regression gate...")
    await run_evaluator_regression(
        working_dir=ctx.working_dir,
        model=model,
    )
    regression_fail = Path(ctx.working_dir) / "regression-fail.md"
    if regression_fail.exists():
        LOG.error("💥 Regression gate FAILED — existing tests are broken")
        raise RuntimeError(
            "Regression gate failed. Fix existing tests before adding new features. "
            f"See: {regression_fail}"
        )
    _cleanup_file(ctx.working_dir, "regression-pass.md")

    # Step 4: Spawn the Architect (if not resuming with tasks)
    if not ctx.tasks:
        LOG.info("🏗️ Spawning Architect...")
        planner_result = await run_planner(
            issue_title=issue.title,
            issue_body=issue.body or "",
            repo_name=repo_name,
            working_dir=ctx.working_dir,
            model=model,
        )

        tasks_path = Path(ctx.working_dir) / "tasks.json"
        if not planner_result.success and not tasks_path.exists():
            LOG.error("Architect failed (stderr): %s", planner_result.stderr)
            LOG.error("Architect failed (stdout): %s", planner_result.stdout[:500])
            raise RuntimeError("Architect agent failed")
        if not planner_result.success:
            LOG.warning("Architect exited with error but tasks.json exists — continuing")

        # Load tasks and create sub-issues
        ctx.tasks = _load_tasks(ctx.working_dir)
        ctx.tasks = github.create_sub_issues(repo_name, issue_number, ctx.tasks)
        state.tasks = ctx.tasks
        save_state(state)
        LOG.info("📝 Created %d tasks with GitHub sub-issues", len(ctx.tasks))

    # Step 5: Process tasks — each task gets its own branch, PR, merge
    for batch in get_ready_batches(ctx.tasks):
        batch_titles = [t.title for t in batch]
        LOG.info("📦 Processing batch: %s", batch_titles)

        for task in batch:
            # Create a branch from latest main
            task_branch = f"factory/issue-{issue_number}/{task.id}"
            await _checkout_main(ctx)
            await _pull_latest(ctx)
            await _create_branch_from(ctx, task_branch)

            # Run the red-green cycle
            await _process_task(task, ctx, github, model, state)

            if task.status == "completed":
                # Push, open PR, merge
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

                github.merge_pr(repo_name, pr.number)
                LOG.info("✅ Merged PR #%d", pr.number)

                if task.issue_number:
                    github.close_issue(repo_name, task.issue_number)

                save_state(state)

            elif task.status == "failed":
                # Push partial work, create needs-human issue
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
                LOG.warning(
                    "⚠️ Task '%s' failed — draft PR #%d, needs-human issue #%d",
                    task.title,
                    pr.number,
                    failure_issue.number,
                )
                save_state(state)

    # Step 6: Finalize
    completed = [t for t in ctx.tasks if t.status == "completed"]
    failed = [t for t in ctx.tasks if t.status == "failed"]

    if failed:
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
        github.close_issue(repo_name, issue_number)
        state.status = "completed"
        save_state(state)
        LOG.info("✅ All %d tasks complete. Issue #%d closed.", len(completed), issue_number)


async def retry_job(
    repo_name: str,
    issue_number: int,
    model: str | None = None,
) -> None:
    """Retry failed tasks using human guidance from GitHub issue comments.

    1. Load saved state
    2. Find needs-human issues with human comments
    3. Retry each failed task with human guidance injected into prompt
    4. If all pass: convert draft PR to ready, merge
    """
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

    LOG.info("Retrying failed tasks for %s#%d", repo_name, issue_number)

    # Find failed tasks and their human guidance
    failed_tasks = [t for t in ctx.tasks if t.status == "failed"]
    if not failed_tasks:
        LOG.info("No failed tasks to retry")
        return

    for task in failed_tasks:
        # Get human comments from the failure issue
        human_guidance = ""
        if task.failure_issue:
            comments = github.get_issue_comments(repo_name, task.failure_issue)
            if comments:
                human_guidance = "\n\n".join(comments)
                LOG.info("Found human guidance for task '%s'", task.title)
            else:
                LOG.warning("No comments on failure issue #%d — retrying without guidance", task.failure_issue)

        # Reset task status and retry
        task.status = "pending"
        await _process_task_with_guidance(task, ctx, github, model, state, human_guidance)

    # Check results
    still_failed = [t for t in ctx.tasks if t.status == "failed"]

    await _push_changes(ctx)

    if still_failed:
        # Update the failure issues
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
        LOG.warning("Retry failed. %d task(s) still need human input.", len(still_failed))
    else:
        # All tasks passed — convert draft to ready and merge
        if state.pr_number:
            repo = github.get_repo(repo_name)
            pr = repo.get_pull(state.pr_number)
            # Update PR body and mark ready
            completed = [t for t in ctx.tasks if t.status == "completed"]
            pr.edit(
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

        # Close failure issues
        for task in ctx.tasks:
            if task.failure_issue:
                github.close_issue(repo_name, task.failure_issue)

        github.close_issue(repo_name, issue_number)
        state.status = "completed"
        save_state(state)
        LOG.info("Retry successful. All tasks complete. PR merged.")


async def _process_task_with_guidance(
    task: TaskInfo,
    ctx: JobContext,
    github: GitHubClient,
    model: str | None,
    state: JobState,
    human_guidance: str,
) -> None:
    """Retry a failed task with human guidance injected into the Developer prompt."""
    LOG.info("Retrying task: %s", task.title)

    # Red-Green loop with human guidance
    for round_num in range(1, MAX_ROUNDS + 1):
        LOG.info("  Retry round %d/%d", round_num, MAX_ROUNDS)
        _cleanup_artifacts(ctx.working_dir)

        # Developer writes code with human guidance
        LOG.info("    Developer coding (with human guidance)...")
        await run_generator(
            task_title=task.title,
            task_description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            round_number=round_num,
            working_dir=ctx.working_dir,
            model=model,
            human_guidance=human_guidance,
        )

        # QA reviews
        LOG.info("    🔍 QA Engineer reviewing...")
        await run_evaluator_review(
            task_title=task.title,
            round_number=round_num,
            working_dir=ctx.working_dir,
            model=model,
        )

        approved_path = Path(ctx.working_dir) / "approved.md"
        if approved_path.exists():
            LOG.info("  GREEN — task approved on retry round %d", round_num)
            task.status = "completed"
            await _commit_task(ctx, task)
            if task.issue_number:
                github.close_issue(ctx.repo_name, task.issue_number)
            save_state(state)
            return

        LOG.warning("  RED — retry round %d failed", round_num)

    task.status = "failed"
    save_state(state)
    LOG.error("Task '%s' still failing after retry.", task.title)


def get_ready_batches(tasks: list[TaskInfo]) -> list[list[TaskInfo]]:
    """Yield batches of tasks whose dependencies are all complete.

    Tasks in the same batch can run in parallel.
    """
    completed: set[str] = set()
    remaining = list(tasks)

    # Include already-completed tasks from resumed state
    for t in remaining[:]:
        if t.status == "completed":
            completed.add(t.id)
            remaining.remove(t)

    while remaining:
        batch = [
            t
            for t in remaining
            if all(d in completed for d in t.depends_on)
        ]

        if not batch:
            pending_ids = [t.id for t in remaining]
            raise RuntimeError(
                f"Deadlock: no tasks ready. Remaining: {pending_ids}"
            )

        yield batch

        for t in batch:
            completed.add(t.id)
            remaining.remove(t)


async def _process_task(
    task: TaskInfo,
    ctx: JobContext,
    github: GitHubClient,
    model: str | None,
    state: JobState,
) -> None:
    """Run the full red-green cycle for a single task."""
    LOG.info("🔧 Task: %s", task.title)

    # Phase 0: QA writes interface contracts
    LOG.info("  📄 QA Engineer writing contracts...")
    await run_evaluator_contracts(
        task_title=task.title,
        task_description=task.description,
        acceptance_criteria=task.acceptance_criteria,
        working_dir=ctx.working_dir,
        model=model,
    )

    # Phase 1: QA writes tests AND Developer scaffolds (parallel)
    LOG.info("  ⚡ QA writing tests + Developer scaffolding (parallel)...")
    await asyncio.gather(
        run_evaluator_red(
            task_title=task.title,
            task_description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            working_dir=ctx.working_dir,
            model=model,
        ),
        run_generator_scaffold(
            task_title=task.title,
            task_description=task.description,
            working_dir=ctx.working_dir,
            model=model,
        ),
    )

    # Phase 2-3: Red-Green loop
    for round_num in range(1, MAX_ROUNDS + 1):
        LOG.info("  🔄 Round %d/%d", round_num, MAX_ROUNDS)

        # Remove stale artifacts
        _cleanup_artifacts(ctx.working_dir)

        # Developer writes code
        LOG.info("    💻 Developer coding...")
        await run_generator(
            task_title=task.title,
            task_description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            round_number=round_num,
            working_dir=ctx.working_dir,
            model=model,
        )

        # QA reviews
        LOG.info("    🔍 QA Engineer reviewing...")
        await run_evaluator_review(
            task_title=task.title,
            round_number=round_num,
            working_dir=ctx.working_dir,
            model=model,
        )

        # Check result
        approved_path = Path(ctx.working_dir) / "approved.md"
        feedback_path = Path(ctx.working_dir) / "feedback.md"

        if approved_path.exists():
            LOG.info("  ✅ GREEN — task approved on round %d", round_num)
            task.status = "completed"
            await _commit_task(ctx, task)
            if task.issue_number:
                github.close_issue(ctx.repo_name, task.issue_number)
            save_state(state)
            return

        if not feedback_path.exists():
            # QA crashed without writing feedback — generate a default
            LOG.warning("  QA Review didn't write feedback or approved — running tests directly")
            test_result = await _run_tests(ctx.working_dir)
            feedback_path.write_text(
                f"# Feedback — Round {round_num}\n\n"
                f"QA Review agent crashed. Test output:\n\n```\n{test_result}\n```\n"
            )

        LOG.warning("  🔴 RED — round %d failed", round_num)

    # Exhausted all rounds — mark as failed but don't crash
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
    coros = [
        _process_task(task, ctx, github, model, state)
        for task in batch
    ]
    await asyncio.gather(*coros)


def _load_tasks(working_dir: str) -> list[TaskInfo]:
    """Load tasks.json written by the Architect."""
    tasks_path = Path(working_dir) / "tasks.json"
    if not tasks_path.exists():
        raise FileNotFoundError(f"Architect didn't create tasks.json in {working_dir}")

    raw = json.loads(tasks_path.read_text())
    return [
        TaskInfo(
            id=t["id"],
            title=t["title"],
            description=t["description"],
            acceptance_criteria=t.get("acceptance_criteria", []),
            depends_on=t.get("depends_on", []),
        )
        for t in raw
    ]


def _build_pr_body(
    issue_number: int,
    completed: list[TaskInfo],
    failed: list[TaskInfo],
    pending: list[TaskInfo],
) -> str:
    """Build PR body showing task progress."""
    body = f"Closes #{issue_number}\n\nAutonomous implementation by Dark Factory.\n\n"
    if completed:
        body += "## Completed\n" + "\n".join(f"- [x] {t.title}" for t in completed) + "\n\n"
    if failed:
        body += "## Failed (needs human input)\n" + "\n".join(f"- [ ] {t.title}" for t in failed) + "\n\n"
    if pending:
        body += "## Pending\n" + "\n".join(f"- [ ] {t.title}" for t in pending) + "\n\n"
    return body


def _read_feedback(working_dir: str) -> str:
    """Read feedback.md if it exists."""
    path = Path(working_dir) / "feedback.md"
    if path.exists():
        return path.read_text()
    return "No feedback file found."


async def _clone_repo(github: GitHubClient, ctx: JobContext) -> str:
    """Clone the target repo into a temp directory."""
    import tempfile

    work_dir = tempfile.mkdtemp(prefix="dark-factory-")
    clone_url = f"https://{github.token}@github.com/{github.owner}/{ctx.repo_name}.git"

    proc = await asyncio.create_subprocess_exec(
        "git", "clone", clone_url, work_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to clone {ctx.repo_name}")

    LOG.info("Cloned %s to %s", ctx.repo_name, work_dir)
    return work_dir


async def _checkout_main(ctx: JobContext) -> None:
    """Switch back to main branch."""
    proc = await asyncio.create_subprocess_exec(
        "git", "checkout", "main",
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _pull_latest(ctx: JobContext) -> None:
    """Pull latest changes from origin main."""
    proc = await asyncio.create_subprocess_exec(
        "git", "pull", "origin", "main",
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _create_branch_from(ctx: JobContext, branch_name: str) -> None:
    """Create and checkout a new branch from current HEAD."""
    proc = await asyncio.create_subprocess_exec(
        "git", "checkout", "-b", branch_name,
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _push_branch(ctx: JobContext, branch_name: str) -> None:
    """Push a specific branch to origin."""
    proc = await asyncio.create_subprocess_exec(
        "git", "push", "-u", "origin", branch_name,
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _commit_task(ctx: JobContext, task: TaskInfo) -> None:
    """Commit all changes for a completed task."""
    proc = await asyncio.create_subprocess_exec(
        "git", "add", "-A",
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    proc = await asyncio.create_subprocess_exec(
        "git", "commit", "-m", f"feat: {task.title}\n\nTask: {task.id}",
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _push_changes(ctx: JobContext) -> None:
    """Push the feature branch to origin."""
    proc = await asyncio.create_subprocess_exec(
        "git", "push", "-u", "origin", ctx.branch,
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _run_tests(working_dir: str) -> str:
    """Run make test directly and return output."""
    proc = await asyncio.create_subprocess_exec(
        "make", "test",
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
    return stdout.decode()[-2000:]  # Last 2000 chars of test output


def _cleanup_artifacts(working_dir: str) -> None:
    """Remove feedback.md and approved.md between rounds."""
    for name in ("feedback.md", "approved.md", "contracts.md"):
        _cleanup_file(working_dir, name)


def _cleanup_file(working_dir: str, filename: str) -> None:
    """Remove a single file if it exists."""
    path = Path(working_dir) / filename
    if path.exists():
        path.unlink()


async def _check_claude_cli() -> None:
    """Verify claude CLI is installed and working before starting a job."""
    LOG.info("🏥 Running health check...")
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", "Reply with OK", "--output-format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except FileNotFoundError:
        raise RuntimeError(
            "claude CLI not found. Install it: https://docs.anthropic.com/en/docs/claude-code"
        )
    except asyncio.TimeoutError:
        raise RuntimeError("claude CLI health check timed out after 30s")

    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI returned exit code {proc.returncode}. "
            f"Make sure you're authenticated (run 'claude' to log in)."
        )

    LOG.info("✅ Health check passed — claude CLI is working")
