import pytest

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


def _assert_create_limit(jm: JobManager, *, domain: str, user: str, limit: int) -> None:
    # Create exactly `limit` succeeds
    for i in range(limit):
        jm.create_job(domain=domain, queue="default", job_type=f"t{i}", payload={}, owner_user_id=user)
    # Next create should fail
    with pytest.raises(ValueError):
        jm.create_job(domain=domain, queue="default", job_type="overflow", payload={}, owner_user_id=user)


def test_max_queued_precedence_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs_quota_prec.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)

    # Precedence in _quota_get: domain+user > user > domain > global
    monkeypatch.setenv("JOBS_QUOTA_MAX_QUEUED", "5")
    monkeypatch.setenv("JOBS_QUOTA_MAX_QUEUED_CHATBOOKS", "3")
    monkeypatch.setenv("JOBS_QUOTA_MAX_QUEUED_USER_1", "2")
    monkeypatch.setenv("JOBS_QUOTA_MAX_QUEUED_CHATBOOKS_USER_1", "1")

    # User 1 + chatbooks => domain+user scope (1)
    _assert_create_limit(jm, domain="chatbooks", user="1", limit=1)

    # User 1 + other => user scope (2)
    _assert_create_limit(jm, domain="other", user="1", limit=2)

    # User 2 + chatbooks => domain scope (3)
    _assert_create_limit(jm, domain="chatbooks", user="2", limit=3)

    # User 2 + other => global (5)
    _assert_create_limit(jm, domain="other", user="2", limit=5)


def test_inflight_precedence_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs_quota_inflight_prec.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)

    # Precedence for inflight
    monkeypatch.setenv("JOBS_QUOTA_MAX_INFLIGHT", "5")
    monkeypatch.setenv("JOBS_QUOTA_MAX_INFLIGHT_CHATBOOKS", "2")
    monkeypatch.setenv("JOBS_QUOTA_MAX_INFLIGHT_USER_1", "3")
    monkeypatch.setenv("JOBS_QUOTA_MAX_INFLIGHT_CHATBOOKS_USER_1", "1")

    # Seed enough queued jobs per (domain,user)
    for d, u, n in [("chatbooks", "1", 3), ("other", "1", 4), ("chatbooks", "2", 3), ("other", "2", 6)]:
        for i in range(n):
            jm.create_job(domain=d, queue="default", job_type=f"t{d}{u}{i}", payload={}, owner_user_id=u)

    # Helper to attempt acquiring up to `limit`; returns actual acquired count
    def acquire_up_to(domain: str, user: str, limit: int) -> int:
        cnt = 0
        while cnt < limit + 1:  # attempt one over
            acq = jm.acquire_next_job(domain=domain, queue="default", lease_seconds=30, worker_id=f"w{domain}{user}{cnt}", owner_user_id=user)
            if not acq:
                break
            cnt += 1
        return cnt

    # User 1 + chatbooks => limit 1
    assert acquire_up_to("chatbooks", "1", 1) == 1

    # User 1 + other => user scope (3)
    assert acquire_up_to("other", "1", 3) == 3

    # User 2 + chatbooks => domain scope (2)
    assert acquire_up_to("chatbooks", "2", 2) == 2

    # User 2 + other => global (5)
    assert acquire_up_to("other", "2", 5) == 5


def test_submits_per_minute_precedence_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs_quota_spm_prec.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)

    monkeypatch.setenv("JOBS_QUOTA_SUBMITS_PER_MIN", "1")
    monkeypatch.setenv("JOBS_QUOTA_SUBMITS_PER_MIN_CHATBOOKS", "1")
    monkeypatch.setenv("JOBS_QUOTA_SUBMITS_PER_MIN_USER_1", "2")
    monkeypatch.setenv("JOBS_QUOTA_SUBMITS_PER_MIN_CHATBOOKS_USER_1", "3")

    # User 1 + chatbooks => 3/min
    for i in range(3):
        jm.create_job(domain="chatbooks", queue="default", job_type=f"a{i}", payload={}, owner_user_id="1")
    with pytest.raises(ValueError):
        jm.create_job(domain="chatbooks", queue="default", job_type="a4", payload={}, owner_user_id="1")

    # User 1 + other => 2/min (user scope)
    jm.create_job(domain="other", queue="default", job_type="b1", payload={}, owner_user_id="1")
    jm.create_job(domain="other", queue="default", job_type="b2", payload={}, owner_user_id="1")
    with pytest.raises(ValueError):
        jm.create_job(domain="other", queue="default", job_type="b3", payload={}, owner_user_id="1")

    # User 2 + chatbooks => 1/min (domain scope)
    jm.create_job(domain="chatbooks", queue="default", job_type="c1", payload={}, owner_user_id="2")
    with pytest.raises(ValueError):
        jm.create_job(domain="chatbooks", queue="default", job_type="c2", payload={}, owner_user_id="2")

    # User 2 + other => 1/min (global)
    jm.create_job(domain="other", queue="default", job_type="d1", payload={}, owner_user_id="2")
    with pytest.raises(ValueError):
        jm.create_job(domain="other", queue="default", job_type="d2", payload={}, owner_user_id="2")
