import os
import pytest
from urllib.parse import quote, urlparse, urlunparse

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_rls_policies_pg, ensure_jobs_tables_pg
from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.pg_jobs


def _dsn_or_skip(monkeypatch):


    base_dsn = os.getenv("JOBS_DB_URL")
    if not base_dsn:
        pytest.skip("JOBS_DB_URL not configured for Postgres RLS tests")
    # Enable single-update acquire path for consistency (not strictly needed here)
    monkeypatch.setenv("JOBS_PG_SINGLE_UPDATE_ACQUIRE", "true")
    monkeypatch.setenv("JOBS_PG_RLS_ENABLE", "true")
    role = "jobs_rls"
    monkeypatch.setenv("JOBS_PG_RLS_ROLE", role)
    password = os.getenv("JOBS_PG_RLS_PASSWORD", "jobs_rls_pw")
    monkeypatch.setenv("JOBS_PG_SKIP_SCHEMA_INIT", "true")
    # Ensure role exists with login and grants for RLS enforcement
    import psycopg
    from psycopg import sql as _sql
    with psycopg.connect(base_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            role_ident = _sql.Identifier(role)
            pwd_literal = _sql.Literal(password)
            if not cur.fetchone():
                cur.execute(_sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(role_ident, pwd_literal))
            else:
                try:
                    cur.execute(_sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(role_ident, pwd_literal))
                except Exception:
                    _ = None
            cur.execute("SELECT current_schema()")
            schema_row = cur.fetchone()
            schema_name = (schema_row[0] if schema_row else None) or "public"
            cur.execute(
                _sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    _sql.Identifier(schema_name),
                    role_ident,
                )
            )
            cur.execute(
                _sql.SQL("GRANT SELECT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(
                    _sql.Identifier(schema_name),
                    role_ident,
                )
            )

    def _with_role(dsn: str, user: str, pwd: str) -> str:
        parsed = urlparse(dsn)
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        auth = quote(user)
        if pwd:
            auth = f"{auth}:{quote(pwd)}"
        netloc = f"{auth}@{host}{port}"
        return urlunparse(
            (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
        )

    rls_dsn = _with_role(base_dsn, role, password)
    monkeypatch.setenv("JOBS_DB_URL", rls_dsn)
    return base_dsn, rls_dsn


def _row_val(row, key, idx):
    if isinstance(row, dict):
        return row.get(key)
    return row[idx] if row is not None else None


def _seed(dsn):


    import psycopg
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Minimal cleanup to keep test deterministic
            cur.execute("DELETE FROM job_events")
            cur.execute("DELETE FROM jobs")
            cur.execute("DELETE FROM job_counters")
            cur.execute("DELETE FROM job_queue_controls")
            cur.execute("DELETE FROM job_sla_policies")
            # Seed jobs across domains/owners
            cur.execute(
                "INSERT INTO jobs(domain,queue,job_type,owner_user_id,status,priority,created_at) VALUES"
                "('chatbooks','default','export','u1','queued',5,NOW()),"
                "('chatbooks','default','export','u2','queued',5,NOW()),"
                "('web','crawler','fetch','u1','queued',5,NOW()),"
                "('web','crawler','fetch','u2','queued',5,NOW())"
            )
            cur.execute(
                "INSERT INTO job_queue_controls(domain,queue,paused,drain) VALUES"
                "('chatbooks','default',false,false) ON CONFLICT (domain,queue) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES"
                "('chatbooks','default','export',2,0,0,0) ON CONFLICT (domain,queue,job_type) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO job_sla_policies(domain,queue,job_type,max_queue_latency_seconds,max_duration_seconds,enabled) VALUES"
                "('chatbooks','default','export', 60, 300, true) ON CONFLICT (domain,queue,job_type) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO job_events(job_id,domain,queue,job_type,event_type,attrs_json,owner_user_id,created_at) VALUES"
                "(NULL,'chatbooks','default','export','jobs.seed','{}'::jsonb,'u1',NOW()),"
                "(NULL,'web','crawler','fetch','jobs.seed','{}'::jsonb,'u2',NOW())"
            )


def test_rls_context_filters_results(monkeypatch):


    admin_dsn, rls_dsn = _dsn_or_skip(monkeypatch)
    ensure_jobs_tables_pg(admin_dsn)
    ensure_jobs_rls_policies_pg(admin_dsn)
    _seed(admin_dsn)

    jm = JobManager(backend="postgres", db_url=rls_dsn)

    # Admin: see all rows (bypass)
    JobManager.set_rls_context(is_admin=True, domain_allowlist=None, owner_user_id=None)
    all_rows = jm.list_jobs()
    assert len(all_rows) >= 4

    # chatbooks:u1: see exactly one job (domain + owner)
    JobManager.set_rls_context(is_admin=False, domain_allowlist="chatbooks", owner_user_id="u1")
    cb_u1 = jm.list_jobs()
    assert len(cb_u1) == 1
    assert cb_u1[0]["domain"] == "chatbooks" and cb_u1[0]["owner_user_id"] == "u1"

    # web:u2: see exactly one
    JobManager.set_rls_context(is_admin=False, domain_allowlist="web", owner_user_id="u2")
    web_u2 = jm.list_jobs()
    assert len(web_u2) == 1
    assert web_u2[0]["domain"] == "web" and web_u2[0]["owner_user_id"] == "u2"


def test_rls_applies_to_events_and_controls(monkeypatch):


    admin_dsn, rls_dsn = _dsn_or_skip(monkeypatch)
    ensure_jobs_tables_pg(admin_dsn)
    ensure_jobs_rls_policies_pg(admin_dsn)
    _seed(admin_dsn)
    import psycopg

    jm = JobManager(backend="postgres", db_url=rls_dsn)

    # chatbooks:u1 context
    JobManager.set_rls_context(is_admin=False, domain_allowlist="chatbooks", owner_user_id="u1")
    conn = jm._connect()
    try:
        with jm._pg_cursor(conn) as cur:
            # job_events should only show chatbooks/u1 rows
            cur.execute("SELECT COUNT(*) FROM job_events")
            ev_count = int(_row_val(cur.fetchone(), "count", 0) or 0)
            assert ev_count == 1
            # job_queue_controls should only show chatbooks rows
            cur.execute("SELECT COUNT(*) FROM job_queue_controls")
            qc_count = int(_row_val(cur.fetchone(), "count", 0) or 0)
            assert qc_count == 1
            # job_sla_policies should only show chatbooks rows
            cur.execute("SELECT COUNT(*) FROM job_sla_policies")
            sla_count = int(_row_val(cur.fetchone(), "count", 0) or 0)
            assert sla_count >= 1
    finally:
        conn.close()
