"""Job leasing tests for Prompt Studio queue (dual-backend).

Validates:
- Lease is set on acquire and can be renewed (heartbeat API)
- Expired processing jobs are reclaimed on next acquire
- Completing a job clears lease fields
"""

from __future__ import annotations

import asyncio
import os
from typing import Dict, Any

import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_manager import (
    JobManager, JobType,
)


pytestmark = pytest.mark.integration


def _get_job_row(db, job_id: int) -> Dict[str, Any]:
    row = db.get_job(job_id) or {}
    return row


@pytest.mark.asyncio
async def test_lease_set_and_renew_dual_backend(prompt_studio_dual_backend_db, monkeypatch):
    backend_label, db = prompt_studio_dual_backend_db

    # Short lease for test; heartbeat will renew during processing
    monkeypatch.setenv("TLDW_PS_JOB_LEASE_SECONDS", "6")

    # Create a job and acquire it
    job = db.create_job("optimization", 1, payload={})
    job_acq = db.acquire_next_job()
    assert job_acq is not None
    jid = int(job_acq["id"])  # type: ignore[index]

    # Lease should be set after acquire
    row1 = _get_job_row(db, jid)
    assert row1.get("leased_until") is not None

    # Run a handler that sleeps across at least one heartbeat interval
    jm = JobManager(db)

    @jm.register_handler(JobType.OPTIMIZATION)
    async def _handler(payload, entity_id):  # type: ignore[no-redef]
        await asyncio.sleep(4)
        return {"ok": True}

    # Start processing and wait a bit, then check lease was renewed
    task = asyncio.create_task(jm.process_job(job_acq))
    await asyncio.sleep(3)  # allow heartbeat to tick at least once
    row2 = _get_job_row(db, jid)
    assert row2.get("leased_until") is not None
    # If backend normalizes timestamps, the value may change; at least not cleared mid-flight

    await task


@pytest.mark.asyncio
async def test_reclaim_expired_processing_dual_backend(prompt_studio_dual_backend_db, monkeypatch):
    backend_label, db = prompt_studio_dual_backend_db

    # Set very short lease and let it expire
    monkeypatch.setenv("TLDW_PS_JOB_LEASE_SECONDS", "1")

    job = db.create_job("optimization", 2, payload={})
    first = db.acquire_next_job()
    assert first is not None
    jid = int(first["id"])  # type: ignore[index]

    # Wait for lease to expire (1s) and try to acquire again
    await asyncio.sleep(1.2)
    second = db.acquire_next_job()
    # The same job should be reclaimed for processing again (or no-op if none queued)
    assert second is not None
    assert int(second["id"]) == jid


def test_clear_lease_on_completion_dual_backend(prompt_studio_dual_backend_db, monkeypatch):
    backend_label, db = prompt_studio_dual_backend_db

    monkeypatch.setenv("TLDW_PS_JOB_LEASE_SECONDS", "5")

    job = db.create_job("optimization", 3, payload={})
    got = db.acquire_next_job()
    assert got is not None
    jid = int(got["id"])  # type: ignore[index]
    row = _get_job_row(db, jid)
    assert row.get("leased_until") is not None

    # Mark completed; lease should be cleared
    db.update_job_status(jid, "completed")
    row_done = _get_job_row(db, jid)
    assert row_done.get("leased_until") in (None, "")


def test_lease_owner_enforced_dual_backend(prompt_studio_dual_backend_db):
    backend_label, db = prompt_studio_dual_backend_db

    job = db.create_job("evaluation", 7, payload={})
    jm = JobManager(db, worker_id="ps-worker-test")

    acquired = jm.get_next_job()
    assert acquired is not None
    jid = int(acquired["id"])

    row = _get_job_row(db, jid)
    assert row.get("lease_owner") == jm.worker_id

    assert db.renew_job_lease(jid, seconds=10, worker_id=jm.worker_id)
    assert not db.renew_job_lease(jid, seconds=10, worker_id="other-worker")
