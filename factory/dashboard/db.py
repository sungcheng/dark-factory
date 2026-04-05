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

_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    timestamp TEXT NOT NULL
)
"""


async def init_db() -> None:
    """Initialize database on application startup.

    Creates the events table if it does not already exist.
    Safe to call multiple times (idempotent).
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_TABLE_SQL)
        await conn.commit()


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
        await conn.execute(_CREATE_TABLE_SQL)
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
        await conn.execute(_CREATE_TABLE_SQL)
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
