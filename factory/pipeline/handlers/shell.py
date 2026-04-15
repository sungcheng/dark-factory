"""Shell handler — runs a shell command in the pipeline's working dir."""

from __future__ import annotations

import asyncio
import shlex
from typing import TYPE_CHECKING

from factory.pipeline.schema import NodeResult

if TYPE_CHECKING:
    from factory.pipeline.engine import PipelineContext
    from factory.pipeline.schema import Node


async def shell_handler(node: Node, ctx: PipelineContext) -> NodeResult:
    """Run a shell command.

    Expected params:
        command: str — command line (parsed via shlex, not via shell=True)
        timeout: int — seconds; default 300
    """
    command = node.params["command"]
    timeout = int(node.params.get("timeout", 300))
    args = shlex.split(command)

    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=ctx.working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return NodeResult(
            status="failed",
            message=f"{command!r} timed out after {timeout}s",
        )

    stdout_str = stdout.decode()
    stderr_str = stderr.decode()
    ok = proc.returncode == 0
    return NodeResult(
        status="success" if ok else "failed",
        message=stderr_str[-500:] if not ok else "",
        data={
            "exit_code": proc.returncode,
            "stdout": stdout_str[-2000:],
        },
    )
