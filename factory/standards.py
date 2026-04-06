"""Standards loader — extracts role-specific sections from project docs.

Reads CONVENTIONS.md and STYLEGUIDE.md from the working directory and
returns only the sections relevant to a given agent role. This keeps
agent context focused instead of loading 500+ lines of docs.
"""

from __future__ import annotations

import logging
from pathlib import Path

LOG = logging.getLogger(__name__)

# Which sections each role needs (matched against ## headings)
ROLE_SECTIONS: dict[str, list[str]] = {
    "Architect": [
        "1. Project Structure",
        "2. Git & Branching",
        "3. Pull Requests",
        "5. Deploy Order",
        "7. Testing",
        "11. Documentation",
    ],
    "Developer": [
        "2. Git & Branching",
        "4. API Design",
        "6. Database & Migrations",
        "7. Testing",
        "8. Error Handling & Logging",
        "9. Security",
        "Python",
        "SQL",
        "API Design",
        "Testing — Python",
        "Collections",
    ],
    "QA Engineer": [
        "7. Testing",
        "3. Pull Requests",
        "Testing — Python",
        "Testing — React",
    ],
    "Staff Engineer": [
        "3. Pull Requests",
        "4. API Design",
        "7. Testing",
        "8. Error Handling & Logging",
        "9. Security",
        "11. Documentation",
    ],
}


def _extract_sections(content: str, section_names: list[str]) -> str:
    """Extract specific ## sections from a markdown document."""
    lines = content.split("\n")
    result: list[str] = []
    capturing = False

    for line in lines:
        # Check if this is a ## heading
        if line.startswith("## "):
            heading = line.lstrip("# ").strip()
            # Check if any requested section matches this heading
            capturing = any(name in heading for name in section_names)

        if capturing:
            result.append(line)

    return "\n".join(result).strip()


def load_standards_for_role(
    working_dir: str,
    role: str,
) -> str:
    """Load trimmed standards for a specific agent role.

    Reads CONVENTIONS.md and STYLEGUIDE.md from the working directory,
    extracts only the sections relevant to the role, and returns a
    compact string suitable for injection into the agent prompt.

    Returns empty string if no standards files exist.
    """
    sections = ROLE_SECTIONS.get(role, [])
    if not sections:
        return ""

    parts: list[str] = []
    conventions = Path(working_dir) / "CONVENTIONS.md"
    styleguide = Path(working_dir) / "STYLEGUIDE.md"

    if conventions.exists():
        extracted = _extract_sections(conventions.read_text(), sections)
        if extracted:
            parts.append(extracted)

    if styleguide.exists():
        extracted = _extract_sections(styleguide.read_text(), sections)
        if extracted:
            parts.append(extracted)

    if not parts:
        return ""

    result = "\n\n---\n\n".join(parts)
    LOG.debug(
        "Loaded %d chars of standards for %s (from %d+ lines)",
        len(result),
        role,
        conventions.stat().st_size // 40 if conventions.exists() else 0,
    )
    return f"\n\n## Project Standards (follow these)\n\n{result}\n"
