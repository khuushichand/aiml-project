import os
from datetime import datetime, timedelta

import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.mark.unit
def test_acquire_order_priority_and_availability_sqlite(tmp_path, monkeypatch):
    # Use dedicated SQLite DB
    db_path = tmp_path / "jobs_test.db"
    jm = JobManager(db_path=db_path)

    domain = "acqtest"
    queue = "default"

    # Create queued ready jobs with varying priorities
    j_low = jm.create_job(
        domain=domain,
        queue=queue,
        job_type="low",
        payload={},
        owner_user_id=None,
        priority=5,
    )
    j_high = jm.create_job(
        domain=domain,
        queue=queue,
        job_type="high",
        payload={},
        owner_user_id=None,
        priority=1,
    )
    # Scheduled job in the future should not be acquired yet
    future = datetime.utcnow() + timedelta(hours=1)
    j_sched = jm.create_job(
        domain=domain,
        queue=queue,
        job_type="scheduled",
        payload={},
        owner_user_id=None,
        priority=3,
        available_at=future,
    )
    # Another ready job
    j_mid = jm.create_job(
        domain=domain,
        queue=queue,
        job_type="mid",
        payload={},
        owner_user_id=None,
        priority=3,
    )

    # Acquire up to 3 jobs; should exclude scheduled job and honor priority ASC
    got = jm.acquire_next_jobs(domain=domain, queue=queue, lease_seconds=30, worker_id="worker-1", limit=3)
    assert len(got) == 3
    # Priorities should be [1, 3, 5]
    assert [int(g.get("priority")) for g in got] == [1, 3, 5]
    # Ensure scheduled job remains queued
    queued = jm.list_jobs(domain=domain, queue=queue, status="queued")
    assert any(j.get("job_type") == "scheduled" for j in queued)
