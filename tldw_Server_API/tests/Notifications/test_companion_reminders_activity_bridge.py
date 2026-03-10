from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.permissions import TASKS_CONTROL, TASKS_READ
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.tests.Notifications.test_reminders_api import reminders_app


pytestmark = pytest.mark.unit


def test_reminder_task_creation_records_companion_event(reminders_app):
    personalization_db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(880)))
    personalization_db.update_profile("880", enabled=1)

    app = reminders_app

    async def override_user():
        return User(id=880, username="reminder-user", email=None, is_active=True)

    async def override_principal():
        return AuthPrincipal(
            kind="user",
            user_id=880,
            roles=[],
            permissions=[TASKS_READ, TASKS_CONTROL],
            is_admin=False,
        )

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[get_auth_principal] = override_principal

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tasks",
            json={
                "title": "Review companion roadmap",
                "body": "Check explicit capture plan",
                "schedule_kind": "one_time",
                "run_at": "2026-03-01T10:00:00+00:00",
                "enabled": True,
            },
        )

    assert response.status_code == 201, response.text
    payload = response.json()

    events, total = personalization_db.list_companion_activity_events("880", limit=10)
    assert total == 1
    event = events[0]
    assert event["event_type"] == "reminder_task_created"
    assert event["source_type"] == "reminder_task"
    assert event["source_id"] == payload["id"]
    assert event["surface"] == "api.tasks"
    assert event["provenance"]["route"] == "/api/v1/tasks"
    assert event["metadata"]["title"] == "Review companion roadmap"


def test_reminder_task_update_and_delete_record_companion_events(reminders_app):
    personalization_db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(880)))
    personalization_db.update_profile("880", enabled=1)

    app = reminders_app

    async def override_user():
        return User(id=880, username="reminder-user", email=None, is_active=True)

    async def override_principal():
        return AuthPrincipal(
            kind="user",
            user_id=880,
            roles=[],
            permissions=[TASKS_READ, TASKS_CONTROL],
            is_admin=False,
        )

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[get_auth_principal] = override_principal

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/tasks",
            json={
                "title": "Follow up on reminders",
                "body": "Make sure update and delete are captured.",
                "schedule_kind": "one_time",
                "run_at": "2026-03-10T19:00:00+00:00",
                "enabled": True,
                "link_type": "note",
                "link_id": "note-9",
            },
        )
        assert create_response.status_code == 201, create_response.text
        task_id = create_response.json()["id"]

        patch_response = client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"enabled": False, "title": "Follow up on reminder lifecycle"},
        )
        assert patch_response.status_code == 200, patch_response.text
        patched = patch_response.json()

        delete_response = client.delete(f"/api/v1/tasks/{task_id}")
        assert delete_response.status_code == 200, delete_response.text
        assert delete_response.json()["deleted"] is True

    events, total = personalization_db.list_companion_activity_events("880", limit=10)
    assert total == 3

    event_types = [event["event_type"] for event in events]
    assert event_types == [
        "reminder_task_deleted",
        "reminder_task_updated",
        "reminder_task_created",
    ]

    deleted_event = events[0]
    assert deleted_event["source_id"] == task_id
    assert deleted_event["provenance"]["route"] == f"/api/v1/tasks/{task_id}"
    assert deleted_event["metadata"]["title"] == "Follow up on reminder lifecycle"
    assert deleted_event["metadata"]["hard_delete"] is True

    updated_event = events[1]
    assert updated_event["source_id"] == task_id
    assert updated_event["metadata"]["title"] == patched["title"]
    assert updated_event["metadata"]["enabled"] is False
    assert updated_event["metadata"]["changed_fields"] == ["enabled", "title"]
