"""Project templates — pre-built scaffolds for common patterns."""

from __future__ import annotations

import logging
from pathlib import Path

LOG = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent

AVAILABLE_TEMPLATES = {
    "fastapi": (
        "FastAPI service with layered architecture "
        "(routers/services/repositories), async SQLite, SSE job progress"
    ),
    "fullstack": "FastAPI backend + React frontend with Docker Compose",
    "terraform": "Terraform IaC with environments, modules, CI/CD",
}


def list_templates() -> dict[str, str]:
    """Return available templates with descriptions."""
    return AVAILABLE_TEMPLATES


def apply_template(
    template_name: str,
    target_dir: str,
    variables: dict[str, str] | None = None,
) -> None:
    """Copy a template to the target directory and replace variables.

    Variables use {{VARIABLE_NAME}} syntax in file contents.
    """
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise ValueError(
            f"Template '{template_name}' not found. "
            f"Available: {list(AVAILABLE_TEMPLATES.keys())}"
        )

    variables = variables or {}
    target = Path(target_dir)

    skip_patterns = ("__pycache__", ".ruff_cache", "node_modules", ".git/")

    for src_file in template_path.rglob("*"):
        if src_file.is_dir():
            continue
        if any(p in str(src_file) for p in skip_patterns):
            continue

        rel_path = src_file.relative_to(template_path)
        dest_file = target / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # Skip if file already exists
        if dest_file.exists():
            continue

        # Skip binary files
        try:
            content = src_file.read_text()
        except UnicodeDecodeError:
            LOG.debug("Skipping binary file: %s", rel_path)
            continue

        for key, value in variables.items():
            content = content.replace(f"{{{{{key}}}}}", value)

        dest_file.write_text(content)

    LOG.info("Applied template '%s' to %s", template_name, target_dir)
