"""Orchestrator — the dumb Python script that runs the factory.

No AI here. Just subprocess management, task ordering, and GitHub integration.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from pathlib import Path

from factory.agents.evaluator import run_evaluator_red
from factory.agents.evaluator import run_evaluator_review
from factory.agents.generator import run_generator
from factory.agents.planner import run_planner
from factory.github_client import GitHubClient
from factory.github_client import JobContext
from factory.github_client import TaskInfo

LOG = logging.getLogger(__name__)

MAX_ROUNDS = 5


def run_job(repo_name: str, issue_number: int) -> None:
    """Main orchestrator loop.

    1. Fetch issue from GitHub
    2. Spawn Architect to create tasks
    3. Process tasks in dependency order (parallel where possible)
    4. For each task: QA writes tests -> Developer codes -> QA reviews (max 5 rounds)
    5. Open PR and merge
    """
    github = GitHubClient()
    ctx = JobContext(repo_name=repo_name, issue_number=issue_number)

    LOG.info("Starting job for %s#%d", repo_name, issue_number)

    # Step 1: Fetch the issue
    issue = github.fetch_issue(repo_name, issue_number)
    LOG.info("Fetched issue: %s", issue.title)

    # Step 2: Clone the repo and create a feature branch
    ctx.working_dir = _clone_repo(github, ctx)
    ctx.branch = f"factory/issue-{issue_number}"
    _create_branch(ctx)

    # Step 3: Spawn the Architect
    LOG.info("Spawning Architect...")
    planner_result = run_planner(
        issue_title=issue.title,
        issue_body=issue.body or "",
        repo_name=repo_name,
        working_dir=ctx.working_dir,
    )

    if not planner_result.success:
        LOG.error("Architect failed: %s", planner_result.stderr)
        raise RuntimeError("Architect agent failed")

    # Step 4: Load tasks and create sub-issues
    ctx.tasks = _load_tasks(ctx.working_dir)
    ctx.tasks = github.create_sub_issues(repo_name, issue_number, ctx.tasks)
    LOG.info("Created %d tasks with GitHub sub-issues", len(ctx.tasks))

    # Step 5: Process tasks in dependency order
    for batch in get_ready_batches(ctx.tasks):
        batch_titles = [t.title for t in batch]
        LOG.info("Processing batch: %s", batch_titles)

        if len(batch) == 1:
            _process_task(batch[0], ctx, github)
        else:
            _process_batch_parallel(batch, ctx, github)

    # Step 6: Commit, push, open PR
    _push_changes(ctx)
    pr = github.create_pr(
        repo_name=repo_name,
        branch=ctx.branch,
        title=f"feat: {issue.title}",
        body=(
            f"Closes #{issue_number}\n\n"
            f"Autonomous implementation by Dark Factory.\n\n"
            f"## Tasks completed\n"
            + "\n".join(f"- [x] {t.title}" for t in ctx.tasks)
        ),
    )
    LOG.info("Opened PR #%d", pr.number)

    # Step 7: Auto-merge
    github.merge_pr(repo_name, pr.number)
    github.close_issue(repo_name, issue_number)
    LOG.info("Job complete. PR #%d merged.", pr.number)


def get_ready_batches(tasks: list[TaskInfo]) -> list[list[TaskInfo]]:
    """Yield batches of tasks whose dependencies are all complete.

    Tasks in the same batch can run in parallel.
    """
    completed: set[str] = set()
    remaining = list(tasks)

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


def _process_task(
    task: TaskInfo,
    ctx: JobContext,
    github: GitHubClient,
) -> None:
    """Run the full red-green cycle for a single task."""
    LOG.info("Task: %s", task.title)

    # Phase 1: QA writes failing tests (RED)
    LOG.info("  QA Engineer writing tests...")
    run_evaluator_red(
        task_title=task.title,
        task_description=task.description,
        acceptance_criteria=task.acceptance_criteria,
        working_dir=ctx.working_dir,
    )

    # Phase 2-3: Red-Green loop
    for round_num in range(1, MAX_ROUNDS + 1):
        LOG.info("  Round %d/%d", round_num, MAX_ROUNDS)

        # Remove stale artifacts
        _cleanup_artifacts(ctx.working_dir)

        # Developer writes code
        LOG.info("    Developer coding...")
        run_generator(
            task_title=task.title,
            task_description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            round_number=round_num,
            working_dir=ctx.working_dir,
        )

        # QA reviews
        LOG.info("    QA Engineer reviewing...")
        run_evaluator_review(
            task_title=task.title,
            round_number=round_num,
            working_dir=ctx.working_dir,
        )

        # Check result
        approved_path = Path(ctx.working_dir) / "approved.md"
        if approved_path.exists():
            LOG.info("  GREEN — task approved on round %d", round_num)
            task.status = "completed"
            _commit_task(ctx, task)
            if task.issue_number:
                github.close_issue(ctx.repo_name, task.issue_number)
            return

        LOG.warning("  RED — round %d failed", round_num)

    # Exhausted all rounds
    task.status = "failed"
    LOG.error(
        "Task '%s' failed after %d rounds. Escalating to human.",
        task.title,
        MAX_ROUNDS,
    )
    raise RuntimeError(
        f"Task '{task.title}' failed after {MAX_ROUNDS} rounds"
    )


def _process_batch_parallel(
    batch: list[TaskInfo],
    ctx: JobContext,
    github: GitHubClient,
) -> None:
    """Process a batch of independent tasks in parallel."""
    with ThreadPoolExecutor(max_workers=len(batch)) as executor:
        futures = {
            executor.submit(_process_task, task, ctx, github): task
            for task in batch
        }
        for future in as_completed(futures):
            task = futures[future]
            try:
                future.result()
            except Exception:
                LOG.exception("Task '%s' failed", task.title)
                raise


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


def _clone_repo(github: GitHubClient, ctx: JobContext) -> str:
    """Clone the target repo into a temp directory."""
    work_dir = tempfile.mkdtemp(prefix="dark-factory-")
    clone_url = f"https://{github.token}@github.com/{github.owner}/{ctx.repo_name}.git"

    subprocess.run(
        ["git", "clone", clone_url, work_dir],
        check=True,
        capture_output=True,
    )
    LOG.info("Cloned %s to %s", ctx.repo_name, work_dir)
    return work_dir


def _create_branch(ctx: JobContext) -> None:
    """Create and checkout a feature branch."""
    subprocess.run(
        ["git", "checkout", "-b", ctx.branch],
        cwd=ctx.working_dir,
        check=True,
        capture_output=True,
    )


def _commit_task(ctx: JobContext, task: TaskInfo) -> None:
    """Commit all changes for a completed task."""
    subprocess.run(
        ["git", "add", "-A"],
        cwd=ctx.working_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"feat: {task.title}\n\nTask: {task.id}"],
        cwd=ctx.working_dir,
        check=True,
        capture_output=True,
    )


def _push_changes(ctx: JobContext) -> None:
    """Push the feature branch to origin."""
    subprocess.run(
        ["git", "push", "-u", "origin", ctx.branch],
        cwd=ctx.working_dir,
        check=True,
        capture_output=True,
    )


def _cleanup_artifacts(working_dir: str) -> None:
    """Remove feedback.md and approved.md between rounds."""
    for name in ("feedback.md", "approved.md"):
        path = Path(working_dir) / name
        if path.exists():
            path.unlink()
