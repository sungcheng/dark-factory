"""Handler registry.

Each handler is an async callable with signature
    handler(node: Node, ctx: PipelineContext) -> NodeResult

The YAML's `handler:` field names which one to run. Adding a new
handler type = one file in this directory + one entry in HANDLERS.
"""

from __future__ import annotations

from factory.pipeline.handlers.agent import agent_handler
from factory.pipeline.handlers.df_job import df_job_handler
from factory.pipeline.handlers.loop import loop_handler
from factory.pipeline.handlers.parallel import parallel_handler
from factory.pipeline.handlers.shell import shell_handler
from factory.pipeline.handlers.skill import skill_handler
from factory.pipeline.handlers.subpipeline import subpipeline_handler

HANDLERS = {
    "agent": agent_handler,
    "df_job": df_job_handler,
    "loop": loop_handler,
    "parallel": parallel_handler,
    "shell": shell_handler,
    "skill": skill_handler,
    "subpipeline": subpipeline_handler,
}

__all__ = ["HANDLERS"]
