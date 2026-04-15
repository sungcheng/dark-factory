"""Engine execution tests using stub handlers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from factory.pipeline.engine import PipelineContext
from factory.pipeline.engine import _eval_condition
from factory.pipeline.engine import run_pipeline
from factory.pipeline.handlers import HANDLERS
from factory.pipeline.schema import Edge
from factory.pipeline.schema import Node
from factory.pipeline.schema import NodeResult
from factory.pipeline.schema import Pipeline
from factory.pipeline.schema import RetryPolicy


@pytest.fixture
def record_handler() -> Callable[..., Any]:
    """Register a stub handler that records which node ids ran."""
    visited: list[str] = []

    async def handler(node: Node, ctx: PipelineContext) -> NodeResult:
        visited.append(node.id)
        outcome = node.params.get("outcome", "success")
        return NodeResult(status=outcome, data=node.params.get("data", {}))

    HANDLERS["record"] = handler
    yield visited
    del HANDLERS["record"]


@pytest.mark.anyio
async def test_engine_walks_linear_chain(record_handler: list[str]) -> None:
    pipeline = Pipeline(
        name="linear",
        start="a",
        nodes=[
            Node(id="a", handler="record"),
            Node(id="b", handler="record"),
            Node(id="c", handler="record"),
        ],
        edges=[
            Edge(**{"from": "a", "to": "b"}),
            Edge(**{"from": "b", "to": "c"}),
        ],
    )
    await run_pipeline(pipeline, PipelineContext(working_dir="."))
    assert record_handler == ["a", "b", "c"]


@pytest.mark.anyio
async def test_engine_follows_matching_condition(record_handler: list[str]) -> None:
    pipeline = Pipeline(
        name="cond",
        start="a",
        nodes=[
            Node(id="a", handler="record", params={"outcome": "failed"}),
            Node(id="success_branch", handler="record"),
            Node(id="failure_branch", handler="record"),
        ],
        edges=[
            Edge(
                **{"from": "a", "to": "success_branch", "when": 'status == "success"'}
            ),
            Edge(**{"from": "a", "to": "failure_branch", "when": 'status == "failed"'}),
        ],
    )
    await run_pipeline(pipeline, PipelineContext(working_dir="."))
    assert record_handler == ["a", "failure_branch"]


@pytest.mark.anyio
async def test_engine_retries_on_failure_until_success() -> None:
    attempts = 0

    async def handler(node: Node, ctx: PipelineContext) -> NodeResult:
        nonlocal attempts
        attempts += 1
        return NodeResult(status="success" if attempts >= 3 else "failed")

    HANDLERS["flaky"] = handler
    try:
        pipeline = Pipeline(
            name="retry",
            start="a",
            nodes=[Node(id="a", handler="flaky", retry=RetryPolicy(max=5))],
            edges=[],
        )
        await run_pipeline(pipeline, PipelineContext(working_dir="."))
        assert attempts == 3
    finally:
        del HANDLERS["flaky"]


@pytest.mark.anyio
async def test_engine_aborts_when_retries_exhausted() -> None:
    async def handler(node: Node, ctx: PipelineContext) -> NodeResult:
        return NodeResult(status="failed", message="boom")

    HANDLERS["always_fail"] = handler
    try:
        pipeline = Pipeline(
            name="fail",
            start="a",
            nodes=[
                Node(
                    id="a",
                    handler="always_fail",
                    retry=RetryPolicy(max=2, on_exhausted="abort"),
                ),
            ],
            edges=[],
        )
        with pytest.raises(RuntimeError, match="boom"):
            await run_pipeline(pipeline, PipelineContext(working_dir="."))
    finally:
        del HANDLERS["always_fail"]


@pytest.mark.anyio
async def test_engine_continues_after_exhaustion_when_configured(
    record_handler: list[str],
) -> None:
    async def failing(node: Node, ctx: PipelineContext) -> NodeResult:
        return NodeResult(status="failed")

    HANDLERS["failing"] = failing
    try:
        pipeline = Pipeline(
            name="continue",
            start="a",
            nodes=[
                Node(
                    id="a",
                    handler="failing",
                    retry=RetryPolicy(max=1, on_exhausted="continue"),
                ),
                Node(id="b", handler="record"),
            ],
            edges=[Edge(**{"from": "a", "to": "b"})],
        )
        await run_pipeline(pipeline, PipelineContext(working_dir="."))
        assert record_handler == ["b"]
    finally:
        del HANDLERS["failing"]


@pytest.mark.anyio
async def test_engine_raises_on_unknown_handler() -> None:
    pipeline = Pipeline(
        name="bad",
        start="a",
        nodes=[Node(id="a", handler="no_such_handler")],
        edges=[],
    )
    with pytest.raises(ValueError, match="Unknown handler"):
        await run_pipeline(pipeline, PipelineContext(working_dir="."))


def test_condition_eval_supports_equality_and_inequality() -> None:
    r = NodeResult(status="success", data={"count": 7})
    assert _eval_condition('status == "success"', r) is True
    assert _eval_condition('status != "failed"', r) is True
    assert _eval_condition("count == 7", r) is True
    assert _eval_condition("count != 7", r) is False


def test_condition_eval_rejects_unsupported_operator() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        _eval_condition("status > 5", NodeResult(status="success"))
