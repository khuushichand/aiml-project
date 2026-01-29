from __future__ import annotations

"""Shared helpers for Jobs-based worker modules."""

import os
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager


def jobs_manager_from_env() -> JobManager:
    """Build a JobManager based on the JOBS_DB_URL environment variable."""
    db_url = (os.getenv("JOBS_DB_URL") or "").strip()
    if db_url and not (db_url.startswith("postgres") or db_url.startswith("sqlite")):
        logger.warning("Unexpected JOBS_DB_URL scheme; defaulting to in-memory jobs backend.")
        db_url = ""
    if not db_url:
        return JobManager()
    backend = "postgres" if db_url.startswith("postgres") else None
    return JobManager(backend=backend, db_url=db_url)


def coerce_int(value: Any, default: int) -> int:
    """Return value coerced to int, or default when conversion fails."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)
