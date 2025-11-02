import os

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors as pg_errors

from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup
from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = [
    pytest.mark.pg_jobs,
    pytest.mark.skipif(not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"),
]


@pytest.fixture(scope="module", autouse=True)
def _setup(pg_schema_and_cleanup):
    yield


def test_acquire_serialization_conflict_then_retry_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    jm.create_job(domain="ps", queue="default", job_type="t", payload={}, owner_user_id="u")

    # Monkeypatch psycopg.connect to raise SerializationFailure on first cursor.execute
    real_connect = __import__("psycopg").connect

    class FlakyCursor:
        def __init__(self, cur):
            self._cur = cur
            self._calls = 0

        def execute(self, *a, **k):
            if self._calls == 0:
                self._calls += 1
                raise pg_errors.SerializationFailure("serialization_failure")
            return self._cur.execute(*a, **k)

        def fetchone(self):
            return self._cur.fetchone()

        def fetchall(self):
            return self._cur.fetchall()

        def __enter__(self):
            self._cur.__enter__()
            return self
        def __exit__(self, exc_type, exc, tb):
            return self._cur.__exit__(exc_type, exc, tb)

    class FlakyConn:
        def __init__(self, *a, **k):
            self._conn = real_connect(*a, **k)
        def cursor(self, *a, **k):
            return FlakyCursor(self._conn.cursor(*a, **k))
        def __enter__(self):
            self._conn.__enter__()
            return self
        def __exit__(self, exc_type, exc, tb):
            return self._conn.__exit__(exc_type, exc, tb)
        def close(self):
            return self._conn.close()

    def fake_connect(*a, **k):
        return FlakyConn(*a, **k)

    monkeypatch.setattr("psycopg.connect", fake_connect)
    with pytest.raises(pg_errors.SerializationFailure):
        jm.acquire_next_job(domain="ps", queue="default", lease_seconds=5, worker_id="w")

    # Restore and retry
    monkeypatch.setattr("psycopg.connect", real_connect)
    acq = jm.acquire_next_job(domain="ps", queue="default", lease_seconds=5, worker_id="w")
    assert acq and str(acq.get("status")) == "processing"
