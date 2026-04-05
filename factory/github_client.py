"""GitHub API client — issues, repos, PRs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import field

from github import Github
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository


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
    issue_number: int | None = None
    status: str = "pending"
    failure_issue: int | None = None

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
        """Create GitHub issues for each task, linking to the parent."""
        repo = self.get_repo(repo_name)
        for task in tasks:
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
                labels=["dark-factory", "auto-generated", f"issue-{parent_issue}"],
            )
            task.issue_number = issue.number
        return tasks

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
