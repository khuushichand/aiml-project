import os
import pytest

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.pg_jobs


def _dsn_or_skip(monkeypatch):
    dsn = os.getenv("JOBS_DB_URL")
    if not dsn:
        pytest.skip("JOBS_DB_URL not configured for Postgres RLS tests")
    # Enable single-update acquire path for consistency (not strictly needed here)
    monkeypatch.setenv("JOBS_PG_SINGLE_UPDATE_ACQUIRE", "true")
    return dsn


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
    dsn = _dsn_or_skip(monkeypatch)
    ensure_jobs_tables_pg(dsn)
    _seed(dsn)

    jm = JobManager(backend="postgres", db_url=dsn)

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
    dsn = _dsn_or_skip(monkeypatch)
    ensure_jobs_tables_pg(dsn)
    _seed(dsn)
    import psycopg

    jm = JobManager(backend="postgres", db_url=dsn)

    # chatbooks:u1 context
    JobManager.set_rls_context(is_admin=False, domain_allowlist="chatbooks", owner_user_id="u1")
    conn = jm._connect()
    try:
        with jm._pg_cursor(conn) as cur:
            # job_events should only show chatbooks/u1 rows
            cur.execute("SELECT COUNT(*) FROM job_events")
            ev_count = int(cur.fetchone()[0])
            assert ev_count == 1
            # job_queue_controls should only show chatbooks rows
            cur.execute("SELECT COUNT(*) FROM job_queue_controls")
            qc_count = int(cur.fetchone()[0])
            assert qc_count == 1
            # job_sla_policies should only show chatbooks rows
            cur.execute("SELECT COUNT(*) FROM job_sla_policies")
            sla_count = int(cur.fetchone()[0])
            assert sla_count >= 1
    finally:
        conn.close()
