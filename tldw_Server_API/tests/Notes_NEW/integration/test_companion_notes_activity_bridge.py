from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.endpoints import notes as notes_ep
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit

TEST_USER_ID = 333

fastapi_app = FastAPI()
fastapi_app.include_router(notes_ep.router, prefix="/api/v1/notes")


@pytest.fixture()
def notes_client_with_companion_opt_in(monkeypatch, tmp_path):
    base_dir = tmp_path / "user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")

    notes_db = CharactersRAGDB(str(tmp_path / "notes.db"), client_id="companion-notes-tests")
    personalization_db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(TEST_USER_ID)))
    personalization_db.update_profile(str(TEST_USER_ID), enabled=1)

    async def override_user():
        return User(id=TEST_USER_ID, username="notes-user", email=None, is_active=True, is_admin=True)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = lambda: notes_db
    try:
        with TestClient(fastapi_app) as client:
            yield client, personalization_db
    finally:
        fastapi_app.dependency_overrides.clear()
        if hasattr(notes_db, "close_connection"):
            notes_db.close_connection()
        elif hasattr(notes_db, "close"):
            notes_db.close()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_note_create_and_patch_record_companion_activity(notes_client_with_companion_opt_in):
    client, personalization_db = notes_client_with_companion_opt_in

    create_resp = client.post(
        "/api/v1/notes/",
        json={
            "title": "Companion Note",
            "content": "Original note body for explicit capture.",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    note_id = created["id"]

    patch_resp = client.patch(
        f"/api/v1/notes/{note_id}",
        json={
            "title": "Companion Note Updated",
            "content": "Updated note body for explicit capture.",
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    updated = patch_resp.json()

    events, total = personalization_db.list_companion_activity_events(str(TEST_USER_ID), limit=10)
    assert total == 2

    event_types = [event["event_type"] for event in events]
    assert event_types == ["note_updated", "note_created"]

    created_event = events[1]
    assert created_event["source_type"] == "note"
    assert created_event["source_id"] == note_id
    assert created_event["surface"] == "api.notes"
    assert created_event["provenance"]["capture_mode"] == "explicit"
    assert created_event["provenance"]["route"] == "/api/v1/notes/"
    assert created_event["metadata"]["title"] == "Companion Note"

    updated_event = events[0]
    assert updated_event["source_type"] == "note"
    assert updated_event["source_id"] == note_id
    assert updated_event["surface"] == "api.notes"
    assert updated_event["provenance"]["capture_mode"] == "explicit"
    assert updated_event["provenance"]["route"] == f"/api/v1/notes/{note_id}"
    assert updated_event["metadata"]["title"] == "Companion Note Updated"
    assert updated_event["metadata"]["version"] == updated["version"]


def test_note_delete_and_restore_record_companion_activity(notes_client_with_companion_opt_in):
    client, personalization_db = notes_client_with_companion_opt_in

    create_resp = client.post(
        "/api/v1/notes/",
        json={
            "title": "Recoverable Note",
            "content": "This note will be deleted and restored.",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    note_id = created["id"]

    delete_resp = client.delete(
        f"/api/v1/notes/{note_id}",
        headers={"expected-version": str(created["version"])},
    )
    assert delete_resp.status_code == 204, delete_resp.text

    trash_resp = client.get("/api/v1/notes/trash")
    assert trash_resp.status_code == 200, trash_resp.text
    trash_notes = trash_resp.json()["notes"]
    deleted_note = next(note for note in trash_notes if note["id"] == note_id)

    restore_resp = client.post(
        f"/api/v1/notes/{note_id}/restore",
        params={"expected_version": deleted_note["version"]},
    )
    assert restore_resp.status_code == 200, restore_resp.text
    restored = restore_resp.json()

    events, total = personalization_db.list_companion_activity_events(str(TEST_USER_ID), limit=10)
    assert total == 3

    event_types = [event["event_type"] for event in events]
    assert event_types == ["note_restored", "note_deleted", "note_created"]

    deleted_event = events[1]
    assert deleted_event["source_type"] == "note"
    assert deleted_event["source_id"] == note_id
    assert deleted_event["surface"] == "api.notes"
    assert deleted_event["provenance"]["route"] == f"/api/v1/notes/{note_id}"
    assert deleted_event["metadata"]["title"] == "Recoverable Note"
    assert deleted_event["metadata"]["version"] == deleted_note["version"]
    assert deleted_event["metadata"]["deleted"] is True

    restored_event = events[0]
    assert restored_event["source_type"] == "note"
    assert restored_event["source_id"] == note_id
    assert restored_event["surface"] == "api.notes"
    assert restored_event["provenance"]["route"] == f"/api/v1/notes/{note_id}/restore"
    assert restored_event["metadata"]["title"] == "Recoverable Note"
    assert restored_event["metadata"]["version"] == restored["version"]
    assert restored_event["metadata"]["deleted"] is False
