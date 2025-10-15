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
  -- include 'quarantined' for poison message handling
  status TEXT NOT NULL CHECK (status IN ('queued','processing','completed','failed','cancelled','quarantined')),
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
  completion_token TEXT,
  failure_streak_code TEXT,
  failure_streak_count INTEGER DEFAULT 0,
  quarantined_at TIMESTAMPTZ,
  progress_percent REAL CHECK (progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)),
  progress_message TEXT,
  -- correlation
  request_id TEXT,
  trace_id TEXT,
  -- structured failure history (JSONB array of objects)
  failure_timeline JSONB,
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
  completion_token TEXT,
  failure_streak_code TEXT,
  failure_streak_count INTEGER,
  quarantined_at TIMESTAMPTZ,
  progress_percent REAL,
  progress_message TEXT,
  request_id TEXT,
  trace_id TEXT,
  failure_timeline JSONB,
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
        # Forward-migrate older installs: add missing columns that newer code expects
        try:
            with psycopg.connect(db_url, autocommit=True) as cfix:
                with cfix.cursor() as f:
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS completion_token TEXT")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS failure_streak_code TEXT")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS failure_streak_count INTEGER DEFAULT 0")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS quarantined_at TIMESTAMPTZ")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS progress_percent REAL")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS progress_message TEXT")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS request_id TEXT")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS trace_id TEXT")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS failure_timeline JSONB")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS error_code TEXT")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS error_class TEXT")
                    f.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS error_stack JSONB")
        except Exception:
            # Best-effort; if the DB already has these or lacks permissions, continue
            pass
        # Create hot-path indexes concurrently (outside transaction) when possible
        try:
            with psycopg.connect(db_url, autocommit=True) as c2:
                with c2.cursor() as k:
                    # Ready vs scheduled scans
                    k.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_status_available_at ON jobs(status, available_at)")
                    # Composite unique for idempotency (NULLs are allowed and do not conflict)
                    k.execute("CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_idempotent_unique ON jobs(domain, queue, job_type, idempotency_key)")
                    # Optional partial index to speed common hot-path queries
                    try:
                        k.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_hot ON jobs(domain, queue, job_type, priority, available_at, created_at) WHERE status IN ('queued','processing')")
                    except Exception:
                        pass
                    # Acquisition ordering index: priority ASC (lower number = higher priority),
                    # then available/created, then id; queued only. The ORDER BY in queries
                    # is explicit; this index simply supports that access pattern.
                    try:
                        k.execute(
                            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_acquire_order ON jobs (priority, COALESCE(available_at, created_at), id) WHERE status = 'queued'"
                        )
                    except Exception:
                        # Older PG versions or permission issues: non-fatal
                        pass
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
    # Optionally enable RLS policies for domain scoping when requested
    try:
        import os as _os_rls
        if str(_os_rls.getenv("JOBS_PG_RLS_ENABLE", "")).lower() in {"1","true","yes","y","on"}:
            try:
                ensure_jobs_rls_policies_pg(db_url)
            except Exception:
                pass
    except Exception:
        pass
    return db_url


def ensure_jobs_rls_policies_pg(db_url: str) -> None:
    """Enable Postgres Row Level Security (RLS) for domain scoping.

    Policies restrict SELECT/UPDATE/DELETE to rows where jobs.domain is in
    current_setting('app.domain_allowlist', true), if set.
    """
    try:
        import psycopg  # type: ignore
    except Exception:
        return
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Enable RLS
                try:
                    cur.execute("ALTER TABLE jobs ENABLE ROW LEVEL SECURITY")
                except Exception:
                    pass
                # Check existing policies
                cur.execute("SELECT polname FROM pg_policies WHERE schemaname = current_schema() AND tablename = 'jobs'")
                existing = {r[0] for r in cur.fetchall()}
                if 'jobs_domain_select' not in existing:
                    cur.execute(
                        """
                        CREATE POLICY jobs_domain_select ON jobs FOR SELECT
                        USING (
                          current_setting('app.domain_allowlist', true) IS NULL OR
                          domain = ANY(string_to_array(current_setting('app.domain_allowlist', true), ','))
                        )
                        """
                    )
                if 'jobs_domain_modify' not in existing:
                    cur.execute(
                        """
                        CREATE POLICY jobs_domain_modify ON jobs FOR UPDATE, DELETE
                        USING (
                          current_setting('app.domain_allowlist', true) IS NULL OR
                          domain = ANY(string_to_array(current_setting('app.domain_allowlist', true), ','))
                        )
                        """
                    )
    except Exception:
        return


def ensure_job_counters_pg(db_url: str) -> None:
    """Ensure per-queue counters table exists in PG."""
    try:
        import psycopg
    except Exception:
        return
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS job_counters (
                      domain TEXT NOT NULL,
                      queue TEXT NOT NULL,
                      job_type TEXT NOT NULL,
                      ready_count INTEGER DEFAULT 0,
                      scheduled_count INTEGER DEFAULT 0,
                      processing_count INTEGER DEFAULT 0,
                      quarantined_count INTEGER DEFAULT 0,
                      updated_at TIMESTAMPTZ DEFAULT NOW(),
                      PRIMARY KEY (domain, queue, job_type)
                    );
                    """
                )
                try:
                    cur.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_counters_domain_queue ON job_counters(domain, queue)")
                except Exception:
                    pass
    except Exception:
        return
