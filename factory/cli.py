"""CLI for Dark Factory — dark-factory command."""
from __future__ import annotations

import asyncio
import logging
import sys

import click
from dotenv import load_dotenv

load_dotenv()

LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(verbose: bool) -> None:
    """Dark Factory — autonomous AI coding pipeline."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, level=level, stream=sys.stderr)


@main.command()
@click.option("--repo", "-r", required=True, help="Target repo name")
@click.option("--issue", "-i", required=True, type=int, help="GitHub issue number")
@click.option(
    "--model", "-m",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    default=None,
    help="Override model for all agents",
)
def start(repo: str, issue: int, model: str | None) -> None:
    """Start a factory job for a single GitHub issue.

    Example:
        dark-factory start --repo weather-api --issue 1
    """
    from factory.orchestrator import run_job

    click.echo(f"Starting Dark Factory job for {repo}#{issue}")
    try:
        asyncio.run(run_job(repo_name=repo, issue_number=issue, model=model))
        click.echo("Job completed successfully.")
    except Exception as e:
        click.echo(f"Job failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--repo", "-r", required=True, help="Target repo name")
@click.option("--issue", "-i", required=True, type=int, help="Original issue number")
@click.option(
    "--model", "-m",
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


@main.command()
@click.option("--repo", "-r", required=True, help="Target repo name")
@click.option(
    "--model", "-m",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    default=None,
    help="Override model for all agents",
)
def run(repo: str, model: str | None) -> None:
    """Process all open issues in a repo, ordered by issue number.

    Example:
        dark-factory run --repo weather-api
    """
    from factory.github_client import GitHubClient
    from factory.orchestrator import run_job

    github = GitHubClient()
    repo_obj = github.get_repo(repo)
    open_issues = sorted(
        [i for i in repo_obj.get_issues(state="open") if not i.pull_request],
        key=lambda i: i.number,
    )

    if not open_issues:
        click.echo(f"No open issues in {repo}")
        return

    click.echo(f"Found {len(open_issues)} open issue(s) in {repo}:")
    for issue in open_issues:
        click.echo(f"  #{issue.number}: {issue.title}")

    for issue in open_issues:
        click.echo(f"\nProcessing #{issue.number}: {issue.title}")
        try:
            asyncio.run(run_job(repo_name=repo, issue_number=issue.number, model=model))
            click.echo(f"  #{issue.number} completed.")
        except Exception as e:
            click.echo(f"  #{issue.number} failed: {e}", err=True)


@main.command()
def repos() -> None:
    """List all GitHub repos for the configured owner."""
    from factory.github_client import GitHubClient

    github = GitHubClient()
    user = github._gh.get_user()

    click.echo(f"Repos for {github.owner}:\n")
    for repo in sorted(user.get_repos(), key=lambda r: r.name):
        visibility = "private" if repo.private else "public"
        issues = repo.open_issues_count
        click.echo(f"  {repo.name:<30} [{visibility}]  {issues} open issue(s)")


@main.command()
def version() -> None:
    """Show the Dark Factory version."""
    click.echo("dark-factory v0.1.0")


if __name__ == "__main__":
    main()
