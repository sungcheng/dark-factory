from __future__ import annotations

import logging
from datetime import UTC
from datetime import datetime
from uuid import uuid4

import aiosqlite

from factory.dashboard.models import EventIn
from factory.dashboard.models import EventOut

LOG = logging.getLogger(__name__)

DB_PATH: str = "dark_factory.db"

_CREATE_EVENTS_SQL = """\
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    timestamp TEXT NOT NULL
)
"""

_CREATE_JOBS_SQL = """\
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    repo_name TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',
    task_count INTEGER NOT NULL DEFAULT 0,
    completed_task_count INTEGER NOT NULL DEFAULT 0,
    tasks_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


async def init_db() -> None:
    """Initialize database on application startup.

    Creates the events and jobs tables if they do not already exist.
    Safe to call multiple times (idempotent).
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_EVENTS_SQL)
        await conn.execute(_CREATE_JOBS_SQL)
        await conn.commit()


async def upsert_job(
    job_id: str,
    repo_name: str,
    issue_number: int,
    status: str = "in_progress",
    task_count: int = 0,
    completed_task_count: int = 0,
    tasks_json: str = "[]",
) -> None:
    """Insert or update a job record.

    Called by the orchestrator (via emitter) to persist job state
    into the database so historical jobs survive state file cleanup.
    """
    now = datetime.now(UTC).isoformat()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_JOBS_SQL)
        await conn.execute(
            """\
            INSERT INTO jobs (
                job_id, repo_name, issue_number, status,
                task_count, completed_task_count, tasks_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                status = excluded.status,
                task_count = excluded.task_count,
                completed_task_count = excluded.completed_task_count,
                tasks_json = excluded.tasks_json,
                updated_at = excluded.updated_at
            """,
            (
                job_id,
                repo_name,
                issue_number,
                status,
                task_count,
                completed_task_count,
                tasks_json,
                now,
                now,
            ),
        )
        await conn.commit()


async def fetch_all_jobs() -> list[dict[str, object]]:
    """Fetch all jobs from the database, most recent first."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_JOBS_SQL)
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM jobs ORDER BY updated_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()

    return [dict(row) for row in rows]


async def fetch_job(job_id: str) -> dict[str, object] | None:
    """Fetch a single job from the database."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_JOBS_SQL)
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()

    return dict(row) if row else None


async def insert_event(event_in: EventIn) -> EventOut:
    """Insert event into database and return created event.

    Ensures the events table exists before inserting.

    Args:
        event_in: EventIn Pydantic model with task_id, event_type,
            status, message

    Returns:
        EventOut: Created event including id and timestamp
    """
    event_id = str(uuid4())
    timestamp = datetime.now(UTC)

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_EVENTS_SQL)
        await conn.execute(
            """\
            INSERT INTO events (id, task_id, event_type, status, message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_in.task_id,
                event_in.event_type,
                event_in.status,
                event_in.message,
                timestamp.isoformat(),
            ),
        )
        await conn.commit()

    return EventOut(
        id=event_id,
        task_id=event_in.task_id,
        event_type=event_in.event_type,
        status=event_in.status,
        message=event_in.message,
        timestamp=timestamp,
    )


async def fetch_events_for_job(task_ids: list[str]) -> list[EventOut]:
    """Fetch all events for given task IDs, ordered by timestamp ascending.

    Args:
        task_ids: List of task IDs to fetch events for

    Returns:
        List of EventOut, ordered by timestamp ascending
    """
    if not task_ids:
        return []

    placeholders = ",".join("?" for _ in task_ids)
    query = f"""\
        SELECT id, task_id, event_type, status, message, timestamp
        FROM events
        WHERE task_id IN ({placeholders})
        ORDER BY timestamp ASC
    """

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_EVENTS_SQL)
        conn.row_factory = aiosqlite.Row
        async with conn.execute(query, task_ids) as cursor:
            rows = await cursor.fetchall()

    return [
        EventOut(
            id=row["id"],
            task_id=row["task_id"],
            event_type=row["event_type"],
            status=row["status"],
            message=row["message"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
        for row in rows
    ]
