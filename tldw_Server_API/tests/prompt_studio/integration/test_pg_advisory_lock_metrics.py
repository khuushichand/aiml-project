import pytest


class _StubMM:
    def __init__(self):
        self.increments = []

    def increment(self, name, value=1, labels=None):
        self.increments.append((name, value, labels or {}))


class _StubPSMetrics:
    def __init__(self):
        self.metrics_manager = _StubMM()


pytestmark = pytest.mark.integration


def test_pg_advisory_lock_metrics_increment(prompt_studio_dual_backend_db, monkeypatch):
    label, db = prompt_studio_dual_backend_db
    if label != "postgres":
        pytest.skip("Postgres-specific test")

    # Stub metrics in monitoring module so DB import picks it up
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import monitoring as mon
    stub = _StubPSMetrics()
    monkeypatch.setattr(mon, "prompt_studio_metrics", stub, raising=True)

    # Create one job and acquire
    db.create_job(job_type="evaluation", entity_id=0, payload={})
    job = db.acquire_next_job()
    assert job is not None

    names = [n for (n, _, _) in stub.metrics_manager.increments]
    assert "prompt_studio.pg_advisory.lock_attempts_total" in names, "lock attempts not recorded"
    assert "prompt_studio.pg_advisory.locks_acquired_total" in names, "locks acquired not recorded"
    assert "prompt_studio.pg_advisory.unlocks_total" in names, "unlocks not recorded"
