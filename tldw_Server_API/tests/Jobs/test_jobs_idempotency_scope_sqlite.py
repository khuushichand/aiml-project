import os
import pytest

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.fixture()
def jobs_db(tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    yield db_path


def test_idempotency_scoped_to_domain_queue_type_sqlite(jobs_db):
    jm = JobManager(jobs_db)
    key = "idem-key-123"

    # Same group (domain, queue, job_type) + same key -> same row
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1", idempotency_key=key)
    j2 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1", idempotency_key=key)
    assert int(j1["id"]) == int(j2["id"])  # idempotent

    # Different queue -> new row allowed
    j3 = jm.create_job(domain="chatbooks", queue="high", job_type="export", payload={}, owner_user_id="1", idempotency_key=key)
    assert int(j3["id"]) != int(j1["id"])  # distinct

    # Different job_type -> new row allowed
    j4 = jm.create_job(domain="chatbooks", queue="default", job_type="import", payload={}, owner_user_id="1", idempotency_key=key)
    assert int(j4["id"]) != int(j1["id"])  # distinct

    # Different domain -> new row allowed
    j5 = jm.create_job(domain="other", queue="default", job_type="export", payload={}, owner_user_id="2", idempotency_key=key)
    assert int(j5["id"]) != int(j1["id"])  # distinct
