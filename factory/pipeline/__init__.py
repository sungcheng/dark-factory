"""Pipeline engine — YAML-defined graph execution for Dark Factory.

Runs alongside the legacy `factory/orchestrator.py`. Gate via the
`--engine=graph` CLI flag. Default remains the orchestrator until the
graph engine is proven across a real job.
"""

from __future__ import annotations

from factory.pipeline.engine import run_pipeline
from factory.pipeline.schema import Edge
from factory.pipeline.schema import Node
from factory.pipeline.schema import NodeResult
from factory.pipeline.schema import Pipeline

__all__ = ["Edge", "Node", "NodeResult", "Pipeline", "run_pipeline"]
