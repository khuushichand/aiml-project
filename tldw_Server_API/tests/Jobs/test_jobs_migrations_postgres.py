import os

import pytest

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup


pytestmark = [
    pytest.mark.pg_jobs,
    pytest.mark.skipif(not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"),
]


@pytest.fixture(scope="module", autouse=True)
def _setup(pg_schema_and_cleanup):
    yield


def test_pg_forward_migration_adds_missing_columns_and_partial_indexes():
    ensure_jobs_tables_pg(pg_dsn)
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Try to drop a new-ish column to simulate an older schema
            try:
                cur.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS progress_message")
            except Exception:
                pass

    # Run ensure to forward-migrate
    ensure_jobs_tables_pg(pg_dsn)

    with psycopg.connect(pg_dsn) as conn:
        with conn.cursor() as cur:
            # Column should exist now
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='jobs' AND column_name='progress_message'")
            row = cur.fetchone()
            assert row is not None
            # idx_jobs_acquire_order partial index exists and is queued-only
            cur.execute("""
                SELECT indexname, indexdef FROM pg_indexes
                WHERE schemaname = current_schema() AND tablename = 'jobs' AND indexname = 'idx_jobs_acquire_order'
            """)
            row2 = cur.fetchone()
            assert row2 is not None
            assert "status = 'queued'" in (row2[1] or "")
