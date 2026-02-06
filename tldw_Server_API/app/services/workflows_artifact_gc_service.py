from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlite3 import Error as SQLiteError

from loguru import logger

from tldw_Server_API.app.core.DB_Management.DB_Manager import create_workflows_database, get_content_backend_instance
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase

_GC_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    OSError,
    RuntimeError,
    SQLiteError,
    TypeError,
    ValueError,
)


def _now_utc() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


async def run_workflows_artifact_gc_worker(stop_event: asyncio.Event) -> None:
    """Background loop to enforce artifact retention by deleting old files and DB rows.

    Env:
      WORKFLOWS_ARTIFACT_GC_ENABLED=true|false (caller controls start)
      WORKFLOWS_ARTIFACT_RETENTION_DAYS=30
      WORKFLOWS_ARTIFACT_GC_INTERVAL_SEC=3600
    Policy:
      - Only file:// artifacts are removed from disk; DB row is removed regardless.
      - Runs are not checked; age is by artifact.created_at timestamp.
    """
    backend = get_content_backend_instance()
    db: WorkflowsDatabase = create_workflows_database(backend=backend)

    interval = int(os.getenv("WORKFLOWS_ARTIFACT_GC_INTERVAL_SEC", "3600"))
    retention_days = int(os.getenv("WORKFLOWS_ARTIFACT_RETENTION_DAYS", "30"))
    logger.info(f"Starting Workflows artifact GC worker (interval={interval}s, retention_days={retention_days})")

    while not stop_event.is_set():
        try:
            cutoff = _now_utc() - timedelta(days=retention_days)
            cutoff_iso = cutoff.isoformat()
            rows = db.list_artifacts_older_than(cutoff_iso)
            deleted = 0
            for r in rows:
                try:
                    uri = str(r.get("uri") or "")
                    if uri.startswith("file://"):
                        fp = Path(uri[7:])
                        try:
                            if fp.exists() and fp.is_file():
                                fp.unlink()
                        except OSError as fe:
                            logger.warning(f"Artifact GC: failed to delete file {fp}: {fe}")
                    db.delete_artifact(str(r.get("artifact_id")))
                    deleted += 1
                except _GC_NONCRITICAL_EXCEPTIONS as e:
                    logger.warning(f"Artifact GC: error deleting artifact {r.get('artifact_id')}: {e}")
            if deleted:
                logger.info(f"Artifact GC: deleted {deleted} artifacts older than {retention_days} days")
        except _GC_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"Artifact GC loop error: {e}")

        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=interval)

    logger.info("Workflows artifact GC worker stopped")
