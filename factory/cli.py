"""CLI for Dark Factory — claude-factory command."""
from __future__ import annotations

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
def start(repo: str, issue: int) -> None:
    """Start a factory job for a GitHub issue.

    Example:
        claude-factory start --repo weather-api --issue 1
    """
    from factory.orchestrator import run_job

    click.echo(f"Starting Dark Factory job for {repo}#{issue}")
    try:
        run_job(repo_name=repo, issue_number=issue)
        click.echo("Job completed successfully.")
    except Exception as e:
        click.echo(f"Job failed: {e}", err=True)
        sys.exit(1)


@main.command()
def version() -> None:
    """Show the Dark Factory version."""
    click.echo("dark-factory v0.1.0")


if __name__ == "__main__":
    main()
