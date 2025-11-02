import pytest

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.fixture()
def jobs_db(tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    yield db_path


def test_illegal_complete_on_queued_is_noop_sqlite(jobs_db):
    jm = JobManager(jobs_db)
    j = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="1")
    ok = jm.complete_job(int(j["id"]))
    assert ok is False
    j2 = jm.get_job(int(j["id"]))
    assert j2["status"] == "queued"


def test_illegal_fail_on_queued_is_noop_sqlite(jobs_db):
    jm = JobManager(jobs_db)
    j = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="1")
    ok = jm.fail_job(int(j["id"]), error="boom", retryable=False)
    assert ok is False
    j2 = jm.get_job(int(j["id"]))
    assert j2["status"] == "queued"
