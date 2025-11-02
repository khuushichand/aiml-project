import os
import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.fixture()
def events(monkeypatch):
    calls = []

    def _emit(name, job=None, attrs=None):
        calls.append((name, job or {}, attrs or {}))

    # Enable events and patch the emitter
    monkeypatch.setenv("JOBS_EVENTS_ENABLED", "true")
    from tldw_Server_API.app.core.Jobs import manager as mgr
    monkeypatch.setattr(mgr, "emit_job_event", _emit, raising=True)
    return calls


def test_events_emitted_for_core_paths_sqlite(tmp_path, monkeypatch, events):
    # Use temp DB via explicit path
    db_path = tmp_path / "jobs.db"
    jm = JobManager(db_path)

    # Create (emits job.created)
    j = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="u1")
    assert any(n == "job.created" for (n, _j, _a) in events)

    # Acquire (emits job.acquired)
    acq = jm.acquire_next_job(domain="d", queue="default", lease_seconds=5, worker_id="w1")
    assert acq is not None
    assert any(n == "job.acquired" for (n, _j, _a) in events)

    # Renew (emits job.lease_renewed)
    ok = jm.renew_job_lease(int(acq["id"]), seconds=3)
    assert ok
    assert any(n == "job.lease_renewed" for (n, _j, _a) in events)

    # Retryable fail (emits job.retry_scheduled)
    ok2 = jm.fail_job(int(acq["id"]), error="boom", retryable=True, backoff_seconds=1)
    assert ok2
    assert any(n == "job.retry_scheduled" for (n, _j, _a) in events)

    # Acquire again and terminal fail (emits job.failed)
    acq2 = jm.acquire_next_job(domain="d", queue="default", lease_seconds=5, worker_id="w1")
    assert acq2 is not None
    ok3 = jm.fail_job(int(acq2["id"]), error="boom2", retryable=False)
    assert ok3
    assert any(n == "job.failed" for (n, _j, _a) in events)

    # Cancel path (create new queued, then cancel -> job.cancelled)
    j2 = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="u1")
    ok4 = jm.cancel_job(int(j2["id"]))
    assert ok4
    assert any(n == "job.cancelled" for (n, _j, _a) in events)

    # Prune (emits jobs.pruned)
    deleted = jm.prune_jobs(statuses=["failed", "cancelled"], older_than_days=0, domain="d")
    assert isinstance(deleted, int)
    assert any(n == "jobs.pruned" for (n, _j, _a) in events)

    # TTL sweep (emits jobs.ttl_sweep) - cancel queued immediately via age_seconds=0
    affected = jm.apply_ttl_policies(age_seconds=0, runtime_seconds=None, action="cancel", domain="d")
    assert isinstance(affected, int)
    assert any(n == "jobs.ttl_sweep" for (n, _j, _a) in events)
