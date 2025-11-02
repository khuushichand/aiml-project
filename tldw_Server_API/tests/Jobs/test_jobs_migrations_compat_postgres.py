import pytest

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.tests.helpers.pg import pg_dsn
from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg


pytestmark = [
    pytest.mark.pg_jobs,
    pytest.mark.skipif(not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"),
]


def test_pg_schema_has_aux_tables_and_indexes():
    ensure_jobs_tables_pg(pg_dsn)
    with psycopg.connect(pg_dsn) as conn:
        with conn.cursor() as cur:
            # Tables exist
            def table_exists(name: str) -> bool:
                cur.execute("SELECT to_regclass(%s)", (name,))
                return cur.fetchone()[0] is not None

            assert table_exists("jobs")
            assert table_exists("job_events")
            assert table_exists("job_queue_controls")
            assert table_exists("job_attachments")
            assert table_exists("job_sla_policies")
            assert table_exists("job_counters")

            # Indexes present
            cur.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() AND tablename = 'jobs'"
            )
            idxs = {r[0] for r in cur.fetchall()}
            assert "idx_jobs_status_available_at" in idxs
            assert "idx_jobs_idempotent_unique" in idxs
