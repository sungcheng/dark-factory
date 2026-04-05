"""Shared pytest configuration for all tests."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Restrict anyio tests to asyncio only.

    aiosqlite is asyncio-only and does not support trio.
    """
    return "asyncio"


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path: Path) -> Generator[None, None, None]:
    """Redirect all DB writes to a temp file for every test automatically.

    Prevents tests from polluting the production dark_factory.db.
    """
    import factory.dashboard.db as db_module

    original: str = db_module.DB_PATH
    db_module.DB_PATH = str(tmp_path / "test.db")
    yield
    db_module.DB_PATH = original
