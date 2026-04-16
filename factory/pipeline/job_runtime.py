"""Shared runtime state for Dark Factory stage handlers.

Phase 4 decomposes `orchestrator.run_job` into a sequence of stage
handlers. Each handler pulls the shared `JobRuntime` out of the
`PipelineContext.state` dict, mutates it, and lets subsequent stages
observe the updates. This is the minimum coupling needed to split the
stateful parts of `run_job` across nodes without inventing a new
dependency-injection mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from github.Issue import Issue

    from factory.emitter import EventEmitter
    from factory.github_client import GitHubClient
    from factory.guardrails import PreflightResult
    from factory.orchestrator import JobContext
    from factory.state import JobState


RUNTIME_KEY = "job_runtime"


@dataclass
class JobRuntime:
    """State shared across Phase 4 stage handlers.

    Populated by the first stage (`job_setup`), mutated by subsequent
    stages. Lives in `PipelineContext.state[RUNTIME_KEY]`.
    """

    repo_name: str
    issue_number: int
    model: str | None = None
    merge_mode: str = "auto"

    # Populated by job_setup
    github: GitHubClient | None = None
    emitter: EventEmitter | None = None
    state: JobState | None = None
    ctx: JobContext | None = None
    issue: Issue | None = None

    # Populated by preflight
    preflight: PreflightResult | None = None
    pre_job_test_count: int = 0

    # Populated by regression_gate
    has_existing_tests: bool = False

    # Handlers append log lines for the dashboard / tests
    logs: list[str] = field(default_factory=list)


def get_runtime(ctx_state: dict[str, object]) -> JobRuntime:
    """Retrieve the JobRuntime from a PipelineContext's state dict."""
    runtime = ctx_state.get(RUNTIME_KEY)
    if not isinstance(runtime, JobRuntime):
        raise RuntimeError(
            "JobRuntime not found in PipelineContext.state — "
            "the job_setup handler must run first",
        )
    return runtime
