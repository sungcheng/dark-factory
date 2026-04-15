"""CLI entry point for running a pipeline YAML directly.

Usage:
    uv run python -m factory.pipeline.runner pipelines/demo.yaml
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from factory.pipeline.engine import PipelineContext
from factory.pipeline.engine import run_pipeline
from factory.pipeline.schema import Pipeline


async def _main(yaml_path: str, working_dir: str) -> int:
    pipeline = Pipeline.from_yaml(yaml_path)
    ctx = PipelineContext(working_dir=working_dir)
    await run_pipeline(pipeline, ctx)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) < 2:
        print("usage: python -m factory.pipeline.runner PIPELINE.yaml [WORKING_DIR]")
        return 2
    yaml_path = sys.argv[1]
    working_dir = sys.argv[2] if len(sys.argv) > 2 else str(Path.cwd())
    return asyncio.run(_main(yaml_path, working_dir))


if __name__ == "__main__":
    sys.exit(main())
