from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.config import get_db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL DEFAULT '',
    value      REAL NOT NULL DEFAULT 0.0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_created_at ON items(created_at);

CREATE TABLE IF NOT EXISTS jobs (
    job_id     TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    status     TEXT NOT NULL,
    progress   REAL NOT NULL DEFAULT 0.0,
    total      INTEGER NOT NULL DEFAULT 0,
    done       INTEGER NOT NULL DEFAULT 0,
    error      TEXT,
    meta       TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""

PRAGMAS = [
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous  = NORMAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA temp_store   = MEMORY",
    "PRAGMA cache_size   = -20000",
]


async def init_db(path: Path | None = None) -> None:
    db_path = path or get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as conn:
        for pragma in PRAGMAS:
            await conn.execute(pragma)
        await conn.executescript(SCHEMA)
        await conn.commit()


@asynccontextmanager
async def connect(path: Path | None = None) -> AsyncIterator[aiosqlite.Connection]:
    db_path = path or get_db_path()
    conn = await aiosqlite.connect(db_path)
    try:
        for pragma in PRAGMAS:
            await conn.execute(pragma)
        conn.row_factory = aiosqlite.Row
        yield conn
    finally:
        await conn.close()
