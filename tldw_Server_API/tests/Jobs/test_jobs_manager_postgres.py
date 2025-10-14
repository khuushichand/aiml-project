import os
from concurrent.futures import ThreadPoolExecutor

import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup


pytestmark = pytest.mark.skipif(
    not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"
)

@pytest.fixture(scope="module", autouse=True)
def _setup(pg_schema_and_cleanup):
    # Standardize env for this module and ensure schema once
    os.environ.setdefault("TEST_MODE", "true")
    os.environ.setdefault("AUTH_MODE", "single_user")
    # Ensure target database exists (connect to 'postgres' and create if needed)
    try:
        base = pg_dsn.rsplit("/", 1)[0] + "/postgres"
        db_name = pg_dsn.rsplit("/", 1)[1].split("?")[0]
        with psycopg.connect(base, autocommit=True) as _conn:
            with _conn.cursor() as _cur:
                _cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db_name,))
                if _cur.fetchone() is None:
                    _cur.execute(f"CREATE DATABASE {db_name}")
    except Exception:
        pass
    ensure_jobs_tables_pg(pg_dsn)
    # Clean slate to avoid state bleed across modules
    with psycopg.connect(pg_dsn) as conn:
        with conn, conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE jobs RESTART IDENTITY")
    # Avoid concurrent DDL during threaded acquire by no-op'ing ensure in JobManager for this module
    try:
        import tldw_Server_API.app.core.Jobs.manager as _jm
        _jm.ensure_jobs_tables_pg = lambda url: url  # type: ignore[attr-defined]
    except Exception:
        pass
    yield


def _new_pg_manager():
    return JobManager(None, backend="postgres", db_url=pg_dsn)


def test_pg_create_acquire_complete_idempotent():
    jm = _new_pg_manager()
    idem = "pg-idem-1"
    j1 = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export", "chatbooks_job_id": "p1"},
        owner_user_id="1",
        idempotency_key=idem,
    )
    j2 = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export", "chatbooks_job_id": "p1"},
        owner_user_id="1",
        idempotency_key=idem,
    )
    assert int(j1["id"]) == int(j2["id"])  # idempotent
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id="w1")
    assert acq is not None
    assert acq["status"] == "processing"
    ok = jm.complete_job(int(acq["id"]))
    assert ok


def test_pg_concurrent_acquire_skip_locked():
    jm = _new_pg_manager()
    # Seed 4 jobs
    ids = []
    for i in range(4):
        j = jm.create_job(
            domain="chatbooks",
            queue="default",
            job_type="export",
            payload={"action": "export", "chatbooks_job_id": f"pj{i}"},
            owner_user_id="1",
        )
        ids.append(int(j["id"]))

    def acq_one(tag):
        jmx = _new_pg_manager()
        got = jmx.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id=tag)
        return got["id"] if got else None

    with ThreadPoolExecutor(max_workers=3) as ex:
        f1 = ex.submit(acq_one, "wA")
        f2 = ex.submit(acq_one, "wB")
        f3 = ex.submit(acq_one, "wC")
        r1, r2, r3 = f1.result(), f2.result(), f3.result()

    got_ids = {r for r in (r1, r2, r3) if r is not None}
    # Expect at least 2 distinct jobs acquired without conflict
    assert len(got_ids) >= 2
