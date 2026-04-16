"""Loop handler — repeats a body pipeline until a condition is met.

Replaces the hardcoded red-green loop. The body is itself a pipeline
YAML; its final NodeResult is evaluated against `exit_when` each
iteration. Hits `max_iterations` means the last body result is
returned as-is (the caller routes on it via outgoing edges).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from factory.pipeline.schema import NodeResult
from factory.pipeline.schema import Pipeline

if TYPE_CHECKING:
    from factory.pipeline.engine import PipelineContext
    from factory.pipeline.schema import Node

LOG = logging.getLogger(__name__)


async def loop_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Run a body pipeline repeatedly until exit_when or max_iterations.

    Expected params:
        body: str — path to the body pipeline YAML
        max_iterations: int — hard cap on iterations (default 5)
        exit_when: str — expression evaluated against each iteration's
            final NodeResult (default 'status == "success"')
    """
    from factory.pipeline.engine import eval_condition
    from factory.pipeline.engine import run_pipeline

    body_path = node.params["body"]
    resolved = (
        body_path if Path(body_path).is_absolute() else str(Path.cwd() / body_path)
    )
    max_iter = int(node.params.get("max_iterations", 5))
    exit_when = node.params.get("exit_when", 'status == "success"')
    body = Pipeline.from_yaml(resolved)

    last_result = NodeResult(status="failed", message="no iterations executed")
    for iteration in range(1, max_iter + 1):
        LOG.info("↻ loop %s iteration %d/%d", node.id, iteration, max_iter)
        try:
            last_result = await run_pipeline(body, ctx)
        except RuntimeError as exc:
            # A body node aborted on failure — treat as failed iteration
            # so the loop can retry rather than bubbling up.
            LOG.warning("↻ loop %s body raised: %s", node.id, exc)
            last_result = NodeResult(status="failed", message=str(exc))
        if eval_condition(exit_when, last_result):
            LOG.info(
                "↻ loop %s exit condition met at iteration %d",
                node.id,
                iteration,
            )
            return last_result

    LOG.warning(
        "↻ loop %s exhausted %d iterations without meeting %r",
        node.id,
        max_iter,
        exit_when,
    )
    return last_result
