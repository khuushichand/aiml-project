import os
import time
from concurrent.futures import ProcessPoolExecutor

import pytest

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.tests.helpers.pg import pg_dsn, pg_schema_and_cleanup as _pg_schema_and_cleanup


pytestmark = [
    pytest.mark.pg_jobs,
    pytest.mark.pg_jobs_stress,
    pytest.mark.skipif(not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping PG stress tests"),
    pytest.mark.skipif(os.getenv("RUN_PG_JOBS_STRESS", "").lower() not in {"1", "true", "yes", "on"},
                       reason="Set RUN_PG_JOBS_STRESS=1 to enable PG stress tests")
]


@pytest.fixture(scope="module", autouse=True)
def _setup(pg_schema_and_cleanup):
    # Ensure schema and clean table once per module via shared fixture
    yield


def _worker_loop(tag: str, max_iters: int = 20, complete: bool = False):
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    acquired = []
    for _ in range(max_iters):
        j = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id=tag)
        if not j:
            # brief pause; allow other workers to make progress
            time.sleep(0.05)
            continue
        acquired.append(int(j["id"]))
        if complete:
            jm.complete_job(int(j["id"]))
    return acquired


def test_pg_concurrency_skip_locked_stress():
    # Seed jobs (a few multiples of workers)
    ensure_jobs_tables_pg(pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=pg_dsn)
    seed_count = 12
    for i in range(seed_count):
        jm.create_job(
            domain="chatbooks",
            queue="default",
            job_type="export",
            payload={"action": "export", "chatbooks_job_id": f"stress-{i}"},
            owner_user_id="1",
        )

    # Run 4 processes concurrently acquiring jobs
    with ProcessPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(_worker_loop, f"P{i}") for i in range(4)]
        try:
            results = [f.result() for f in futures]
        except KeyboardInterrupt:
            # Cancel any pending futures and request fast shutdown
            for f in futures:
                f.cancel()
            ex.shutdown(wait=False, cancel_futures=True)
            raise

    flat = [jid for sub in results for jid in sub]
    # there may be duplicates if a worker reacquires after lease expiry; enforce uniqueness expectation
    # given short test window and small lease_seconds, we expect most to be unique
    unique = set(flat)
    assert len(unique) >= min(seed_count, 6)
    # ensure no process acquired the same job id twice in its own list
    for ids in results:
        assert len(ids) == len(set(ids))

    # Strict coverage mode (opt-in): expect full coverage of a new seeded batch
    if os.getenv("RUN_PG_JOBS_STRESS_STRICT", "").lower() in {"1", "true", "yes", "on"}:
        # Seed a separate batch
        batch_ids = []
        for i in range(seed_count):
            jj = jm.create_job(
                domain="chatbooks",
                queue="default",
                job_type="export",
                payload={"action": "export", "chatbooks_job_id": f"strict-{i}"},
                owner_user_id="1",
            )
            batch_ids.append(int(jj["id"]))

        with ProcessPoolExecutor(max_workers=4) as ex:
            futures2 = [ex.submit(_worker_loop, f"S{i}", 50, True) for i in range(4)]
            try:
                results2 = [f.result() for f in futures2]
            except KeyboardInterrupt:
                for f in futures2:
                    f.cancel()
                ex.shutdown(wait=False, cancel_futures=True)
                raise

        flat2 = [jid for sub in results2 for jid in sub]
        unique2 = set(flat2)
        assert len(unique2.intersection(set(batch_ids))) == len(batch_ids)
