"""
Jobs module migrations (SQLite-focused).

Provides a simple helper to ensure the `jobs` table exists in a given SQLite
database path. This scaffolds the future core JobManager backend.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional
from loguru import logger


JOBS_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  uuid TEXT UNIQUE,
  domain TEXT NOT NULL,
  queue TEXT NOT NULL,
  job_type TEXT NOT NULL,
  owner_user_id TEXT,
  project_id INTEGER,
  idempotency_key TEXT UNIQUE,
  payload TEXT,
  result TEXT,
  status TEXT NOT NULL,
  priority INTEGER DEFAULT 5,
  max_retries INTEGER DEFAULT 3,
  retry_count INTEGER DEFAULT 0,
  available_at TEXT,
  started_at TEXT,
  leased_until TEXT,
  lease_id TEXT,
  worker_id TEXT,
  acquired_at TEXT,
  error_message TEXT,
  last_error TEXT,
  cancel_requested_at TEXT,
  cancelled_at TEXT,
  cancellation_reason TEXT,
  created_at TEXT DEFAULT (DATETIME('now')),
  updated_at TEXT DEFAULT (DATETIME('now')),
  completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_lookup ON jobs(domain, queue, status, available_at, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(leased_until);
CREATE INDEX IF NOT EXISTS idx_jobs_owner_status ON jobs(owner_user_id, status, created_at);

-- Keep updated_at current
CREATE TRIGGER IF NOT EXISTS trg_jobs_updated_at
AFTER UPDATE ON jobs
FOR EACH ROW
BEGIN
  UPDATE jobs SET updated_at = DATETIME('now') WHERE id = NEW.id;
END;
"""


def ensure_jobs_tables(db_path: Optional[Path] = None) -> Path:
    """Ensure the jobs table exists in the given SQLite database.

    Args:
        db_path: Optional path to the SQLite database; defaults to Databases/jobs.db

    Returns:
        Path to the database used
    """
    if db_path is None:
        db_path = Path("Databases/jobs.db")
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        with sqlite3.connect(db_path) as conn:
            conn.executescript(JOBS_SQLITE_DDL)
            conn.commit()
        logger.info(f"Ensured Jobs schema at {db_path}")
    except Exception as e:
        logger.warning(f"Failed to ensure Jobs schema at {db_path}: {e}")
    return db_path
