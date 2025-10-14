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
  idempotency_key TEXT UNIQUE,
  payload JSONB,
  result JSONB,
  status TEXT NOT NULL,
  priority INTEGER DEFAULT 5,
  max_retries INTEGER DEFAULT 3,
  retry_count INTEGER DEFAULT 0,
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
    except Exception as e:
        # Re-raise with context
        raise RuntimeError(f"Failed to ensure Jobs schema in Postgres: {e}") from e
    return db_url
