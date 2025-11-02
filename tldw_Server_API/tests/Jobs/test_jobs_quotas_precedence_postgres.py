import pytest

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.tests.helpers.pg import pg_dsn
from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = [
    pytest.mark.pg_jobs,
    pytest.mark.skipif(not pg_dsn, reason="JOBS_DB_URL/POSTGRES_TEST_DSN not set; skipping Postgres jobs tests"),
]


def _assert_create_limit_pg(jm: JobManager, *, domain: str, user: str, limit: int) -> None:
    for i in range(limit):
        jm.create_job(domain=domain, queue="default", job_type=f"t{i}", payload={}, owner_user_id=user)
    import pytest as _pytest
    with _pytest.raises(ValueError):
        jm.create_job(domain=domain, queue="default", job_type="overflow", payload={}, owner_user_id=user)


def test_max_queued_precedence_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    jm = JobManager(backend="postgres", db_url=pg_dsn)

    monkeypatch.setenv("JOBS_QUOTA_MAX_QUEUED", "5")
    monkeypatch.setenv("JOBS_QUOTA_MAX_QUEUED_CHATBOOKS", "3")
    monkeypatch.setenv("JOBS_QUOTA_MAX_QUEUED_USER_1", "2")
    monkeypatch.setenv("JOBS_QUOTA_MAX_QUEUED_CHATBOOKS_USER_1", "1")

    _assert_create_limit_pg(jm, domain="chatbooks", user="1", limit=1)
    _assert_create_limit_pg(jm, domain="other", user="1", limit=2)
    _assert_create_limit_pg(jm, domain="chatbooks", user="2", limit=3)
    _assert_create_limit_pg(jm, domain="other", user="2", limit=5)


def test_inflight_precedence_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    jm = JobManager(backend="postgres", db_url=pg_dsn)

    monkeypatch.setenv("JOBS_QUOTA_MAX_INFLIGHT", "5")
    monkeypatch.setenv("JOBS_QUOTA_MAX_INFLIGHT_CHATBOOKS", "2")
    monkeypatch.setenv("JOBS_QUOTA_MAX_INFLIGHT_USER_1", "3")
    monkeypatch.setenv("JOBS_QUOTA_MAX_INFLIGHT_CHATBOOKS_USER_1", "1")

    for d, u, n in [("chatbooks", "1", 3), ("other", "1", 4), ("chatbooks", "2", 3), ("other", "2", 6)]:
        for i in range(n):
            jm.create_job(domain=d, queue="default", job_type=f"t{d}{u}{i}", payload={}, owner_user_id=u)

    def acquire_up_to(domain: str, user: str, limit: int) -> int:
        cnt = 0
        while cnt < limit + 1:
            acq = jm.acquire_next_job(domain=domain, queue="default", lease_seconds=30, worker_id=f"w{domain}{user}{cnt}", owner_user_id=user)
            if not acq:
                break
            cnt += 1
        return cnt

    assert acquire_up_to("chatbooks", "1", 1) == 1
    assert acquire_up_to("other", "1", 3) == 3
    assert acquire_up_to("chatbooks", "2", 2) == 2
    assert acquire_up_to("other", "2", 5) == 5


def test_submits_per_minute_precedence_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    jm = JobManager(backend="postgres", db_url=pg_dsn)

    monkeypatch.setenv("JOBS_QUOTA_SUBMITS_PER_MIN", "1")
    monkeypatch.setenv("JOBS_QUOTA_SUBMITS_PER_MIN_CHATBOOKS", "1")
    monkeypatch.setenv("JOBS_QUOTA_SUBMITS_PER_MIN_USER_1", "2")
    monkeypatch.setenv("JOBS_QUOTA_SUBMITS_PER_MIN_CHATBOOKS_USER_1", "3")

    for i in range(3):
        jm.create_job(domain="chatbooks", queue="default", job_type=f"a{i}", payload={}, owner_user_id="1")
    with pytest.raises(ValueError):
        jm.create_job(domain="chatbooks", queue="default", job_type="a4", payload={}, owner_user_id="1")

    jm.create_job(domain="other", queue="default", job_type="b1", payload={}, owner_user_id="1")
    jm.create_job(domain="other", queue="default", job_type="b2", payload={}, owner_user_id="1")
    with pytest.raises(ValueError):
        jm.create_job(domain="other", queue="default", job_type="b3", payload={}, owner_user_id="1")

    jm.create_job(domain="chatbooks", queue="default", job_type="c1", payload={}, owner_user_id="2")
    with pytest.raises(ValueError):
        jm.create_job(domain="chatbooks", queue="default", job_type="c2", payload={}, owner_user_id="2")

    jm.create_job(domain="other", queue="default", job_type="d1", payload={}, owner_user_id="2")
    with pytest.raises(ValueError):
        jm.create_job(domain="other", queue="default", job_type="d2", payload={}, owner_user_id="2")
