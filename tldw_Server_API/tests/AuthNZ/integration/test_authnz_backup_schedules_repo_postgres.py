from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.backup_schedules_repo import (
    AuthnzBackupSchedulesRepo,
)


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authnz_backup_schedules_repo_postgres_roundtrip(test_db_pool) -> None:
    repo = AuthnzBackupSchedulesRepo(test_db_pool)
    await repo.ensure_schema()

    created = await repo.create_schedule(
        dataset="authnz",
        target_user_id=None,
        frequency="monthly",
        time_of_day="02:00",
        timezone="UTC",
        anchor_day_of_week=None,
        anchor_day_of_month=31,
        retention_count=12,
        created_by_user_id=None,
        updated_by_user_id=None,
        next_run_at="2026-03-31T02:00:00+00:00",
    )

    assert created["dataset"] == "authnz"
    assert created["anchor_day_of_month"] == 31

    claimed = await repo.claim_run_slot(
        schedule_id=str(created["id"]),
        scheduled_for="2026-03-31T02:00:00+00:00",
        run_slot_key=f"{created['id']}:2026-03-31T02:00:00+00:00",
        enqueued_at=datetime.now(timezone.utc).isoformat(),
    )
    assert claimed is not None

    duplicate = await repo.claim_run_slot(
        schedule_id=str(created["id"]),
        scheduled_for="2026-03-31T02:00:00+00:00",
        run_slot_key=f"{created['id']}:2026-03-31T02:00:00+00:00",
        enqueued_at=datetime.now(timezone.utc).isoformat(),
    )
    assert duplicate is None

    listed, total = await repo.list_schedules(limit=20, offset=0)
    assert total >= 1
    assert any(str(item["id"]) == str(created["id"]) for item in listed)
