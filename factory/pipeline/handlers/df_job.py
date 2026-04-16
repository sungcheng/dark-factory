"""df_job handler — runs a full Dark Factory job via the legacy orchestrator.

This is the Phase 3 bridge: the graph engine can invoke a real DF job
as a single node. Future phases will decompose `run_job` into per-stage
handlers (preflight, skills, architect, batch, validation) so the
pipeline YAML becomes the authoritative flow description and the
legacy pipeline logic in `orchestrator.py` can be retired.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from factory.pipeline.schema import NodeResult

if TYPE_CHECKING:
    from factory.pipeline.engine import PipelineContext
    from factory.pipeline.schema import Node

LOG = logging.getLogger(__name__)


async def df_job_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Drive a full Dark Factory job for a single issue.

    Expected params:
        repo_name: str — GitHub repo (without owner)
        issue_number: int — issue to process
        model: str | None — override model for all agents
        merge_mode: "auto" | "manual" — PR merge policy
    """
    from factory.orchestrator import run_job

    params = node.params
    repo_name = params["repo_name"]
    issue_number = int(params["issue_number"])
    model = params.get("model")
    merge_mode = params.get("merge_mode", "auto")

    LOG.info(
        "🏭 df_job handler dispatching to run_job for %s#%d",
        repo_name,
        issue_number,
    )
    try:
        await run_job(
            repo_name=repo_name,
            issue_number=issue_number,
            model=model,
            merge_mode=merge_mode,
        )
    except Exception as exc:
        LOG.exception("df_job failed")
        return NodeResult(status="failed", message=str(exc))

    return NodeResult(
        status="success",
        data={"repo": repo_name, "issue": issue_number},
    )
