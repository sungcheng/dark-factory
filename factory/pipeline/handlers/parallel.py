"""Parallel handler — fans out N sub-pipelines concurrently.

Replaces the hand-rolled git worktree parallelism in orchestrator.py
with a composable graph node. Child pipelines share the same
PipelineContext; use subpipeline-level isolation if they shouldn't.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from factory.pipeline.schema import NodeResult
from factory.pipeline.schema import Pipeline

if TYPE_CHECKING:
    from factory.pipeline.engine import PipelineContext
    from factory.pipeline.schema import Node

LOG = logging.getLogger(__name__)


async def parallel_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Run multiple sub-pipelines concurrently.

    Expected params:
        pipelines: list[str] — paths to sub-pipeline YAML files
        wait_for: "all" | "any" (default "all") — aggregation policy.
            "all": success iff every child succeeded.
            "any": success iff at least one child succeeded.
    """
    from factory.pipeline.engine import run_pipeline

    paths = list(node.params["pipelines"])
    wait_for = node.params.get("wait_for", "all")
    if wait_for not in ("all", "any"):
        return NodeResult(
            status="failed",
            message=f"Invalid wait_for: {wait_for!r} (expected all|any)",
        )

    resolved = [p if Path(p).is_absolute() else str(Path.cwd() / p) for p in paths]
    subs = [Pipeline.from_yaml(p) for p in resolved]

    results = await asyncio.gather(
        *(run_pipeline(sub, ctx) for sub in subs),
        return_exceptions=True,
    )

    child_statuses: list[str] = []
    child_messages: list[str] = []
    for idx, r in enumerate(results):
        if isinstance(r, Exception):
            child_statuses.append("failed")
            child_messages.append(f"{paths[idx]}: {r}")
            LOG.warning("Parallel child %s raised: %s", paths[idx], r)
        else:
            child_statuses.append(r.status)
            if r.status != "success":
                child_messages.append(f"{paths[idx]}: {r.message}")

    if wait_for == "all":
        ok = all(s == "success" for s in child_statuses)
    else:
        ok = any(s == "success" for s in child_statuses)

    return NodeResult(
        status="success" if ok else "failed",
        message="; ".join(child_messages)[:500],
        data={"children": child_statuses},
    )
