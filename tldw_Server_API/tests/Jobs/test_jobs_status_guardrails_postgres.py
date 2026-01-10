import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg


def test_illegal_complete_fail_on_queued_postgres(monkeypatch, jobs_pg_dsn):


     monkeypatch.setenv("JOBS_DB_URL", jobs_pg_dsn)
    ensure_jobs_tables_pg(jobs_pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=jobs_pg_dsn)

    j = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="1")
    ok_c = jm.complete_job(int(j["id"]))
    assert ok_c is False
    j1 = jm.get_job(int(j["id"]))
    assert j1["status"] == "queued"

    ok_f = jm.fail_job(int(j["id"]), error="boom", retryable=False)
    assert ok_f is False
    j2 = jm.get_job(int(j["id"]))
    assert j2["status"] == "queued"
