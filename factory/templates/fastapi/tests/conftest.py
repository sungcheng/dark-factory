from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.db import connect, init_db
from app.repositories.items import ItemRepository
from app.repositories.jobs import JobRepository


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    return db_path


@pytest_asyncio.fixture
async def initialized_db(tmp_db: Path) -> Path:
    await init_db(tmp_db)
    return tmp_db


@pytest_asyncio.fixture
async def item_repo(initialized_db: Path) -> AsyncIterator[ItemRepository]:
    async with connect(initialized_db) as conn:
        yield ItemRepository(conn)


@pytest_asyncio.fixture
async def job_repo(initialized_db: Path) -> AsyncIterator[JobRepository]:
    async with connect(initialized_db) as conn:
        yield JobRepository(conn)


@pytest.fixture
def client(initialized_db: Path) -> Iterator[TestClient]:
    from app import deps as deps_module

    deps_module._job_runner = None
    from main import app

    with TestClient(app) as c:
        yield c

    deps_module._job_runner = None
