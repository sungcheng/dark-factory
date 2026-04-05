"""Shared pytest configuration for all tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Restrict anyio tests to asyncio only.

    aiosqlite is asyncio-only and does not support trio.
    """
    return "asyncio"
