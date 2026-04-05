"""Project templates — pre-built scaffolds for common patterns."""

from __future__ import annotations

import logging
from pathlib import Path

LOG = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent

AVAILABLE_TEMPLATES = {
    "fastapi": "FastAPI web service with health endpoint, config, Docker",
    "terraform": "Terraform IaC with environments, modules, CI/CD",
    "react": "React + TypeScript + Tailwind + Vite frontend",
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

    for src_file in template_path.rglob("*"):
        if src_file.is_dir() or "__pycache__" in str(src_file):
            continue

        rel_path = src_file.relative_to(template_path)
        dest_file = target / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # Skip if file already exists
        if dest_file.exists():
            continue

        content = src_file.read_text()
        for key, value in variables.items():
            content = content.replace(f"{{{{{key}}}}}", value)

        dest_file.write_text(content)

    LOG.info("Applied template '%s' to %s", template_name, target_dir)
