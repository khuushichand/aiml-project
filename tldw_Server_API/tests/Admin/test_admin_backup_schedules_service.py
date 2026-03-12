from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException


@dataclass
class _RecordingRepo:
    created_payload: dict | None = None

    async def create_schedule(self, **kwargs):
        self.created_payload = dict(kwargs)
        return {
            "id": "sched-1",
            "dataset": kwargs["dataset"],
            "target_user_id": kwargs["target_user_id"],
            "frequency": kwargs["frequency"],
            "time_of_day": kwargs["time_of_day"],
            "timezone": kwargs["timezone"],
            "anchor_day_of_week": kwargs["anchor_day_of_week"],
            "anchor_day_of_month": kwargs["anchor_day_of_month"],
            "retention_count": kwargs["retention_count"],
            "is_paused": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "next_run_at": kwargs.get("next_run_at"),
            "last_run_at": None,
            "last_status": None,
            "last_job_id": None,
            "last_error": None,
            "deleted_at": None,
        }


@dataclass
class _DuplicateRepo:
    async def create_schedule(self, **kwargs):
        raise RuntimeError("UNIQUE constraint failed: backup_schedules.target_scope_key")


def test_monthly_schedule_falls_back_to_last_day() -> None:
    from tldw_Server_API.app.services.admin_backup_schedules_service import (
        AdminBackupSchedulesService,
    )

    service = AdminBackupSchedulesService(repo=None)
    assert service.resolve_monthly_run_day(anchor_day_of_month=31, year=2026, month=2) == 28
    assert service.resolve_monthly_run_day(anchor_day_of_month=31, year=2024, month=2) == 29


def test_describe_schedule_uses_anchor_details() -> None:
    from tldw_Server_API.app.services.admin_backup_schedules_service import (
        AdminBackupSchedulesService,
    )

    service = AdminBackupSchedulesService(repo=None)
    description = service.describe_schedule(
        {
            "frequency": "weekly",
            "time_of_day": "02:00",
            "timezone": "UTC",
            "anchor_day_of_week": 1,
            "anchor_day_of_month": None,
        }
    )
    assert description == "Weekly on Tuesday at 02:00 UTC"


def test_compute_next_run_at_for_weekly_schedule_uses_anchor_and_time() -> None:
    from tldw_Server_API.app.services.admin_backup_schedules_service import (
        AdminBackupSchedulesService,
    )

    service = AdminBackupSchedulesService(repo=None)
    next_run = service.compute_next_run_at(
        {
            "frequency": "weekly",
            "time_of_day": "02:00",
            "timezone": "UTC",
            "anchor_day_of_week": 1,
            "anchor_day_of_month": None,
        },
        from_time=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
    )
    assert next_run == "2026-03-17T02:00:00+00:00"


def test_compute_next_run_at_for_monthly_schedule_uses_last_day_fallback() -> None:
    from tldw_Server_API.app.services.admin_backup_schedules_service import (
        AdminBackupSchedulesService,
    )

    service = AdminBackupSchedulesService(repo=None)
    next_run = service.compute_next_run_at(
        {
            "frequency": "monthly",
            "time_of_day": "02:00",
            "timezone": "UTC",
            "anchor_day_of_week": None,
            "anchor_day_of_month": 31,
        },
        from_time=datetime(2026, 1, 31, 15, 0, tzinfo=timezone.utc),
    )
    assert next_run == "2026-02-28T02:00:00+00:00"


@pytest.mark.asyncio
async def test_create_schedule_derives_weekly_anchor_from_reference_time() -> None:
    from tldw_Server_API.app.services.admin_backup_schedules_service import (
        AdminBackupSchedulesService,
    )

    repo = _RecordingRepo()
    service = AdminBackupSchedulesService(repo=repo)
    await service.create_schedule(
        dataset="authnz",
        target_user_id=None,
        frequency="weekly",
        time_of_day="02:00",
        timezone_name=None,
        retention_count=30,
        principal_user_id=1,
        now=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
    )
    assert repo.created_payload is not None
    assert repo.created_payload["anchor_day_of_week"] == 1
    assert repo.created_payload["anchor_day_of_month"] is None


@pytest.mark.asyncio
async def test_create_schedule_derives_monthly_anchor_from_reference_time() -> None:
    from tldw_Server_API.app.services.admin_backup_schedules_service import (
        AdminBackupSchedulesService,
    )

    repo = _RecordingRepo()
    service = AdminBackupSchedulesService(repo=repo)
    await service.create_schedule(
        dataset="authnz",
        target_user_id=None,
        frequency="monthly",
        time_of_day="02:00",
        timezone_name=None,
        retention_count=30,
        principal_user_id=1,
        now=datetime(2026, 1, 31, 15, 0, tzinfo=timezone.utc),
    )
    assert repo.created_payload is not None
    assert repo.created_payload["anchor_day_of_week"] is None
    assert repo.created_payload["anchor_day_of_month"] == 31


@pytest.mark.asyncio
async def test_create_schedule_rejects_duplicate_active_target() -> None:
    from tldw_Server_API.app.services.admin_backup_schedules_service import (
        AdminBackupSchedulesService,
    )

    service = AdminBackupSchedulesService(repo=_DuplicateRepo())
    with pytest.raises(HTTPException) as exc_info:
        await service.create_schedule(
            dataset="media",
            target_user_id=7,
            frequency="daily",
            time_of_day="02:00",
            timezone_name="UTC",
            retention_count=14,
            principal_user_id=1,
            now=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "duplicate_active_schedule"
