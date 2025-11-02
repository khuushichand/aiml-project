#!/usr/bin/env python3
"""
Verify Jobs RLS policies with simple end-to-end checks.

Requirements:
  - psycopg installed (pip install psycopg[binary])
  - Postgres DSN in JOBS_DB_URL
  - RLS enabled: export JOBS_PG_RLS_ENABLE=true (run the app once or call ensure_jobs_tables_pg)

Usage:
  JOBS_DB_URL=postgresql://user:pass@host:5432/db python Helper_Scripts/verify_jobs_rls.py

What it does:
  - Ensures Jobs schema exists
  - Seeds a few rows across domains and owners
  - Runs queries under different RLS contexts:
      1) Admin bypass
      2) domain=chatbooks, owner=u1
      3) domain=web, owner=u2
  - Prints visible counts per table under each context
"""
import os
import sys
from contextlib import contextmanager


def _truthy(v: str | None) -> bool:
    return str(v or "").lower() in {"1", "true", "yes", "y", "on"}


def main() -> int:
    dsn = os.getenv("JOBS_DB_URL")
    if not dsn:
        print("JOBS_DB_URL not set", file=sys.stderr)
        return 2
    try:
        import psycopg
    except Exception:
        print("psycopg not installed; pip install psycopg[binary]", file=sys.stderr)
        return 2

    # Ensure schema
    try:
        from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
        ensure_jobs_tables_pg(dsn)
    except Exception as e:
        print(f"Failed to ensure Jobs schema: {e}", file=sys.stderr)
        return 2

    def seed():
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Minimal seed across two domains and two owners
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
                # One event in outbox per domain
                cur.execute(
                    "INSERT INTO job_events(job_id,domain,queue,job_type,event_type,attrs_json,owner_user_id,created_at) VALUES"
                    "(NULL,'chatbooks','default','export','jobs.seed','{}'::jsonb,'u1',NOW()),"
                    "(NULL,'web','crawler','fetch','jobs.seed','{}'::jsonb,'u2',NOW())"
                )

    def show(ctx_name: str, *, is_admin: bool, dom: str | None, owner: str | None):
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Apply RLS context via SET LOCAL in an explicit transaction
                cur.execute("BEGIN")
                cur.execute("SET LOCAL app.is_admin = %s", ("true" if is_admin else "false",))
                if dom:
                    cur.execute("SET LOCAL app.domain_allowlist = %s", (dom,))
                if owner:
                    cur.execute("SET LOCAL app.owner_user_id = %s", (owner,))
                cur.execute("SELECT COUNT(*) FROM jobs")
                jobs_c = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM job_events")
                ev_c = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM job_counters")
                cnt_c = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM job_queue_controls")
                qc_c = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM job_sla_policies")
                sla_c = int(cur.fetchone()[0])
                cur.execute("COMMIT")
        print(f"[{ctx_name}] jobs={jobs_c} events={ev_c} counters={cnt_c} queue_controls={qc_c} sla_policies={sla_c}")

    print("Seeding sample rows…")
    seed()
    print("Testing RLS views…")
    show("admin", is_admin=True, dom=None, owner=None)
    show("chatbooks:u1", is_admin=False, dom="chatbooks", owner="u1")
    show("web:u2", is_admin=False, dom="web", owner="u2")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
