"""CLI for Dark Factory — dark-factory command."""

from __future__ import annotations

import asyncio
import logging
import sys

import click
from dotenv import load_dotenv

load_dotenv()

LOG_FORMAT = "%(asctime)s %(message)s"
LOG_FORMAT_VERBOSE = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(verbose: bool) -> None:
    """Dark Factory — autonomous AI coding pipeline."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = LOG_FORMAT_VERBOSE if verbose else LOG_FORMAT
    logging.basicConfig(format=fmt, level=level, stream=sys.stderr)


@main.command()
@click.option("--repo", "-r", required=True, help="Target repo name")
@click.option("--issue", "-i", required=True, type=int, help="GitHub issue number")
@click.option(
    "--model",
    "-m",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    default=None,
    help="Override model for all agents",
)
@click.option(
    "--merge-mode",
    type=click.Choice(["auto", "manual"]),
    default="auto",
    help="auto: merge PRs immediately. manual: wait for human merge.",
)
def start(repo: str, issue: int, model: str | None, merge_mode: str) -> None:
    """Start a factory job for a single GitHub issue.

    Example:
        dark-factory start --repo weather-api --issue 1
        dark-factory start --repo weather-api --issue 1 --merge-mode manual
    """
    from factory.orchestrator import run_job

    click.echo(f"Starting Dark Factory job for {repo}#{issue}")
    if merge_mode == "manual":
        click.echo("  Merge mode: MANUAL — PRs require human merge")
    try:
        asyncio.run(
            run_job(
                repo_name=repo,
                issue_number=issue,
                model=model,
                merge_mode=merge_mode,
            )
        )
        click.echo("Job completed successfully.")
    except Exception as e:
        click.echo(f"Job failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--repo", "-r", required=True, help="Target repo name")
@click.option("--issue", "-i", required=True, type=int, help="Original issue number")
@click.option(
    "--model",
    "-m",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    default=None,
    help="Override model for all agents",
)
def retry(repo: str, issue: int, model: str | None) -> None:
    """Retry failed tasks using human guidance from GitHub comments.

    After a task fails, comment on the needs-human issue with guidance,
    then run this command to retry.

    Example:
        dark-factory retry --repo weather-api --issue 1
    """
    from factory.orchestrator import retry_job

    click.echo(f"Retrying failed tasks for {repo}#{issue}")
    try:
        asyncio.run(retry_job(repo_name=repo, issue_number=issue, model=model))
        click.echo("Retry completed.")
    except Exception as e:
        click.echo(f"Retry failed: {e}", err=True)
        sys.exit(1)


@main.command("run-pipeline")
@click.argument("yaml_path", type=click.Path(exists=True))
@click.option(
    "--working-dir",
    "-d",
    default=".",
    help="Working directory for the pipeline (default: cwd)",
)
def run_pipeline_cmd(yaml_path: str, working_dir: str) -> None:
    """Run a YAML pipeline through the graph engine.

    Phase-1 entry point for graph-based execution, alongside the
    legacy `start` command. Use this to run pipelines defined in
    `pipelines/*.yaml`.

    Examples:
        dark-factory run-pipeline pipelines/demo.yaml
        dark-factory run-pipeline pipelines/hotfix.yaml -d /tmp/work
    """
    from factory.pipeline.engine import PipelineContext
    from factory.pipeline.engine import run_pipeline
    from factory.pipeline.schema import Pipeline

    pipeline = Pipeline.from_yaml(yaml_path)
    ctx = PipelineContext(working_dir=working_dir)
    click.echo(f"Running pipeline {pipeline.name} from {yaml_path}")
    try:
        asyncio.run(run_pipeline(pipeline, ctx))
        click.echo("Pipeline completed.")
    except Exception as e:
        click.echo(f"Pipeline failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--repo", "-r", required=True, help="Target repo name")
@click.option(
    "--model",
    "-m",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    default=None,
    help="Override model for all agents",
)
@click.option(
    "--sequential",
    "-s",
    is_flag=True,
    help="Process issues one at a time (default is parallel)",
)
def run(repo: str, model: str | None, sequential: bool) -> None:
    """Process all open issues in a repo (parallel by default).

    Examples:
        dark-factory run --repo weather-api
        dark-factory run --repo weather-api --sequential
    """
    from factory.github_client import GitHubClient
    from factory.orchestrator import run_job

    github = GitHubClient()
    repo_obj = github.get_repo(repo)

    # Filter: only real parent issues (not auto-generated sub-issues or needs-human)
    skip_labels = {"auto-generated", "needs-human"}
    open_issues = sorted(
        [
            i
            for i in repo_obj.get_issues(state="open")
            if not i.pull_request
            and not skip_labels.intersection({lbl.name for lbl in i.labels})
        ],
        key=lambda i: i.number,
    )

    if not open_issues:
        click.echo(f"No open issues in {repo}")
        return

    parallel = not sequential
    mode = "in parallel" if parallel else "sequentially"
    click.echo(f"Found {len(open_issues)} open issue(s) in {repo} — processing {mode}:")
    for issue in open_issues:
        click.echo(f"  #{issue.number}: {issue.title}")

    if parallel:

        async def run_all() -> None:
            results = await asyncio.gather(
                *[
                    run_job(repo_name=repo, issue_number=i.number, model=model)
                    for i in open_issues
                ],
                return_exceptions=True,
            )
            for issue, result in zip(open_issues, results):
                if isinstance(result, Exception):
                    click.echo(f"  #{issue.number} failed: {result}", err=True)
                else:
                    click.echo(f"  #{issue.number} completed.")

        asyncio.run(run_all())
    else:
        for issue in open_issues:
            click.echo(f"\nProcessing #{issue.number}: {issue.title}")
            try:
                asyncio.run(
                    run_job(
                        repo_name=repo,
                        issue_number=issue.number,
                        model=model,
                    )
                )
                click.echo(f"  #{issue.number} completed.")
            except Exception as e:
                click.echo(f"  #{issue.number} failed: {e}", err=True)


@main.command()
def repos() -> None:
    """List all GitHub repos for the configured owner."""
    from factory.github_client import GitHubClient

    github = GitHubClient()
    user = github._gh.get_user()
    all_repos = list(user.get_repos())

    # Sort: private first, then alphabetical
    private_repos = sorted([r for r in all_repos if r.private], key=lambda r: r.name)
    public_repos = sorted([r for r in all_repos if not r.private], key=lambda r: r.name)

    click.echo(f"Repos for {github.owner}:\n")

    if private_repos:
        click.echo("  PRIVATE")
        for repo in private_repos:
            lang = repo.language or "—"
            issues = repo.open_issues_count
            click.echo(f"    {repo.name:<30} {lang:<12} {issues} open issue(s)")

    if public_repos:
        if private_repos:
            click.echo()
        click.echo("  PUBLIC")
        for repo in public_repos:
            lang = repo.language or "—"
            issues = repo.open_issues_count
            click.echo(f"    {repo.name:<30} {lang:<12} {issues} open issue(s)")


@main.command(name="create-issue")
@click.option("--repo", "-r", required=True, help="Target repo name")
@click.option("--title", "-t", required=True, help="Issue title")
@click.option("--body", "-b", default="", help="Issue body (or use --editor)")
@click.option("--editor", "-e", is_flag=True, help="Open editor to write issue body")
@click.option("--label", "-l", multiple=True, help="Labels to add (repeatable)")
def create_issue(
    repo: str,
    title: str,
    body: str,
    editor: bool,
    label: tuple[str, ...],
) -> None:
    """Create a GitHub issue on a repo.

    Examples:
        dark-factory create-issue -r weather-api -t "Add caching"
        dark-factory create-issue -r weather-api -t "Add caching" --editor
        dark-factory create-issue -r weather-api -t "Add caching" -b "Cache"
        dark-factory create-issue -r weather-api -t "Add caching" -l enhancement
    """
    from factory.github_client import GitHubClient

    if editor:
        body = click.edit(text="") or ""

    github = GitHubClient()
    repo_obj = github.get_repo(repo)
    labels = list(label) if label else []
    issue = repo_obj.create_issue(title=title, body=body, labels=labels)
    click.echo(f"Created issue #{issue.number}: {issue.title}")
    click.echo(f"  https://github.com/{github.owner}/{repo}/issues/{issue.number}")


@main.command(name="create-project")
@click.argument("name")
@click.option(
    "--template",
    "-t",
    type=click.Choice(["fastapi", "fullstack", "terraform"]),
    default=None,
    help="Apply a project template (optional)",
)
@click.option(
    "--public",
    is_flag=True,
    default=False,
    help="Create as public repo (default: private)",
)
@click.option(
    "--description",
    "-d",
    default="",
    help="Repo description",
)
def create_project(
    name: str,
    template: str,
    public: bool,
    description: str,
) -> None:
    """Create a new project repo with CI/CD, ready for the factory.

    By default creates a bare repo with CLAUDE.md and CI workflow.
    The Architect will scaffold the project based on the first issue.
    Use --template to start with a pre-built scaffold.

    Examples:
        dark-factory create-project weather-api
        dark-factory create-project weather-api --public
        dark-factory create-project weather-api -t fastapi
        dark-factory create-project weather-api -d "Weather API"
    """
    from factory.project import create_project as _create

    try:
        url = _create(
            name=name,
            template=template,
            public=public,
            description=description,
        )
        click.echo(f"Project created: {url}")
    except Exception as e:
        click.echo(f"Failed: {e}", err=True)
        sys.exit(1)


@main.command()
def version() -> None:
    """Show the Dark Factory version."""
    from factory import __version__

    click.echo(f"dark-factory v{__version__}")


@main.command()
@click.option(
    "--push/--no-push",
    default=True,
    help="Push tag to remote (default: yes)",
)
def release(push: bool) -> None:
    """Create a git tag from the current version and push it.

    Reads the version from factory/__init__.py, creates a git tag
    (e.g., v0.3.0), and optionally pushes it to origin. The GitHub
    Actions release workflow will then create a GitHub release.

    Example:
        dark-factory release
        dark-factory release --no-push
    """
    import subprocess

    from factory import __version__

    tag = f"v{__version__}"

    # Check if tag already exists
    result = subprocess.run(
        ["git", "tag", "-l", tag],
        capture_output=True,
        text=True,
    )
    if tag in result.stdout.strip().split("\n"):
        click.echo(f"Tag {tag} already exists.")
        return

    # Create tag
    subprocess.run(
        ["git", "tag", "-a", tag, "-m", f"Release {tag}"],
        check=True,
    )
    click.echo(f"Created tag: {tag}")

    if push:
        subprocess.run(
            ["git", "push", "origin", tag],
            check=True,
        )
        click.echo(f"Pushed {tag} to origin.")
    else:
        click.echo(f"Tag created locally. Push with: git push origin {tag}")


@main.command()
@click.option("--repo", "-r", required=True, help="Target repo name")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be cleaned without doing it",
)
def cleanup(repo: str, dry_run: bool) -> None:
    """Clean up stale sub-issues, state files, and temp dirs for a repo.

    Closes orphaned sub-issues whose parent is done, removes completed
    state files, and cleans up temp clone directories.

    Examples:
        dark-factory cleanup --repo weather-app
        dark-factory cleanup --repo weather-app --dry-run
    """
    import glob
    import pathlib
    import shutil

    from factory.github_client import GitHubClient
    from factory.state import STATE_DIR

    github = GitHubClient()
    prefix = f"{repo}-"
    action = "Would" if dry_run else "Will"

    # 1. Close orphaned sub-issues whose parent issue is closed
    click.echo("Scanning for orphaned sub-issues...")
    if dry_run:
        # For dry-run, do manual scan to show what would happen
        repo_obj = github.get_repo(repo)
        auto_issues = list(repo_obj.get_issues(state="open", labels=["auto-generated"]))
        needs_human = list(repo_obj.get_issues(state="open", labels=["needs-human"]))
        orphan_count = 0
        seen_parents: dict[int, bool] = {}
        for issue in auto_issues + needs_human:
            parent_num = github._extract_parent_number(issue)
            if parent_num is None:
                continue
            if parent_num not in seen_parents:
                try:
                    parent = repo_obj.get_issue(parent_num)
                    seen_parents[parent_num] = parent.state == "closed"
                except Exception:
                    seen_parents[parent_num] = False
            if seen_parents[parent_num]:
                orphan_count += 1
                click.echo(
                    f"  {action} close #{issue.number}: "
                    f"{issue.title} (parent #{parent_num} closed)"
                )
    else:
        orphan_count = github.cleanup_orphaned_issues(repo)

    click.echo(f"  {orphan_count} orphaned issue(s) {'found' if dry_run else 'closed'}")

    # 1b. Close stale PRs from factory branches whose parent issue is closed
    click.echo("\nScanning for stale PRs...")
    if dry_run:
        repo_obj = github.get_repo(repo)
        pr_count = 0
        for pr in repo_obj.get_pulls(state="open"):
            branch = pr.head.ref
            if not branch.startswith("factory/"):
                continue
            parts = branch.split("/")
            if len(parts) < 2:
                continue
            try:
                parent_num = int(parts[1].replace("issue-", ""))
            except ValueError:
                continue
            try:
                parent = repo_obj.get_issue(parent_num)
                if parent.state == "closed":
                    pr_count += 1
                    click.echo(
                        f"  Would close PR #{pr.number}: "
                        f"{pr.title} (parent #{parent_num} closed)"
                    )
            except Exception:
                pass
    else:
        pr_count = github.cleanup_stale_prs(repo)

    click.echo(f"  {pr_count} stale PR(s) {'found' if dry_run else 'closed'}")

    # 2. Clean up completed state files
    click.echo("\nScanning state files...")
    state_files = sorted(STATE_DIR.glob(f"{prefix}*.json"))
    cleaned_states = 0
    for path in state_files:
        try:
            import json

            data = json.loads(path.read_text())
            if data.get("status") == "completed":
                cleaned_states += 1
                if dry_run:
                    click.echo(f"  {action} remove {path.name}")
                else:
                    path.unlink()
                    click.echo(f"  Removed {path.name}")
        except Exception:
            pass

    state_verb = "found" if dry_run else "removed"
    click.echo(f"  {cleaned_states} completed state file(s) {state_verb}")

    # 3. Clean up orphaned temp clone directories
    click.echo("\nScanning temp directories...")
    tmp_dirs = glob.glob("/tmp/dark-factory-*") + glob.glob(
        "/var/folders/**/dark-factory-*", recursive=True
    )
    # Only clean dirs that aren't referenced by active state files
    active_dirs: set[str] = set()
    for path in STATE_DIR.glob(f"{prefix}*.json"):
        try:
            data = json.loads(path.read_text())
            wd = data.get("working_dir", "")
            if wd:
                active_dirs.add(wd)
        except Exception:
            pass

    cleaned_dirs = 0
    for tmp_dir in tmp_dirs:
        tmp_path = pathlib.Path(tmp_dir)
        if tmp_dir not in active_dirs and tmp_path.is_dir():
            cleaned_dirs += 1
            if dry_run:
                click.echo(f"  {action} remove {tmp_dir}")
            else:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                click.echo(f"  Removed {tmp_dir}")

    dir_verb = "found" if dry_run else "removed"
    click.echo(f"  {cleaned_dirs} orphaned temp dir(s) {dir_verb}")

    # Summary
    total = orphan_count + cleaned_states + cleaned_dirs
    if dry_run:
        click.echo(f"\nDry run complete. {total} item(s) would be cleaned.")
    else:
        click.echo(f"\nCleanup complete. {total} item(s) cleaned.")


if __name__ == "__main__":
    main()
