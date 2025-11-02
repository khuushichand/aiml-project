import os

import pytest

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


pytestmark = [
    pytest.mark.pg_jobs,
    pytest.mark.skipif(not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"),
]


@pytest.fixture(scope="module", autouse=True)
def _setup(pg_schema_and_cleanup):
    yield


def test_queue_flag_metrics_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    reg = get_metrics_registry()
    reg.values["jobs.queue_flag"].clear()
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    flags = jm.set_queue_control("ps", "default", "pause")
    assert flags["paused"] is True
    vals = list(reg.values["jobs.queue_flag"])  # MetricValue deque
    assert any(v.labels.get("domain") == "ps" and v.labels.get("queue") == "default" and v.labels.get("flag") == "paused" and v.value == 1.0 for v in vals)


def test_sla_breaches_metrics_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    reg = get_metrics_registry()
    reg.values["jobs.sla_breaches_total"].clear()
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    # Directly exercise internal breach recorder (unit-level)
    jm._record_sla_breach(1, "ps", "default", "slow", "queue_latency", 10.0, 0.0)
    jm._record_sla_breach(1, "ps", "default", "slow", "duration", 20.0, 0.0)
    vals = list(reg.values["jobs.sla_breaches_total"])  # counters include labels
    assert len(vals) >= 2
