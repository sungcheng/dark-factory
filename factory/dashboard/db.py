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
    timestamp TEXT NOT NULL,
    job_id TEXT NOT NULL DEFAULT ''
)
"""

_MIGRATE_EVENTS_ADD_JOB_ID = """\
ALTER TABLE events ADD COLUMN job_id TEXT NOT NULL DEFAULT ''
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
    Runs migrations for schema changes. Safe to call multiple times.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_EVENTS_SQL)
        await conn.execute(_CREATE_JOBS_SQL)

        # Migration: add job_id column to existing events tables
        try:
            await conn.execute(_MIGRATE_EVENTS_ADD_JOB_ID)
        except Exception:
            pass  # Column already exists

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
    When a new job starts, any other in_progress jobs for the same
    repo are marked as 'abandoned' so the dashboard stays clean.
    """
    now = datetime.now(UTC).isoformat()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_JOBS_SQL)

        # Mark stale in-progress jobs for this repo as abandoned
        if status == "in_progress":
            await conn.execute(
                """\
                UPDATE jobs SET status = 'abandoned', updated_at = ?
                WHERE repo_name = ? AND job_id != ? AND status = 'in_progress'
                """,
                (now, repo_name, job_id),
            )

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
    """Fetch active jobs from the database, most recent first.

    Excludes abandoned jobs so the dashboard only shows relevant work.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_JOBS_SQL)
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM jobs WHERE status != 'abandoned' ORDER BY updated_at DESC"
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
            INSERT INTO events
                (id, task_id, event_type, status, message, timestamp, job_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_in.task_id,
                event_in.event_type,
                event_in.status,
                event_in.message,
                timestamp.isoformat(),
                event_in.job_id,
            ),
        )
        await conn.commit()

    return EventOut(
        id=event_id,
        task_id=event_in.task_id,
        event_type=event_in.event_type,
        status=event_in.status,
        message=event_in.message,
        job_id=event_in.job_id,
        timestamp=timestamp,
    )


async def fetch_events_for_job(
    task_ids: list[str],
    job_id: str = "",
    since: str = "",
) -> list[EventOut]:
    """Fetch events for a job, ordered by timestamp ascending.

    When job_id is provided, filters events by job_id (preferred).
    Falls back to task_id-based matching for backward compatibility
    with events created before the job_id column was added.

    Args:
        task_ids: List of task IDs to fetch events for (fallback)
        job_id: Job identifier to filter events by (preferred)

    Returns:
        List of EventOut, ordered by timestamp ascending
    """
    if not task_ids and not job_id:
        return []

    rows: list[aiosqlite.Row] = []

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_EVENTS_SQL)
        conn.row_factory = aiosqlite.Row

        # Try job_id scoping first (no cross-run collisions)
        if job_id:
            query = """\
                SELECT id, task_id, event_type, status, message,
                       timestamp, job_id
                FROM events
                WHERE job_id = ?
                ORDER BY timestamp ASC
            """
            async with conn.execute(query, (job_id,)) as cursor:
                rows = list(await cursor.fetchall())

        # Fall back to task_id matching (backward compat for old events)
        # Use `since` to avoid pulling in events from older runs
        if not rows and task_ids:
            placeholders = ",".join("?" for _ in task_ids)
            if since:
                query = f"""\
                    SELECT id, task_id, event_type, status, message,
                           timestamp, job_id
                    FROM events
                    WHERE task_id IN ({placeholders})
                      AND timestamp >= ?
                    ORDER BY timestamp ASC
                """
                params = (*task_ids, since)
            else:
                query = f"""\
                    SELECT id, task_id, event_type, status, message,
                           timestamp, job_id
                    FROM events
                    WHERE task_id IN ({placeholders})
                    ORDER BY timestamp ASC
                """
                params = tuple(task_ids)
            async with conn.execute(query, params) as cursor:
                rows = list(await cursor.fetchall())

    return [
        EventOut(
            id=row["id"],
            task_id=row["task_id"],
            event_type=row["event_type"],
            status=row["status"],
            message=row["message"],
            job_id=row["job_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
        for row in rows
    ]
