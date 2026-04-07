"""
Tests for fair-share scheduler integration with JobManager.

Verifies that:
- create_job enforces per-user concurrency limits via FairShareScheduler
- create_job adjusts priority using fair-share calculation
- Jobs are allowed when under the limit
- Jobs are blocked when at or over the limit
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tldw_Server_API.app.core.exceptions import BadRequestError
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables

pytestmark = pytest.mark.integration


@pytest.fixture
def job_manager(tmp_path, monkeypatch):
    """Create a JobManager backed by a temporary SQLite database."""
    monkeypatch.delenv("JOBS_DISABLE_LEASE_ENFORCEMENT", raising=False)
    db_path = tmp_path / "jobs_fs.db"
    ensure_jobs_tables(db_path)
    return JobManager(db_path)


class TestFairShareAdmissionControl:
    """Verify that create_job blocks users who exceed the concurrency limit."""

    def test_allows_job_under_limit(self, job_manager, monkeypatch):
        monkeypatch.setenv("JOBS_MAX_PER_USER", "3")
        # Reset the cached scheduler so it picks up new env
        import tldw_Server_API.app.core.Jobs.manager as mgr_mod
        mgr_mod._fair_share = None

        job = job_manager.create_job(
            domain="chatbooks",
            queue="default",
            job_type="export",
            payload={"test": True},
            owner_user_id="42",
        )
        assert job is not None
        assert job.get("status") in ("queued", None) or "uuid" in job

    def test_blocks_when_at_limit(self, job_manager, monkeypatch):
        monkeypatch.setenv("JOBS_MAX_PER_USER", "2")
        import tldw_Server_API.app.core.Jobs.manager as mgr_mod
        mgr_mod._fair_share = None

        # Create 2 jobs (at the limit)
        job_manager.create_job(
            domain="chatbooks", queue="default", job_type="export",
            payload={}, owner_user_id="42",
        )
        job_manager.create_job(
            domain="chatbooks", queue="default", job_type="export",
            payload={}, owner_user_id="42",
        )

        # Third job should be blocked
        with pytest.raises(BadRequestError, match="maximum concurrent job limit"):
            job_manager.create_job(
                domain="chatbooks", queue="default", job_type="export",
                payload={}, owner_user_id="42",
            )

    def test_different_users_independent(self, job_manager, monkeypatch):
        monkeypatch.setenv("JOBS_MAX_PER_USER", "1")
        import tldw_Server_API.app.core.Jobs.manager as mgr_mod
        mgr_mod._fair_share = None

        # User 1 creates a job
        job_manager.create_job(
            domain="chatbooks", queue="default", job_type="export",
            payload={}, owner_user_id="1",
        )

        # User 2 should still be allowed
        job2 = job_manager.create_job(
            domain="chatbooks", queue="default", job_type="export",
            payload={}, owner_user_id="2",
        )
        assert job2 is not None

    def test_no_owner_skips_fair_share(self, job_manager, monkeypatch):
        """Jobs without an owner_user_id bypass fair-share checks."""
        monkeypatch.setenv("JOBS_MAX_PER_USER", "1")
        import tldw_Server_API.app.core.Jobs.manager as mgr_mod
        mgr_mod._fair_share = None

        # Should not raise even though limit is 1
        job_manager.create_job(
            domain="chatbooks", queue="default", job_type="export",
            payload={}, owner_user_id=None,
        )

    def test_non_numeric_owner_user_id_does_not_require_int_cast(self, job_manager, monkeypatch):
        monkeypatch.setenv("JOBS_MAX_PER_USER", "3")
        import tldw_Server_API.app.core.Jobs.manager as mgr_mod
        mgr_mod._fair_share = None

        job = job_manager.create_job(
            domain="chatbooks",
            queue="default",
            job_type="export",
            payload={},
            owner_user_id="user-abc-123",
        )

        assert job is not None
        assert job.get("status") in ("queued", None) or "uuid" in job


class TestFairSharePriorityAdjustment:
    """Verify that priority is adjusted upward based on fair-share calculation."""

    def test_priority_boosted_for_low_active_count(self, job_manager, monkeypatch):
        monkeypatch.setenv("JOBS_MAX_PER_USER", "10")
        import tldw_Server_API.app.core.Jobs.manager as mgr_mod
        mgr_mod._fair_share = None

        job = job_manager.create_job(
            domain="chatbooks", queue="default", job_type="export",
            payload={}, owner_user_id="42", priority=5,
        )
        stored = job_manager.get_job(int(job["id"]))
        assert stored is not None
        assert int(stored["priority"]) < 5

    def test_warns_when_fair_share_check_is_skipped(self, job_manager, monkeypatch):
        monkeypatch.setenv("JOBS_MAX_PER_USER", "10")
        import tldw_Server_API.app.core.Jobs.manager as mgr_mod
        mgr_mod._fair_share = None

        with patch.object(JobManager, "_count_active_jobs_for_user", side_effect=RuntimeError("boom")), \
             patch.object(mgr_mod.logger, "warning") as mock_warning:
            job = job_manager.create_job(
                domain="chatbooks",
                queue="default",
                job_type="export",
                payload={},
                owner_user_id="42",
                priority=5,
            )

        assert job is not None
        mock_warning.assert_called_once()

    def test_completing_a_job_restores_capacity(self, job_manager, monkeypatch):
        monkeypatch.setenv("JOBS_MAX_PER_USER", "1")
        import tldw_Server_API.app.core.Jobs.manager as mgr_mod
        mgr_mod._fair_share = None

        job = job_manager.create_job(
            domain="chatbooks", queue="default", job_type="export",
            payload={}, owner_user_id="99",
        )
        acq = job_manager.acquire_next_job(
            domain="chatbooks", queue="default", lease_seconds=60, worker_id="w1",
        )
        if acq:
            job_manager.complete_job(
                int(acq["id"]),
                result={"ok": True},
                worker_id="w1",
                lease_id=str(acq.get("lease_id")),
            )

        next_job = job_manager.create_job(
            domain="chatbooks", queue="default", job_type="export",
            payload={}, owner_user_id="99",
        )

        assert job is not None
        assert next_job is not None


def test_cached_scheduler_refreshes_after_env_cleanup(tmp_path, monkeypatch):
    """A stale fair-share singleton should not survive env cleanup into later managers."""

    import tldw_Server_API.app.core.Jobs.manager as mgr_mod

    monkeypatch.delenv("JOBS_DISABLE_LEASE_ENFORCEMENT", raising=False)

    first_db = tmp_path / "jobs_fs_first.db"
    ensure_jobs_tables(first_db)
    monkeypatch.setenv("JOBS_MAX_PER_USER", "1")
    mgr_mod._fair_share = None

    first_manager = JobManager(first_db)
    first_manager.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="1",
    )
    with pytest.raises(BadRequestError, match="maximum concurrent job limit"):
        first_manager.create_job(
            domain="chatbooks",
            queue="default",
            job_type="export",
            payload={},
            owner_user_id="1",
        )

    monkeypatch.delenv("JOBS_MAX_PER_USER", raising=False)

    second_db = tmp_path / "jobs_fs_second.db"
    ensure_jobs_tables(second_db)
    second_manager = JobManager(second_db)
    second_manager.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="1",
    )
    second_job = second_manager.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="1",
    )

    assert second_job is not None
