from __future__ import annotations

import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.reminders_schemas import ReminderTaskCreateRequest


def test_reminder_task_create_requires_run_at_for_one_time() -> None:
    with pytest.raises(ValidationError):
        ReminderTaskCreateRequest(
            title="Follow up",
            schedule_kind="one_time",
        )


def test_reminder_task_create_requires_cron_and_timezone_for_recurring() -> None:
    with pytest.raises(ValidationError):
        ReminderTaskCreateRequest(
            title="Daily check-in",
            schedule_kind="recurring",
        )


def test_reminder_task_create_accepts_valid_one_time_payload() -> None:
    task = ReminderTaskCreateRequest(
        title="Review item",
        schedule_kind="one_time",
        run_at="2026-03-01T10:00:00+00:00",
    )

    assert task.schedule_kind == "one_time"
    assert task.run_at == "2026-03-01T10:00:00+00:00"
