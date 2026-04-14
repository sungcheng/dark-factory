from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DB_PATH = ROOT / "data" / "app.db"

JOB_BATCH_SIZE = 1000
JOB_PROGRESS_EVERY = 5000


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_db_path() -> Path:
    value = os.getenv("APP_DB_PATH")
    return Path(value) if value else DEFAULT_DB_PATH


def get_job_workers() -> int:
    return _int_env("APP_JOB_WORKERS", 2)
