from __future__ import annotations

"""Shared helpers for Jobs-based worker modules."""

import os
from typing import Any

from tldw_Server_API.app.core.Jobs.manager import JobManager


def jobs_manager_from_env() -> JobManager:
    """Build a JobManager based on the JOBS_DB_URL environment variable."""
    db_url = (os.getenv("JOBS_DB_URL") or "").strip()
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
