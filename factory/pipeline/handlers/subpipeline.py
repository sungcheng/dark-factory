"""Subpipeline handler — runs another pipeline as a single node.

Lets composite flows delegate to reusable sub-pipelines. The parent
treats the sub-pipeline as a single node with a final success/failed
result, and follows outgoing edges from there normally.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from factory.pipeline.schema import NodeResult
from factory.pipeline.schema import Pipeline

if TYPE_CHECKING:
    from factory.pipeline.engine import PipelineContext
    from factory.pipeline.schema import Node


async def subpipeline_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Load and execute another pipeline YAML.

    Expected params:
        path: str — path to the sub-pipeline YAML (absolute or relative
            to the current working directory)
    """
    from factory.pipeline.engine import run_pipeline

    path = node.params["path"]
    resolved = path if Path(path).is_absolute() else str(Path.cwd() / path)
    sub = Pipeline.from_yaml(resolved)
    return await run_pipeline(sub, ctx)
