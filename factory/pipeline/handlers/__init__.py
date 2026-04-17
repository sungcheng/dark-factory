"""Handler registry.

Each handler is an async callable with signature
    handler(node: Node, ctx: PipelineContext) -> NodeResult

The YAML's `handler:` field names which one to run. Adding a new
handler type = one file in this directory + one entry in HANDLERS.
"""

from __future__ import annotations

from factory.pipeline.handlers.agent import agent_handler
from factory.pipeline.handlers.loop import loop_handler
from factory.pipeline.handlers.parallel import parallel_handler
from factory.pipeline.handlers.shell import shell_handler
from factory.pipeline.handlers.skill import skill_handler
from factory.pipeline.handlers.stages import architect_handler
from factory.pipeline.handlers.stages import clone_repo_handler
from factory.pipeline.handlers.stages import create_sub_issues_handler
from factory.pipeline.handlers.stages import job_setup_handler
from factory.pipeline.handlers.stages import post_job_skills_handler
from factory.pipeline.handlers.stages import post_merge_validation_handler
from factory.pipeline.handlers.stages import pre_job_skills_handler
from factory.pipeline.handlers.stages import preflight_handler
from factory.pipeline.handlers.stages import process_batches_handler
from factory.pipeline.handlers.stages import qa_lead_review_handler
from factory.pipeline.handlers.stages import regression_gate_handler
from factory.pipeline.handlers.subpipeline import subpipeline_handler

HANDLERS = {
    # Primitives
    "agent": agent_handler,
    "loop": loop_handler,
    "parallel": parallel_handler,
    "shell": shell_handler,
    "skill": skill_handler,
    "subpipeline": subpipeline_handler,
    # Stage handlers — the decomposed Dark Factory flow
    "job_setup": job_setup_handler,
    "clone_repo": clone_repo_handler,
    "preflight": preflight_handler,
    "pre_job_skills": pre_job_skills_handler,
    "regression_gate": regression_gate_handler,
    "architect": architect_handler,
    "create_sub_issues": create_sub_issues_handler,
    "process_batches": process_batches_handler,
    "post_merge_validation": post_merge_validation_handler,
    "qa_lead_review": qa_lead_review_handler,
    "post_job_skills": post_job_skills_handler,
}

__all__ = ["HANDLERS"]
