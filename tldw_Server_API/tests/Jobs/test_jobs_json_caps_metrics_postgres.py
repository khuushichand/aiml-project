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


def test_json_truncation_emits_metrics_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    monkeypatch.setenv("JOBS_MAX_JSON_BYTES", "64")
    monkeypatch.setenv("JOBS_JSON_TRUNCATE", "true")
    reg = get_metrics_registry()
    reg.values["jobs.json_truncated_total"].clear()

    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    j = jm.create_job(
        domain="prompt_studio",
        queue="default",
        job_type="t",
        payload={"big": "x" * 1000},
        owner_user_id="u",
    )
    vals = list(reg.values["jobs.json_truncated_total"])  # MetricValue deque
    assert any(v.labels.get("kind") == "payload" for v in vals)

    acq = jm.acquire_next_job(domain="prompt_studio", queue="default", lease_seconds=10, worker_id="w")
    assert acq
    ok = jm.complete_job(int(acq["id"]), result={"too": "y" * 1000})
    assert ok is True
    vals2 = list(reg.values["jobs.json_truncated_total"])  # payload + result
    assert any(v.labels.get("kind") == "result" for v in vals2)
