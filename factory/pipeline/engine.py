"""Graph execution engine.

Walks a `Pipeline` starting from `pipeline.start`, executes each node
via its handler, then follows the first outgoing edge whose `when`
expression matches. Handles retry policy and edge conditions against
the prior `NodeResult`.

The engine itself has no knowledge of agents, git, or skills — all
that work lives in handler modules. Keep this file pipeline-mechanics-only.
"""

from __future__ import annotations

import logging
import operator
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from factory.pipeline.handlers import HANDLERS
from factory.pipeline.schema import Node
from factory.pipeline.schema import NodeResult
from factory.pipeline.schema import Pipeline

LOG = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Shared state threaded through every handler call.

    Handlers can read/write `state` to share data across nodes
    (e.g. the Architect writing tasks.json path, later nodes reading it).
    """

    working_dir: str
    repo_name: str = ""
    issue_number: int = 0
    state: dict[str, Any] = field(default_factory=dict)


def _eval_condition(expr: str, result: NodeResult) -> bool:
    """Safely evaluate an edge `when` expression against a NodeResult.

    Supports a small grammar: `<field> <op> <literal>` where op is one
    of ==, !=, in, not_in. Literals are quoted strings, ints, or bools.
    Fields are NodeResult attributes (status, message) or keys in
    `result.data`.
    """
    tokens = expr.split(None, 2)
    if len(tokens) != 3:
        raise ValueError(f"Cannot parse condition: {expr!r}")
    field_name, op, literal = tokens

    if field_name == "status":
        lhs: Any = result.status
    elif field_name == "message":
        lhs = result.message
    else:
        lhs = result.data.get(field_name)

    rhs: Any
    stripped = literal.strip()
    if stripped.startswith(('"', "'")) and stripped[0] == stripped[-1]:
        rhs = stripped[1:-1]
    elif stripped in ("true", "True"):
        rhs = True
    elif stripped in ("false", "False"):
        rhs = False
    else:
        try:
            rhs = int(stripped)
        except ValueError as exc:
            raise ValueError(f"Cannot parse literal: {literal!r}") from exc

    ops = {
        "==": operator.eq,
        "!=": operator.ne,
    }
    if op in ops:
        return ops[op](lhs, rhs)
    raise ValueError(f"Unsupported operator: {op!r}")


async def _execute_node(node: Node, ctx: PipelineContext) -> NodeResult:
    """Run a node's handler with retry policy.

    Returns the final NodeResult regardless of success/failure. Edge
    routing decides what a failure means — a node returning `failed`
    might still have an outgoing edge that handles it. The caller
    applies `on_exhausted` only when no edge matches.
    """
    if node.handler not in HANDLERS:
        raise ValueError(
            f"Unknown handler {node.handler!r} for node {node.id!r}. "
            f"Registered: {sorted(HANDLERS)}"
        )
    handler = HANDLERS[node.handler]

    last_result: NodeResult | None = None
    for attempt in range(1, node.retry.max + 1):
        LOG.info(
            "▶ %s (handler=%s, attempt=%d/%d)",
            node.id,
            node.handler,
            attempt,
            node.retry.max,
        )
        last_result = await handler(node, ctx)
        if last_result.status == "success":
            return last_result
        if attempt < node.retry.max:
            LOG.warning(
                "%s failed (attempt %d): %s — retrying",
                node.id,
                attempt,
                last_result.message,
            )

    assert last_result is not None
    return last_result


def _next_node_id(
    pipeline: Pipeline,
    current: Node,
    result: NodeResult,
) -> str | None:
    """Pick the first outgoing edge whose condition matches."""
    for edge in pipeline.outgoing(current.id):
        if edge.when is None or _eval_condition(edge.when, result):
            return edge.to
    return None


async def run_pipeline(pipeline: Pipeline, ctx: PipelineContext) -> None:
    """Execute a pipeline end-to-end.

    A node's final result (after retries) is first checked against
    outgoing edges. If any edge matches, traversal continues through it.
    Only when the node ended in `failed` AND no edge matched does
    `retry.on_exhausted` decide whether to abort, continue, or escalate.
    """
    LOG.info("🏭 Running pipeline %s", pipeline.name)
    current_id: str | None = pipeline.start
    while current_id:
        node = pipeline.node(current_id)
        result = await _execute_node(node, ctx)
        next_id = _next_node_id(pipeline, node, result)

        if next_id is None and result.status == "failed":
            LOG.warning(
                "%s failed with no matching edge; on_exhausted=%s",
                node.id,
                node.retry.on_exhausted,
            )
            if node.retry.on_exhausted == "abort":
                raise RuntimeError(f"Node {node.id} failed: {result.message}")

        current_id = next_id
    LOG.info("🏁 Pipeline %s complete", pipeline.name)
