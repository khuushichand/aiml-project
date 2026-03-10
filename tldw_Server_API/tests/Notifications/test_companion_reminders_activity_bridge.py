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
