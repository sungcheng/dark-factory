"""Tests for Phase 2 composite handlers: subpipeline, parallel, loop."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from factory.pipeline.engine import PipelineContext
from factory.pipeline.engine import run_pipeline
from factory.pipeline.handlers import HANDLERS
from factory.pipeline.schema import Edge
from factory.pipeline.schema import Node
from factory.pipeline.schema import NodeResult
from factory.pipeline.schema import Pipeline


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(body).strip() + "\n")
    return p


@pytest.fixture
def flag_handler() -> dict[str, int]:
    """Register a handler that counts invocations and reports per-call outcome."""
    counter: dict[str, int] = {"calls": 0, "fail_until": 0}

    async def handler(node: Node, ctx: PipelineContext) -> NodeResult:
        counter["calls"] += 1
        if counter["calls"] <= counter["fail_until"]:
            return NodeResult(status="failed", message=f"attempt {counter['calls']}")
        return NodeResult(status="success")

    HANDLERS["flag"] = handler
    yield counter
    del HANDLERS["flag"]


@pytest.mark.anyio
async def test_subpipeline_runs_child_and_returns_result(
    tmp_path: Path,
) -> None:
    child = _write(
        tmp_path,
        "child.yaml",
        """
        name: child
        start: s
        nodes:
          - id: s
            handler: shell
            params: { command: "true" }
        """,
    )
    parent = Pipeline(
        name="p",
        start="sub",
        nodes=[
            Node(
                id="sub",
                handler="subpipeline",
                params={"path": str(child)},
            ),
        ],
        edges=[],
    )
    result = await run_pipeline(parent, PipelineContext(working_dir=str(tmp_path)))
    assert result.status == "success"


@pytest.mark.anyio
async def test_parallel_all_success(tmp_path: Path) -> None:
    for name in ("a.yaml", "b.yaml"):
        _write(
            tmp_path,
            name,
            f"""
            name: {name}
            start: s
            nodes:
              - id: s
                handler: shell
                params: {{ command: "true" }}
            """,
        )
    parent = Pipeline(
        name="p",
        start="fan",
        nodes=[
            Node(
                id="fan",
                handler="parallel",
                params={
                    "pipelines": [str(tmp_path / "a.yaml"), str(tmp_path / "b.yaml")],
                    "wait_for": "all",
                },
            ),
        ],
        edges=[],
    )
    result = await run_pipeline(parent, PipelineContext(working_dir=str(tmp_path)))
    assert result.status == "success"
    assert result.data["children"] == ["success", "success"]


@pytest.mark.anyio
async def test_parallel_wait_for_any_succeeds_on_mixed_results(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "ok.yaml",
        """
        name: ok
        start: s
        nodes:
          - id: s
            handler: shell
            params: { command: "true" }
        """,
    )
    _write(
        tmp_path,
        "bad.yaml",
        """
        name: bad
        start: s
        nodes:
          - id: s
            handler: shell
            params: { command: "false" }
        """,
    )
    parent = Pipeline(
        name="p",
        start="fan",
        nodes=[
            Node(
                id="fan",
                handler="parallel",
                params={
                    "pipelines": [
                        str(tmp_path / "ok.yaml"),
                        str(tmp_path / "bad.yaml"),
                    ],
                    "wait_for": "any",
                },
            ),
        ],
        edges=[],
    )
    result = await run_pipeline(parent, PipelineContext(working_dir=str(tmp_path)))
    assert result.status == "success"


@pytest.mark.anyio
async def test_parallel_all_fails_if_one_child_fails(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "ok.yaml",
        """
        name: ok
        start: s
        nodes:
          - id: s
            handler: shell
            params: { command: "true" }
        """,
    )
    _write(
        tmp_path,
        "bad.yaml",
        """
        name: bad
        start: s
        nodes:
          - id: s
            handler: shell
            params: { command: "false" }
        """,
    )
    parent = Pipeline(
        name="p",
        start="fan",
        nodes=[
            Node(
                id="fan",
                handler="parallel",
                params={
                    "pipelines": [
                        str(tmp_path / "ok.yaml"),
                        str(tmp_path / "bad.yaml"),
                    ],
                    "wait_for": "all",
                },
                retry={"max": 1, "on_exhausted": "continue"},
            ),
        ],
        edges=[],
    )
    result = await run_pipeline(parent, PipelineContext(working_dir=str(tmp_path)))
    assert result.status == "failed"


@pytest.mark.anyio
async def test_loop_stops_when_exit_condition_matches(
    tmp_path: Path,
    flag_handler: dict[str, int],
) -> None:
    flag_handler["fail_until"] = 2  # succeed on 3rd attempt
    body = _write(
        tmp_path,
        "body.yaml",
        """
        name: body
        start: s
        nodes:
          - id: s
            handler: flag
        """,
    )
    parent = Pipeline(
        name="p",
        start="loop",
        nodes=[
            Node(
                id="loop",
                handler="loop",
                params={
                    "body": str(body),
                    "max_iterations": 5,
                    "exit_when": 'status == "success"',
                },
            ),
        ],
        edges=[],
    )
    result = await run_pipeline(parent, PipelineContext(working_dir=str(tmp_path)))
    assert result.status == "success"
    assert flag_handler["calls"] == 3


@pytest.mark.anyio
async def test_loop_exhausts_iterations_returns_last_result(
    tmp_path: Path,
    flag_handler: dict[str, int],
) -> None:
    flag_handler["fail_until"] = 100  # never succeeds
    body = _write(
        tmp_path,
        "body.yaml",
        """
        name: body
        start: s
        nodes:
          - id: s
            handler: flag
            retry: { max: 1, on_exhausted: continue }
        """,
    )
    parent = Pipeline(
        name="p",
        start="loop",
        nodes=[
            Node(
                id="loop",
                handler="loop",
                params={"body": str(body), "max_iterations": 3},
                retry={"max": 1, "on_exhausted": "continue"},
            ),
        ],
        edges=[],
    )
    result = await run_pipeline(parent, PipelineContext(working_dir=str(tmp_path)))
    assert result.status == "failed"
    assert flag_handler["calls"] == 3


def test_all_phase2_handlers_registered() -> None:
    for name in ("subpipeline", "parallel", "loop"):
        assert name in HANDLERS
