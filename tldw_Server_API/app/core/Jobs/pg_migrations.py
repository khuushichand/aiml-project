"""
Jobs module migrations (PostgreSQL).

Provides SQL DDL to provision a `jobs` table compatible with the core JobManager
semantics. This module does not connect to Postgres directly; callers should
apply this DDL using their own connection or via a future Postgres JobManager.
"""

JOBS_POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
  id SERIAL PRIMARY KEY,
  uuid TEXT UNIQUE,
  domain TEXT NOT NULL,
  queue TEXT NOT NULL,
  job_type TEXT NOT NULL,
  owner_user_id TEXT,
  project_id INTEGER,
  idempotency_key TEXT,
  payload JSONB,
  result JSONB,
  status TEXT NOT NULL CHECK (status IN ('queued','processing','completed','failed','cancelled')),
  priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
  max_retries INTEGER DEFAULT 3 CHECK (max_retries >= 0 AND max_retries <= 100),
  retry_count INTEGER DEFAULT 0,
  available_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  leased_until TIMESTAMPTZ,
  lease_id TEXT,
  worker_id TEXT,
  acquired_at TIMESTAMPTZ,
  error_message TEXT,
  error_code TEXT,
  error_class TEXT,
  error_stack JSONB,
  last_error TEXT,
  cancel_requested_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  progress_percent REAL CHECK (progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)),
  progress_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jobs_lookup
  ON jobs(domain, queue, status, available_at, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(leased_until);
CREATE INDEX IF NOT EXISTS idx_jobs_owner_status ON jobs(owner_user_id, status, created_at);

-- updated_at trigger
CREATE OR REPLACE FUNCTION set_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jobs_updated_at ON jobs;
CREATE TRIGGER trg_jobs_updated_at
BEFORE UPDATE ON jobs
FOR EACH ROW EXECUTE FUNCTION set_jobs_updated_at();

-- Optional archive table (used when JOBS_ARCHIVE_BEFORE_DELETE=true)
CREATE TABLE IF NOT EXISTS jobs_archive (
  id INTEGER,
  uuid TEXT,
  domain TEXT NOT NULL,
  queue TEXT NOT NULL,
  job_type TEXT NOT NULL,
  owner_user_id TEXT,
  project_id INTEGER,
  idempotency_key TEXT,
  payload JSONB,
  result JSONB,
  status TEXT NOT NULL,
  priority INTEGER,
  max_retries INTEGER,
  retry_count INTEGER,
  available_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  leased_until TIMESTAMPTZ,
  lease_id TEXT,
  worker_id TEXT,
  acquired_at TIMESTAMPTZ,
  error_message TEXT,
  last_error TEXT,
  cancel_requested_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  progress_percent REAL,
  progress_message TEXT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  archived_at TIMESTAMPTZ DEFAULT NOW()
);

-- Status-focused partial indexes to speed common counts and lookups
CREATE INDEX IF NOT EXISTS idx_jobs_status_queued ON jobs(domain, queue, job_type, priority, available_at, created_at) WHERE status='queued';
CREATE INDEX IF NOT EXISTS idx_jobs_status_processing ON jobs(domain, queue, job_type, leased_until) WHERE status='processing';

-- Composite uniqueness for idempotency scoped by domain/queue/job_type (NULL key allowed)
-- A unique index is created outside the DDL block using autocommit.
"""

def ensure_jobs_tables_pg(db_url: str) -> str:
    """Ensure the jobs table exists in the given PostgreSQL database.

    Returns the db_url passed through for convenience.
    """
    try:
        import psycopg
    except Exception as e:  # pragma: no cover - environment dependent
        raise RuntimeError("psycopg is required for PostgreSQL Jobs backend. Install extras 'db_postgres'.") from e

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(JOBS_POSTGRES_DDL)
            conn.commit()
        # Create hot-path indexes concurrently (outside transaction) when possible
        try:
            with psycopg.connect(db_url, autocommit=True) as c2:
                with c2.cursor() as k:
                    # Ready vs scheduled scans
                    k.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_status_available_at ON jobs(status, available_at)")
                    # Composite unique for idempotency (NULLs are allowed and do not conflict)
                    k.execute("CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_idempotent_unique ON jobs(domain, queue, job_type, idempotency_key)")
        except Exception:
            # Best-effort; not fatal
            pass
    except Exception as e:
        # Attempt to create database if it doesn't exist, then retry
        msg = str(e)
        if "does not exist" in msg and "database" in msg:
            try:
                base = db_url.rsplit("/", 1)[0] + "/postgres"
                db_name = db_url.rsplit("/", 1)[1].split("?")[0]
                with psycopg.connect(base, autocommit=True) as conn2:
                    with conn2.cursor() as cur2:
                        cur2.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db_name,))
                        if cur2.fetchone() is None:
                            cur2.execute(f"CREATE DATABASE {db_name}")
                # Retry DDL
                with psycopg.connect(db_url) as conn3:
                    with conn3.cursor() as cur3:
                        cur3.execute(JOBS_POSTGRES_DDL)
                    conn3.commit()
            except Exception as e2:
                raise RuntimeError(f"Failed to ensure Jobs schema in Postgres: {e2}") from e2
        else:
            # Re-raise with context for other errors
            raise RuntimeError(f"Failed to ensure Jobs schema in Postgres: {e}") from e
    return db_url
