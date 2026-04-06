"""GitHub API client — issues, repos, PRs."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from dataclasses import field

from github import Github
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository

LOG = logging.getLogger(__name__)


@dataclass
class SubTaskInfo:
    """A subtask within a parent task."""

    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    depends_on: list[str]
    status: str = "pending"
    failure_issue: int | None = None


@dataclass
class TaskInfo:
    """A task parsed from tasks.json with its GitHub issue number."""

    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    depends_on: list[str]
    subtasks: list[SubTaskInfo] = field(default_factory=list)
    complexity: str = "medium"  # simple, medium, complex
    task_type: str = "feature"  # feature, migration, refactor, etc.
    issue_number: int | None = None
    status: str = "pending"
    failure_issue: int | None = None
    rounds_used: int = 0
    cost_usd: float = 0.0
    total_tokens: int = 0

    @property
    def has_subtasks(self) -> bool:
        """Return True if this task has subtasks."""
        return bool(self.subtasks)

    @property
    def all_subtasks_completed(self) -> bool:
        """Return True if all subtasks are completed."""
        return all(s.status == "completed" for s in self.subtasks)

    @property
    def any_subtask_failed(self) -> bool:
        """Return True if any subtask has failed."""
        return any(s.status == "failed" for s in self.subtasks)


class GitHubClient:
    """Wraps PyGithub for dark-factory operations."""

    def __init__(self, token: str | None = None, owner: str | None = None) -> None:
        self.token = token or os.environ["GITHUB_TOKEN"]
        self.owner = owner or os.environ["GITHUB_OWNER"]
        self._gh = Github(self.token)

    def get_repo(self, repo_name: str) -> Repository:
        """Get a repo by name under the configured owner."""
        return self._gh.get_repo(f"{self.owner}/{repo_name}")

    def fetch_issue(self, repo_name: str, issue_number: int) -> Issue:
        """Fetch a single issue."""
        repo = self.get_repo(repo_name)
        return repo.get_issue(issue_number)

    def create_sub_issues(
        self,
        repo_name: str,
        parent_issue: int,
        tasks: list[TaskInfo],
    ) -> list[TaskInfo]:
        """Create GitHub issues for each task, reusing existing ones.

        Checks for open sub-issues with the same label (issue-{parent})
        and matches by title. Only creates new issues for tasks that
        don't already have one. This prevents duplicate sub-issues
        when re-running the factory.
        """
        repo = self.get_repo(repo_name)
        label = f"issue-{parent_issue}"

        # Find existing open sub-issues for this parent
        existing: dict[str, int] = {}
        for issue in repo.get_issues(
            state="open",
            labels=["auto-generated", label],
        ):
            existing[issue.title.strip().lower()] = issue.number

        for task in tasks:
            # Check if a matching issue already exists
            match_key = task.title.strip().lower()
            if match_key in existing:
                task.issue_number = existing[match_key]
                LOG.debug(
                    "Reusing existing issue #%d for '%s'",
                    task.issue_number,
                    task.title,
                )
                continue

            body = (
                f"Parent: #{parent_issue}\n\n"
                f"## Description\n{task.description}\n\n"
                f"## Acceptance Criteria\n"
            )
            for criterion in task.acceptance_criteria:
                body += f"- [ ] {criterion}\n"

            issue = repo.create_issue(
                title=task.title,
                body=body,
                labels=["dark-factory", "auto-generated", label],
            )
            task.issue_number = issue.number
        return tasks

    def close_stale_sub_issues(
        self,
        repo_name: str,
        parent_issue: int,
        active_titles: list[str],
    ) -> int:
        """Close sub-issues that no longer match the current task plan.

        When the Architect generates a new task plan, old sub-issues
        from previous runs that aren't in the new plan get closed.

        Returns the number of issues closed.
        """
        repo = self.get_repo(repo_name)
        label = f"issue-{parent_issue}"
        active = {t.strip().lower() for t in active_titles}
        closed_count = 0

        for issue in repo.get_issues(
            state="open",
            labels=["auto-generated", label],
        ):
            if issue.title.strip().lower() not in active:
                issue.edit(
                    state="closed",
                    state_reason="not_planned",
                )
                LOG.info(
                    "Closed stale sub-issue #%d: %s",
                    issue.number,
                    issue.title,
                )
                closed_count += 1

        return closed_count

    def cleanup_orphaned_issues(self, repo_name: str) -> int:
        """Close all dark-factory sub-issues whose parent issue is closed.

        Runs at job start to clean up leftovers from previous failed or
        killed runs.  Returns the number of issues closed.
        """
        repo = self.get_repo(repo_name)
        closed_count = 0
        seen_parents: dict[int, bool] = {}  # parent_num → is_closed

        for label_name in ("auto-generated", "needs-human"):
            try:
                issues = list(
                    repo.get_issues(state="open", labels=["dark-factory", label_name])
                )
            except Exception:
                continue

            for issue in issues:
                parent_num = self._extract_parent_number(issue)
                if parent_num is None:
                    continue

                # Cache parent state lookups
                if parent_num not in seen_parents:
                    try:
                        parent = repo.get_issue(parent_num)
                        seen_parents[parent_num] = parent.state == "closed"
                    except Exception:
                        seen_parents[parent_num] = False

                if seen_parents[parent_num]:
                    issue.edit(state="closed", state_reason="not_planned")
                    LOG.info(
                        "🧹 Closed orphaned #%d: %s (parent #%d closed)",
                        issue.number,
                        issue.title,
                        parent_num,
                    )
                    closed_count += 1

        return closed_count

    @staticmethod
    def _extract_parent_number(issue: Issue) -> int | None:
        """Extract parent issue number from a sub-issue body."""
        body = issue.body or ""
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped.startswith("Parent: #"):
                try:
                    return int(stripped.replace("Parent: #", "").strip())
                except ValueError:
                    pass
            if "Original issue" in line and "#" in line:
                try:
                    part = line.split("#")[1].split()[0].strip()
                    return int(part)
                except (ValueError, IndexError):
                    pass
        return None

    def cleanup_stale_prs(self, repo_name: str) -> int:
        """Close open PRs from dark-factory branches whose parent issue is closed.

        Returns the number of PRs closed.
        """
        repo = self.get_repo(repo_name)
        closed_count = 0
        seen_parents: dict[int, bool] = {}

        for pr in repo.get_pulls(state="open"):
            # Only close PRs on factory branches
            branch = pr.head.ref
            if not branch.startswith("factory/"):
                continue

            # Extract parent issue from branch name (factory/issue-N/...)
            parts = branch.split("/")
            if len(parts) < 2:
                continue
            try:
                parent_num = int(parts[1].replace("issue-", ""))
            except ValueError:
                continue

            if parent_num not in seen_parents:
                try:
                    parent = repo.get_issue(parent_num)
                    seen_parents[parent_num] = parent.state == "closed"
                except Exception:
                    seen_parents[parent_num] = False

            if seen_parents[parent_num]:
                pr.edit(state="closed")
                LOG.info(
                    "🧹 Closed stale PR #%d: %s (parent #%d closed)",
                    pr.number,
                    pr.title,
                    parent_num,
                )
                closed_count += 1

        return closed_count

    def protect_main_branch(self, repo_name: str) -> None:
        """Enable branch protection on main.

        Requires PRs, CI checks to pass, and blocks force pushes.
        The factory's PAT must have admin access to set this.
        """
        repo = self.get_repo(repo_name)
        try:
            branch = repo.get_branch("main")
            branch.edit_protection(
                required_approving_review_count=0,
                enforce_admins=False,
                dismiss_stale_reviews=False,
                require_code_owner_reviews=False,
                required_linear_history=True,
                allow_force_pushes=False,
                allow_deletions=False,
            )
            LOG.info("🔒 Branch protection enabled on %s/main", repo_name)
        except Exception as exc:
            LOG.warning(
                "Could not enable branch protection on %s: %s",
                repo_name,
                exc,
            )

    def close_issue(self, repo_name: str, issue_number: int) -> None:
        """Close an issue as completed."""
        repo = self.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        issue.edit(state="closed", state_reason="completed")

    def create_branch(self, repo_name: str, branch_name: str) -> str:
        """Create a branch from main. Returns branch name."""
        repo = self.get_repo(repo_name)
        main = repo.get_branch("main")
        repo.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=main.commit.sha,
        )
        return branch_name

    def create_pr(
        self,
        repo_name: str,
        branch: str,
        title: str,
        body: str = "",
    ) -> PullRequest:
        """Open a pull request from branch to main."""
        repo = self.get_repo(repo_name)
        return repo.create_pull(
            title=title,
            body=body,
            head=branch,
            base="main",
        )

    def merge_pr(self, repo_name: str, pr_number: int) -> None:
        """Merge a pull request."""
        repo = self.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        pr.merge(merge_method="squash")

    def get_ci_status(
        self,
        repo_name: str,
        pr_number: int,
    ) -> tuple[str, str]:
        """Get CI check status for a PR.

        Returns (status, details) where status is one of:
        - "pending" — checks still running
        - "success" — all checks passed
        - "failure" — one or more checks failed
        - "none" — no CI checks configured
        """
        repo = self.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        commit = repo.get_commit(pr.head.sha)

        # Check GitHub Actions (check runs)
        try:
            check_runs = list(commit.get_check_runs())
        except Exception as exc:
            LOG.warning(
                "Cannot read CI checks (token may lack checks:read): %s",
                exc,
            )
            return "none", "Cannot read CI checks — proceeding"
        if not check_runs:
            return "none", "No CI checks found"

        failed: list[str] = []
        pending: list[str] = []
        for run in check_runs:
            if run.status != "completed":
                pending.append(run.name)
            elif run.conclusion not in ("success", "skipped", "neutral"):
                failed.append(f"{run.name}: {run.conclusion}")

        if pending:
            return "pending", f"Waiting: {', '.join(pending)}"
        if failed:
            return "failure", "\n".join(failed)
        return "success", "All checks passed"

    def get_ci_failure_logs(
        self,
        repo_name: str,
        pr_number: int,
    ) -> str:
        """Get failure output from CI check runs."""
        repo = self.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        commit = repo.get_commit(pr.head.sha)

        logs: list[str] = []
        for run in commit.get_check_runs():
            if run.status == "completed" and run.conclusion not in (
                "success",
                "skipped",
                "neutral",
            ):
                logs.append(
                    f"## {run.name} ({run.conclusion})\n"
                    f"URL: {run.html_url}\n"
                    f"{run.output.summary if run.output else ''}"
                )
        return "\n\n".join(logs) if logs else "No failure details available"

    def create_draft_pr(
        self,
        repo_name: str,
        branch: str,
        title: str,
        body: str = "",
    ) -> PullRequest:
        """Open a draft pull request from branch to main."""
        repo = self.get_repo(repo_name)
        return repo.create_pull(
            title=title,
            body=body,
            head=branch,
            base="main",
            draft=True,
        )

    def create_failure_issue(
        self,
        repo_name: str,
        parent_issue: int,
        pr_number: int,
        task: TaskInfo,
        feedback: str,
        round_count: int,
    ) -> Issue:
        """Create a needs-human issue for a failed task."""
        body = (
            f"## Context\n"
            f"- **Original issue**: #{parent_issue}\n"
            f"- **PR**: #{pr_number} (draft)\n"
            f"- **Task**: {task.id} — {task.title}\n"
            f"- **Failed after**: {round_count} rounds\n\n"
            f"## Task Description\n{task.description}\n\n"
            f"## Acceptance Criteria\n"
            + "\n".join(f"- {c}" for c in task.acceptance_criteria)
            + f"\n\n## Last Feedback\n```\n{feedback}\n```\n\n"
            f"## To Retry\n"
            f"Comment on this issue with guidance for the Developer. "
            f"Then run:\n```\n"
            f"dark-factory retry --repo {repo_name} --issue {parent_issue}\n"
            f"```\n"
            f"Your comment will be injected into the Developer's prompt."
        )

        repo = self.get_repo(repo_name)
        return repo.create_issue(
            title=f"[Dark Factory] Task failed: {task.title}",
            body=body,
            labels=["dark-factory", "needs-human"],
        )

    def get_issue_comments(self, repo_name: str, issue_number: int) -> list[str]:
        """Get all comments on an issue, newest first."""
        repo = self.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        comments = list(issue.get_comments())
        return [c.body for c in reversed(comments)]

    def find_needs_human_issues(self, repo_name: str, parent_issue: int) -> list[Issue]:
        """Find all needs-human issues linked to a parent issue."""
        repo = self.get_repo(repo_name)
        issues = repo.get_issues(state="open", labels=["needs-human"])
        return [i for i in issues if f"#{parent_issue}" in (i.body or "")]

    def create_repo(self, repo_name: str, description: str = "") -> Repository:
        """Create a new private repo under the configured owner."""
        user = self._gh.get_user()
        return user.create_repo(  # type: ignore[union-attr]
            name=repo_name,
            description=description,
            private=True,
            auto_init=True,
        )


@dataclass
class JobContext:
    """All state for a single factory job."""

    repo_name: str
    issue_number: int
    branch: str = ""
    tasks: list[TaskInfo] = field(default_factory=list)
    working_dir: str = ""
