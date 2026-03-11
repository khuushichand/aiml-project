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
def companion_notifications_app(monkeypatch, tmp_path):
    base_dir = tmp_path / "test_companion_reflection_notifications"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    app = FastAPI()
    app.include_router(notifications_router, prefix="/api/v1")

    async def override_user():
        return User(id=882, username="companion-notifications", email=None, is_active=True)

    async def override_principal():
        return AuthPrincipal(
            kind="user",
            user_id=882,
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


def test_notifications_list_returns_companion_reflection_rows(companion_notifications_app) -> None:
    cdb = CollectionsDatabase.for_user(user_id=882)
    row = cdb.create_user_notification(
        kind="companion_reflection",
        title="Daily reflection",
        message="You have been focusing on project-alpha.",
        severity="info",
        source_job_id="601",
        source_domain="companion",
        source_job_type="companion_reflection",
        link_type="companion_reflection",
        link_id="reflection-1",
        dedupe_key="companion_reflection:reflection-1",
    )

    with TestClient(companion_notifications_app) as client:
        response = client.get("/api/v1/notifications")

    assert response.status_code == 200, response.text
    payload = response.json()
    item = next(item for item in payload["items"] if item["id"] == row.id)
    assert item["kind"] == "companion_reflection"
    assert item["link_type"] == "companion_reflection"
    assert item["link_id"] == "reflection-1"
    assert item["source_job_id"] == "601"
