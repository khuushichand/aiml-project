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

        r = client.get("/api/v1/notifications")
        assert r.status_code == 200, r.text
        listed_ids = {item["id"] for item in r.json()["items"]}
        assert n2.id not in listed_ids
        assert n1.id in listed_ids

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


def test_notification_snooze_reconciles_scheduler(notifications_app, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import notifications as notifications_endpoint

    cdb = CollectionsDatabase.for_user(user_id=881)
    source = cdb.create_user_notification(
        kind="reminder_due",
        title="Snooze me",
        message="Re-check this later",
        severity="info",
    )

    reconcile_calls: list[tuple[str, int]] = []

    class _FakeScheduler:
        async def reconcile_task(self, *, task_id: str, user_id: int) -> None:
            reconcile_calls.append((task_id, user_id))

    monkeypatch.setattr(notifications_endpoint, "get_reminders_scheduler", lambda: _FakeScheduler(), raising=False)

    with TestClient(notifications_app) as client:
        response = client.post(f"/api/v1/notifications/{source.id}/snooze", json={"minutes": 15})
        assert response.status_code == 200, response.text
        payload = response.json()

    task_id = payload["task_id"]
    task = cdb.get_reminder_task(task_id)
    assert task.schedule_kind == "one_time"
    assert task.link_id == source.link_id
    assert task.run_at is not None
    assert reconcile_calls == [(task_id, 881)]


def test_notification_snooze_persists_archived_state_and_supports_cancel(notifications_app, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import notifications as notifications_endpoint

    cdb = CollectionsDatabase.for_user(user_id=881)
    source = cdb.create_user_notification(
        kind="reminder_due",
        title="Follow up later",
        message="Bring this back after lunch",
        severity="info",
        link_type="note",
        link_id="note-77",
        link_url="/notes/note-77",
    )

    reconcile_calls: list[tuple[str, int]] = []
    unschedule_calls: list[str] = []

    class _FakeScheduler:
        async def reconcile_task(self, *, task_id: str, user_id: int) -> None:
            reconcile_calls.append((task_id, user_id))

        async def unschedule_task(self, task_id: str) -> None:
            unschedule_calls.append(task_id)

    monkeypatch.setattr(notifications_endpoint, "get_reminders_scheduler", lambda: _FakeScheduler(), raising=False)

    with TestClient(notifications_app) as client:
        snooze_response = client.post(f"/api/v1/notifications/{source.id}/snooze", json={"minutes": 15})
        assert snooze_response.status_code == 200, snooze_response.text
        snooze_payload = snooze_response.json()
        task_id = snooze_payload["task_id"]

        active_response = client.get("/api/v1/notifications")
        assert active_response.status_code == 200, active_response.text
        active_ids = {item["id"] for item in active_response.json()["items"]}
        assert source.id not in active_ids

        archived_response = client.get("/api/v1/notifications?include_archived=true")
        assert archived_response.status_code == 200, archived_response.text
        archived_item = next(item for item in archived_response.json()["items"] if item["id"] == source.id)
        assert archived_item["dismissed_at"] is not None
        assert archived_item["snooze_until"] == snooze_payload["run_at"]

        cancel_response = client.delete(f"/api/v1/notifications/{source.id}/snooze")
        assert cancel_response.status_code == 200, cancel_response.text
        assert cancel_response.json() == {"cancelled": True, "deleted_tasks": 1}

        archived_after_cancel = client.get("/api/v1/notifications?include_archived=true")
        assert archived_after_cancel.status_code == 200, archived_after_cancel.text
        archived_item_after_cancel = next(
            item for item in archived_after_cancel.json()["items"] if item["id"] == source.id
        )
        assert archived_item_after_cancel["snooze_until"] is None

    with pytest.raises(KeyError):
        cdb.get_reminder_task(task_id)

    assert reconcile_calls == [(task_id, 881)]
    assert unschedule_calls == [task_id]


def test_duplicate_notifications_keep_distinct_snooze_tasks(notifications_app, monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import notifications as notifications_endpoint

    cdb = CollectionsDatabase.for_user(user_id=881)
    first = cdb.create_user_notification(
        kind="reminder_due",
        title="Duplicate reminder",
        message="Check the same note later",
        severity="info",
        link_type="note",
        link_id="note-88",
        link_url="/notes/note-88",
    )
    second = cdb.create_user_notification(
        kind="reminder_due",
        title="Duplicate reminder",
        message="Check the same note later",
        severity="info",
        link_type="note",
        link_id="note-88",
        link_url="/notes/note-88",
    )

    unschedule_calls: list[str] = []

    class _FakeScheduler:
        async def reconcile_task(self, *, task_id: str, user_id: int) -> None:
            return None

        async def unschedule_task(self, task_id: str) -> None:
            unschedule_calls.append(task_id)

    monkeypatch.setattr(notifications_endpoint, "get_reminders_scheduler", lambda: _FakeScheduler(), raising=False)

    with TestClient(notifications_app) as client:
        first_snooze = client.post(f"/api/v1/notifications/{first.id}/snooze", json={"minutes": 15})
        assert first_snooze.status_code == 200, first_snooze.text
        first_payload = first_snooze.json()

        second_snooze = client.post(f"/api/v1/notifications/{second.id}/snooze", json={"minutes": 45})
        assert second_snooze.status_code == 200, second_snooze.text
        second_payload = second_snooze.json()

        archived = client.get("/api/v1/notifications?include_archived=true")
        assert archived.status_code == 200, archived.text
        archived_by_id = {item["id"]: item for item in archived.json()["items"]}
        assert archived_by_id[first.id]["snooze_until"] == first_payload["run_at"]
        assert archived_by_id[second.id]["snooze_until"] == second_payload["run_at"]

        cancel_first = client.delete(f"/api/v1/notifications/{first.id}/snooze")
        assert cancel_first.status_code == 200, cancel_first.text
        assert cancel_first.json() == {"cancelled": True, "deleted_tasks": 1}

        archived_after_cancel = client.get("/api/v1/notifications?include_archived=true")
        assert archived_after_cancel.status_code == 200, archived_after_cancel.text
        archived_after_cancel_by_id = {item["id"]: item for item in archived_after_cancel.json()["items"]}
        assert archived_after_cancel_by_id[first.id]["snooze_until"] is None
        assert archived_after_cancel_by_id[second.id]["snooze_until"] == second_payload["run_at"]

    with pytest.raises(KeyError):
        cdb.get_reminder_task(first_payload["task_id"])

    assert cdb.get_reminder_task(second_payload["task_id"]).run_at == second_payload["run_at"]
    assert unschedule_calls == [first_payload["task_id"]]
