"""Tests for the df_job handler and the graph-engine CLI path."""

from __future__ import annotations

import pytest

from factory.pipeline.engine import PipelineContext
from factory.pipeline.handlers import HANDLERS
from factory.pipeline.handlers.df_job import df_job_handler
from factory.pipeline.schema import Node
from factory.pipeline.schema import Pipeline


def test_df_job_handler_registered() -> None:
    assert "df_job" in HANDLERS
    assert HANDLERS["df_job"] is df_job_handler


def test_df_job_yaml_loads_with_expected_shape() -> None:
    """The shipped pipeline YAML parses and contains every Phase 4 stage."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    yaml_path = repo_root / "pipelines" / "df_job.yaml"
    pipeline = Pipeline.from_yaml(str(yaml_path))

    assert pipeline.name == "df_job"
    assert pipeline.start == "job_setup"
    expected_handlers = {
        "job_setup",
        "clone_repo",
        "preflight",
        "pre_job_skills",
        "regression_gate",
        "architect",
        "create_sub_issues",
        "process_batches",
        "post_merge_validation",
        "qa_lead_review",
        "post_job_skills",
    }
    actual_handlers = {n.handler for n in pipeline.nodes}
    assert actual_handlers == expected_handlers


@pytest.mark.anyio
async def test_df_job_handler_invokes_run_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """df_job handler dispatches to orchestrator.run_job with the given params."""
    calls: list[dict[str, object]] = []

    async def fake_run_job(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("factory.orchestrator.run_job", fake_run_job)

    node = Node(
        id="n",
        handler="df_job",
        params={
            "repo_name": "acme",
            "issue_number": 42,
            "model": "sonnet",
            "merge_mode": "manual",
        },
    )
    result = await df_job_handler(node, PipelineContext(working_dir="."))

    assert result.status == "success"
    assert len(calls) == 1
    assert calls[0] == {
        "repo_name": "acme",
        "issue_number": 42,
        "model": "sonnet",
        "merge_mode": "manual",
    }


@pytest.mark.anyio
async def test_df_job_handler_failure_returns_failed_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If run_job raises, the handler returns a failed NodeResult (no crash)."""

    async def broken_run_job(**kwargs: object) -> None:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("factory.orchestrator.run_job", broken_run_job)

    node = Node(
        id="n",
        handler="df_job",
        params={
            "repo_name": "acme",
            "issue_number": 1,
            "model": None,
            "merge_mode": "auto",
        },
    )
    result = await df_job_handler(node, PipelineContext(working_dir="."))

    assert result.status == "failed"
    assert "kaboom" in result.message
