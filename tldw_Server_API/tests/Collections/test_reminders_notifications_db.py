from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase


pytestmark = pytest.mark.unit


@pytest.fixture()
def collections_db(monkeypatch: pytest.MonkeyPatch) -> CollectionsDatabase:
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_reminders_notifications"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    try:
        yield CollectionsDatabase.for_user(user_id=778)
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_create_and_list_reminder_task(collections_db: CollectionsDatabase) -> None:
    task_id = collections_db.create_reminder_task(
        title="Ping",
        body="Re-check this thread",
        schedule_kind="one_time",
        run_at="2026-03-01T10:00:00+00:00",
        cron=None,
        timezone=None,
        enabled=True,
    )

    rows = collections_db.list_reminder_tasks()
    assert any(row.id == task_id for row in rows)
