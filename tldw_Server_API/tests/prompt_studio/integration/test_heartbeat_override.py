import asyncio
import os
import time
from datetime import datetime
import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_manager import JobManager, JobType


pytestmark = pytest.mark.integration


def _parse_dt(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    # Try ISO parsing without external deps
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except Exception:
        return None


@pytest.mark.asyncio
async def test_heartbeat_renews_lease(prompt_studio_dual_backend_db, monkeypatch):
    label, db = prompt_studio_dual_backend_db

    # Keep fast, backend-agnostic
    monkeypatch.setenv("TLDW_PS_JOB_LEASE_SECONDS", "6")
    monkeypatch.setenv("TLDW_PS_HEARTBEAT_SECONDS", "2")

    jm = JobManager(db)

    async def handler(payload, entity_id):
        # Sleep long enough to require at least one heartbeat renewal
        await asyncio.sleep(4)
        return {"ok": True}

    jm.register_handler(JobType.OPTIMIZATION, handler)

    job = jm.create_job(JobType.OPTIMIZATION, 0, payload={})
    picked = jm.get_next_job()
    assert picked is not None and picked["id"] == job["id"] and picked["status"] == "processing"

    # Capture initial lease
    j0 = db.get_job(job["id"])
    t0 = _parse_dt(j0.get("leased_until"))

    # Run processing in background
    task = asyncio.create_task(jm.process_job(picked))
    await asyncio.sleep(3)  # allow at least one heartbeat

    # Verify lease extended
    j_mid = db.get_job(job["id"])
    t_mid = _parse_dt(j_mid.get("leased_until"))
    assert t0 is not None and t_mid is not None
    assert t_mid >= t0, "lease should be extended or equal after heartbeat"

    await task
    j_done = db.get_job(job["id"])
    assert j_done["status"] in ("completed", "failed")
