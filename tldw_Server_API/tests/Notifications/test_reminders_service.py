from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.Reminders.reminders_service import RemindersService
from tldw_Server_API.app.core.config import settings


@pytest.fixture()
def reminders_service(monkeypatch, tmp_path):
    base_dir = tmp_path / "test_reminders_service"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    try:
        yield RemindersService(user_id=777)
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def _seed_notification(user_id: int = 777) -> int:
    cdb = CollectionsDatabase.for_user(user_id=user_id)
    row = cdb.create_user_notification(
        kind="reminder_due",
        title="Review docs",
        message="Re-check design assumptions",
        severity="info",
        link_type="item",
        link_id="item-12",
    )
    return row.id


def test_snooze_notification_creates_one_time_task(reminders_service):
    notification_id = _seed_notification()

    task = reminders_service.snooze_notification(notification_id=notification_id, minutes=30)

    assert task.schedule_kind == "one_time"
    assert task.timezone == "UTC"
    assert task.link_type == "item"
    assert task.link_id == "item-12"
    assert task.title.startswith("Snoozed:")
    assert task.run_at is not None
    run_at = datetime.fromisoformat(task.run_at)
    delta_seconds = (run_at - datetime.now(timezone.utc)).total_seconds()
    assert 20 * 60 <= delta_seconds <= 40 * 60


@pytest.mark.parametrize("minutes", [0, 10081])
def test_snooze_notification_rejects_invalid_minutes(reminders_service, minutes: int):
    notification_id = _seed_notification()
    with pytest.raises(ValueError):
        reminders_service.snooze_notification(notification_id=notification_id, minutes=minutes)


def test_snooze_notification_raises_for_missing_notification(reminders_service):
    with pytest.raises(KeyError):
        reminders_service.snooze_notification(notification_id=999999, minutes=10)
