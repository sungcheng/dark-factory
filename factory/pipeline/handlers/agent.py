"""Agent handler — spawns a Claude Code subprocess for a named role."""

from __future__ import annotations

from typing import TYPE_CHECKING

from factory.agents.base import AgentConfig
from factory.agents.base import load_prompt
from factory.agents.base import run_agent
from factory.pipeline.schema import NodeResult

if TYPE_CHECKING:
    from factory.pipeline.engine import PipelineContext
    from factory.pipeline.schema import Node


ROLE_TO_PROMPT = {
    "Architect": "planner",
    "Developer": "generator",
    "QA Engineer (Review)": "evaluator",
    "QA Engineer (Regression)": "evaluator",
}


async def agent_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Run a Claude Code agent for the configured role.

    Expected params:
        role: str — agent role (e.g. "Architect", "Developer")
        model: str | None — override default model for the role
        max_turns: int | None — cap on agent turns
        allowed_tools: list[str] | None — explicit tool allowlist
        prompt_override: str | None — inline prompt instead of loading
    """
    params = node.params
    role = params["role"]
    prompt = (
        params["prompt_override"]
        if "prompt_override" in params
        else load_prompt(ROLE_TO_PROMPT.get(role, "generator"))
    )

    config = AgentConfig(
        role=role,
        prompt=prompt,
        allowed_tools=list(params.get("allowed_tools", [])),
        working_dir=ctx.working_dir,
        max_turns=int(params.get("max_turns", 50)),
        model=params.get("model"),
    )

    result = await run_agent(config)

    return NodeResult(
        status="success" if result.success else "failed",
        message=result.stderr[:500] if not result.success else "",
        data={
            "exit_code": result.exit_code,
            "cost_usd": result.cost.cost_usd,
            "num_turns": result.cost.num_turns,
        },
    )
