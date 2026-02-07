import time
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.unit


def _acquire_with_timeout(
    jm: JobManager,
    *,
    domain: str,
    queue: str,
    worker_id: str,
    timeout_s: float = 3.0,
) -> dict | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        acquired = jm.acquire_next_job(
            domain=domain,
            queue=queue,
            lease_seconds=5,
            worker_id=worker_id,
        )
        if acquired:
            return acquired
        time.sleep(0.05)
    return None


def test_tldw_test_mode_enables_test_retry_semantics_for_quarantine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "y")
    monkeypatch.delenv("JOBS_QUARANTINE_THRESHOLD", raising=False)
    monkeypatch.setenv("JOBS_EVENTS_OUTBOX", "0")

    jm = JobManager(tmp_path / "jobs_tldw_mode.db")
    created = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="1",
        max_retries=5,
    )

    acq1 = _acquire_with_timeout(jm, domain="chatbooks", queue="default", worker_id="w1")
    assert acq1 and int(acq1["id"]) == int(created["id"])
    assert jm.fail_job(
        int(created["id"]),
        error="boom-1",
        error_code="E1",
        retryable=True,
        backoff_seconds=0,
        worker_id="w1",
        lease_id=str(acq1.get("lease_id")),
    )

    acq2 = _acquire_with_timeout(jm, domain="chatbooks", queue="default", worker_id="w2")
    assert acq2 and int(acq2["id"]) == int(created["id"])
    assert jm.fail_job(
        int(created["id"]),
        error="boom-2",
        error_code="E1",
        retryable=True,
        backoff_seconds=0,
        worker_id="w2",
        lease_id=str(acq2.get("lease_id")),
    )

    row = jm.get_job(int(created["id"]))
    assert row is not None
    assert row.get("status") == "queued"
