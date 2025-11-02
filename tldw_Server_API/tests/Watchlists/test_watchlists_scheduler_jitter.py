import os
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_watchlist_schedule_has_jitter(monkeypatch):
    # Isolate per-user DBs
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_sched"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    # Enable scheduler jitter explicitly
    monkeypatch.setenv("WATCHLISTS_SCHEDULER_JITTER_SEC", "60")

    from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler
    svc = get_workflows_scheduler()
    await svc.start()
    try:
        # Create a watchlist schedule directly
        sid = svc.create(
            tenant_id="default",
            user_id=str(555),
            workflow_id=None,
            name="wl-test",
            cron="*/15 * * * *",
            timezone="UTC",
            inputs={"watchlist_job_id": 1},
            run_mode="async",
            validation_mode="strict",
            enabled=True,
        )

        # Inspect stored schedule
        from tldw_Server_API.app.core.DB_Management.Workflows_Scheduler_DB import WorkflowsSchedulerDB
        db = WorkflowsSchedulerDB(user_id=555)
        items = db.list_schedules(tenant_id="default", user_id=str(555), limit=10, offset=0)
        assert any(s.id == sid for s in items)
        s = next(s for s in items if s.id == sid)
        assert s.jitter_sec and s.jitter_sec > 0
        assert s.next_run_at is None or isinstance(s.next_run_at, str)
    finally:
        await svc.stop()
