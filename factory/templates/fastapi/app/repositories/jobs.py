from __future__ import annotations

import json
import time

import aiosqlite

from app.models import Job, JobStatus


class JobRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(self, job_id: str, kind: str, total: int = 0) -> Job:
        now = time.time()
        await self._conn.execute(
            "INSERT INTO jobs (job_id, kind, status, total, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, kind, JobStatus.PENDING.value, total, now, now),
        )
        await self._conn.commit()
        return Job(
            job_id=job_id,
            kind=kind,
            status=JobStatus.PENDING,
            total=total,
            done=0,
            progress=0.0,
            created_at=now,
            updated_at=now,
        )

    async def get(self, job_id: str) -> Job | None:
        async with self._conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        meta_raw = row["meta"]
        meta = json.loads(meta_raw) if meta_raw else None
        return Job(
            job_id=row["job_id"],
            kind=row["kind"],
            status=JobStatus(row["status"]),
            progress=float(row["progress"]),
            total=int(row["total"]),
            done=int(row["done"]),
            error=row["error"],
            meta=meta,
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
        )

    async def update_progress(
        self,
        job_id: str,
        *,
        status: JobStatus,
        done: int,
        total: int | None = None,
        error: str | None = None,
    ) -> None:
        progress = 1.0 if status == JobStatus.COMPLETED else (done / total if total else 0.0)
        now = time.time()
        if total is not None:
            await self._conn.execute(
                "UPDATE jobs SET status = ?, done = ?, total = ?, "
                "progress = ?, error = ?, updated_at = ? WHERE job_id = ?",
                (status.value, done, total, progress, error, now, job_id),
            )
        else:
            await self._conn.execute(
                "UPDATE jobs SET status = ?, done = ?, progress = ?, "
                "error = ?, updated_at = ? WHERE job_id = ?",
                (status.value, done, progress, error, now, job_id),
            )
        await self._conn.commit()
