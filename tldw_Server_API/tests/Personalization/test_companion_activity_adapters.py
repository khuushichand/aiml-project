from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Personalization.companion_activity import (
    record_companion_activity,
    record_note_created,
    record_note_deleted,
    record_note_restored,
    record_note_updated,
    record_reminder_task_deleted,
    record_reminder_task_updated,
)
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


@pytest.fixture()
def companion_db_env(monkeypatch, tmp_path):
    base_dir = tmp_path / "user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")
    try:
        yield Path(base_dir)
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_record_companion_activity_requires_opt_in_and_dedupes(companion_db_env):
    user_id = "77"
    db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))

    skipped = record_companion_activity(
        user_id=user_id,
        event_type="reading_item_saved",
        source_type="reading_item",
        source_id="123",
        surface="api.reading",
        dedupe_key="reading.save:123",
        tags=["ai"],
        provenance={"capture_mode": "explicit", "route": "/api/v1/reading/save"},
        metadata={"title": "Example"},
    )
    assert skipped is None
    _, skipped_total = db.list_companion_activity_events(user_id)
    assert skipped_total == 0

    db.update_profile(user_id, enabled=1)
    created = record_companion_activity(
        user_id=user_id,
        event_type="reading_item_saved",
        source_type="reading_item",
        source_id="123",
        surface="api.reading",
        dedupe_key="reading.save:123",
        tags=["ai"],
        provenance={"capture_mode": "explicit", "route": "/api/v1/reading/save"},
        metadata={"title": "Example"},
    )
    assert created

    items, total = db.list_companion_activity_events(user_id)
    assert total == 1
    assert items[0]["event_type"] == "reading_item_saved"
    assert items[0]["provenance"]["capture_mode"] == "explicit"

    duplicate = record_companion_activity(
        user_id=user_id,
        event_type="reading_item_saved",
        source_type="reading_item",
        source_id="123",
        surface="api.reading",
        dedupe_key="reading.save:123",
        tags=["ai"],
        provenance={"capture_mode": "explicit", "route": "/api/v1/reading/save"},
        metadata={"title": "Example"},
    )
    assert duplicate is None
    _, total_after_duplicate = db.list_companion_activity_events(user_id)
    assert total_after_duplicate == 1


def test_note_activity_adapters_capture_compact_metadata(companion_db_env):
    user_id = "78"
    db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))
    db.update_profile(user_id, enabled=1)

    note = {
        "id": "note-1",
        "title": "Focus Note",
        "content": "This is a note body that should be compactly represented in the companion activity ledger.",
        "created_at": "2026-03-09T10:00:00Z",
        "last_modified": "2026-03-09T10:05:00Z",
        "version": 2,
        "conversation_id": "conv-1",
        "message_id": "msg-1",
        "keywords": [{"keyword": "research"}, {"keyword": "planning"}],
    }

    created = record_note_created(user_id=user_id, note=note)
    updated = record_note_updated(
        user_id=user_id,
        note=note,
        route="/api/v1/notes/note-1",
        action="patch",
        patch={"title": "Focus Note", "content": "Updated body"},
    )

    assert created
    assert updated

    events, total = db.list_companion_activity_events(user_id, limit=10)
    assert total == 2

    updated_event = events[0]
    assert updated_event["event_type"] == "note_updated"
    assert updated_event["tags"] == ["research", "planning"]
    assert updated_event["metadata"]["version"] == 2
    assert updated_event["metadata"]["changed_fields"] == ["content", "title"]
    assert "Updated body" not in str(updated_event["metadata"])
    assert updated_event["provenance"]["action"] == "patch"

    created_event = events[1]
    assert created_event["event_type"] == "note_created"
    assert created_event["provenance"]["route"] == "/api/v1/notes/"
    assert created_event["metadata"]["content_preview"].startswith("This is a note body")


def test_note_delete_and_restore_adapters_capture_state_changes(companion_db_env):
    user_id = "79"
    db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))
    db.update_profile(user_id, enabled=1)

    deleted_note = {
        "id": "note-2",
        "title": "Archive Me",
        "content": "A note that is about to be removed from the active list.",
        "created_at": "2026-03-09T11:00:00Z",
        "last_modified": "2026-03-09T11:05:00Z",
        "version": 2,
        "keywords": [{"keyword": "cleanup"}],
    }
    restored_note = {
        **deleted_note,
        "last_modified": "2026-03-09T11:10:00Z",
        "version": 4,
    }

    deleted = record_note_deleted(user_id=user_id, note=deleted_note, deleted_version=3)
    restored = record_note_restored(user_id=user_id, note=restored_note)

    assert deleted
    assert restored

    events, total = db.list_companion_activity_events(user_id, limit=10)
    assert total == 2

    restored_event = events[0]
    assert restored_event["event_type"] == "note_restored"
    assert restored_event["metadata"]["version"] == 4
    assert restored_event["metadata"]["deleted"] is False
    assert restored_event["provenance"]["action"] == "restore"

    deleted_event = events[1]
    assert deleted_event["event_type"] == "note_deleted"
    assert deleted_event["tags"] == ["cleanup"]
    assert deleted_event["metadata"]["version"] == 3
    assert deleted_event["metadata"]["deleted"] is True
    assert deleted_event["metadata"]["hard_delete"] is False
    assert deleted_event["metadata"]["content_preview"].startswith("A note that is about to be removed")
    assert "content" not in deleted_event["metadata"]


def test_reminder_task_update_and_delete_adapters_capture_compact_metadata(companion_db_env):
    user_id = "80"
    db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))
    db.update_profile(user_id, enabled=1)

    updated_task = {
        "id": "task-1",
        "title": "Review companion signals",
        "body": "Check the explicit activity backlog before the next reflection run.",
        "schedule_kind": "one_time",
        "run_at": "2026-03-10T18:00:00Z",
        "cron": None,
        "timezone": None,
        "enabled": False,
        "link_type": "note",
        "link_id": "note-22",
        "link_url": None,
        "created_at": "2026-03-10T09:00:00Z",
        "updated_at": "2026-03-10T09:30:00Z",
    }

    updated = record_reminder_task_updated(
        user_id=user_id,
        task=updated_task,
        patch={"enabled": False, "title": "Review companion signals"},
    )
    deleted = record_reminder_task_deleted(user_id=user_id, task=updated_task)

    assert updated
    assert deleted

    events, total = db.list_companion_activity_events(user_id, limit=10)
    assert total == 2

    deleted_event = events[0]
    assert deleted_event["event_type"] == "reminder_task_deleted"
    assert deleted_event["source_type"] == "reminder_task"
    assert deleted_event["surface"] == "api.tasks"
    assert deleted_event["provenance"]["action"] == "delete"
    assert deleted_event["metadata"]["title"] == "Review companion signals"
    assert deleted_event["metadata"]["hard_delete"] is True
    assert deleted_event["metadata"]["enabled"] is False
    assert deleted_event["metadata"]["body_preview"].startswith("Check the explicit activity backlog")
    assert "body" not in deleted_event["metadata"]

    updated_event = events[1]
    assert updated_event["event_type"] == "reminder_task_updated"
    assert updated_event["provenance"]["route"] == "/api/v1/tasks/task-1"
    assert updated_event["metadata"]["changed_fields"] == ["enabled", "title"]
    assert updated_event["metadata"]["schedule_kind"] == "one_time"
    assert updated_event["metadata"]["link_type"] == "note"
