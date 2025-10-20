import os

import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


def _prep(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))
    # Reset metrics buffer for deterministic assertions
    reg = get_metrics_registry()
    reg.values["jobs.json_truncated_total"].clear()
    return reg


def test_json_truncation_emits_metrics_sqlite(monkeypatch, tmp_path):
    reg = _prep(monkeypatch, tmp_path)
    monkeypatch.setenv("JOBS_MAX_JSON_BYTES", "64")
    monkeypatch.setenv("JOBS_JSON_TRUNCATE", "true")

    jm = JobManager()
    # Ensure acquire gate is open in case a prior TestClient closed lifespan
    from tldw_Server_API.app.core.Jobs.manager import JobManager as _JM
    _JM.set_acquire_gate(False)

    # Payload truncation on create
    j = jm.create_job(
        domain="prompt_studio",
        queue="default",
        job_type="t",
        payload={"big": "x" * 1000},
        owner_user_id="u",
    )
    # Expect a truncation counter increment for payload
    vals = list(reg.values["jobs.json_truncated_total"])  # MetricValue deque
    assert any(v.labels.get("kind") == "payload" and v.labels.get("domain") == "prompt_studio" for v in vals)

    # Result truncation on complete
    acq = jm.acquire_next_job(domain="prompt_studio", queue="default", lease_seconds=10, worker_id="w")
    assert acq and str(acq.get("status")) == "processing"
    ok = jm.complete_job(int(acq["id"]), result={"too": "y" * 1000})
    assert ok is True
    vals2 = list(reg.values["jobs.json_truncated_total"])
    assert any(v.labels.get("kind") == "result" and v.labels.get("domain") == "prompt_studio" for v in vals2)


def test_json_caps_reject_does_not_emit_truncation_sqlite(monkeypatch, tmp_path):
    reg = _prep(monkeypatch, tmp_path)
    monkeypatch.setenv("JOBS_MAX_JSON_BYTES", "64")
    monkeypatch.delenv("JOBS_JSON_TRUNCATE", raising=False)

    jm = JobManager()
    from tldw_Server_API.app.core.Jobs.manager import JobManager as _JM
    _JM.set_acquire_gate(False)
    with pytest.raises(ValueError):
        jm.create_job(
            domain="prompt_studio",
            queue="default",
            job_type="t",
            payload={"big": "x" * 1000},
            owner_user_id="u",
        )
    # No truncation metric should be emitted when rejecting
    assert len(reg.values["jobs.json_truncated_total"]) == 0
