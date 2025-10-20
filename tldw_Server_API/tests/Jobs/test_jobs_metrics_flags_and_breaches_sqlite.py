import os
from datetime import datetime, timedelta

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


def _reset_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))


def test_queue_flag_metrics_sqlite(monkeypatch, tmp_path):
    _reset_env(monkeypatch, tmp_path)
    ensure_jobs_tables(tmp_path / "jobs.db")
    reg = get_metrics_registry()
    reg.values["jobs.queue_flag"].clear()
    jm = JobManager()
    # Pause
    flags = jm.set_queue_control("ps", "default", "pause")
    assert flags["paused"] is True
    vals = list(reg.values["jobs.queue_flag"])  # MetricValue deque
    assert any(v.labels.get("domain") == "ps" and v.labels.get("queue") == "default" and v.labels.get("flag") == "paused" and v.value == 1.0 for v in vals)
    # Drain
    flags2 = jm.set_queue_control("ps", "default", "drain")
    assert flags2["paused"] is True and flags2["drain"] is True
    vals2 = list(reg.values["jobs.queue_flag"])  # includes paused & drain records
    assert any(v.labels.get("flag") == "drain" and v.value == 1.0 for v in vals2)


def test_sla_breaches_metrics_sqlite(monkeypatch, tmp_path):
    _reset_env(monkeypatch, tmp_path)
    ensure_jobs_tables(tmp_path / "jobs.db")
    reg = get_metrics_registry()
    reg.values["jobs.sla_breaches_total"].clear()
    jm = JobManager()
    # Set SLA: force immediate breach
    jm.upsert_sla_policy(domain="ps", queue="default", job_type="slow", max_queue_latency_seconds=0, max_duration_seconds=0, enabled=True)
    j = jm.create_job(domain="ps", queue="default", job_type="slow", payload={}, owner_user_id="u")
    # Backdate created_at
    conn = jm._connect()
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE jobs SET created_at = ? WHERE id = ?", (cutoff, int(j["id"])) )
        conn.commit()
    finally:
        conn.close()
    # Acquire, then simulate breach via internal helper (unit-level)
    from tldw_Server_API.app.core.Jobs.manager import JobManager as _JM
    _JM.set_acquire_gate(False)
    acq = jm.acquire_next_job(domain="ps", queue="default", lease_seconds=5, worker_id="w")
    assert acq
    # Call internal breach recorder to emit metrics (queue_latency)
    jm._record_sla_breach(int(j["id"]), "ps", "default", "slow", "queue_latency", 10.0, 0.0)
    # And a duration breach
    jm._record_sla_breach(int(j["id"]), "ps", "default", "slow", "duration", 20.0, 0.0)
    vals = list(reg.values["jobs.sla_breaches_total"])  # counters include labels
    assert len(vals) >= 1
