from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.endpoints.notifications import router as notifications_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.permissions import (
    NOTIFICATIONS_CONTROL,
    NOTIFICATIONS_READ,
    TASKS_CONTROL,
    TASKS_READ,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


@pytest.fixture()
def notifications_app(monkeypatch, tmp_path):
    base_dir = tmp_path / "test_notifications_api"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    app = FastAPI()
    app.include_router(notifications_router, prefix="/api/v1")

    async def override_user():
        return User(id=881, username="notifications-user", email=None, is_active=True)

    async def override_principal():
        return AuthPrincipal(
            kind="user",
            user_id=881,
            roles=[],
            permissions=[TASKS_READ, TASKS_CONTROL, NOTIFICATIONS_READ, NOTIFICATIONS_CONTROL],
            is_admin=False,
        )

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[get_auth_principal] = override_principal
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_notifications_unread_mark_read_dismiss_and_preferences(notifications_app):
    cdb = CollectionsDatabase.for_user(user_id=881)
    n1 = cdb.create_user_notification(
        kind="reminder_due",
        title="Reminder Due",
        message="Investigate issue",
        severity="info",
    )
    n2 = cdb.create_user_notification(
        kind="job_completed",
        title="Job Completed",
        message="Daily digest finished",
        severity="info",
    )

    with TestClient(notifications_app) as client:
        r = client.get("/api/v1/notifications/unread-count")
        assert r.status_code == 200, r.text
        assert r.json()["unread_count"] == 2

        r = client.get("/api/v1/notifications")
        assert r.status_code == 200, r.text
        ids = {item["id"] for item in r.json()["items"]}
        assert n1.id in ids and n2.id in ids

        r = client.post("/api/v1/notifications/mark-read", json={"ids": [n1.id]})
        assert r.status_code == 200, r.text
        assert r.json()["updated"] == 1

        r = client.post(f"/api/v1/notifications/{n2.id}/dismiss")
        assert r.status_code == 200, r.text
        assert r.json()["dismissed"] is True

        r = client.get("/api/v1/notifications/unread-count")
        assert r.status_code == 200, r.text
        assert r.json()["unread_count"] == 0

        r = client.get("/api/v1/notifications/preferences")
        assert r.status_code == 200, r.text
        assert r.json()["reminder_enabled"] is True

        r = client.patch(
            "/api/v1/notifications/preferences",
            json={"reminder_enabled": False, "job_failed_enabled": False},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["reminder_enabled"] is False
        assert body["job_failed_enabled"] is False


def test_notifications_unread_requires_read_scope(notifications_app):
    async def restricted_principal():
        return AuthPrincipal(
            kind="user",
            user_id=881,
            roles=[],
            permissions=[],
            is_admin=False,
        )

    notifications_app.dependency_overrides[get_auth_principal] = restricted_principal
    with TestClient(notifications_app) as client:
        r = client.get("/api/v1/notifications/unread-count")
        assert r.status_code == 403
