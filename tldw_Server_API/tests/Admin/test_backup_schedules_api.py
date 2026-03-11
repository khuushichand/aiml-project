from __future__ import annotations

import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.main import app


def _setup_env(tmp_path) -> None:
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-api-key"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'users_test_backup_schedules.db'}"
    os.environ["TLDW_DB_ALLOWED_BASE_DIRS"] = str(tmp_path)
    os.environ["TLDW_DB_BACKUP_PATH"] = str(tmp_path / "backups")
    os.environ["USER_DB_BASE_DIR"] = str(tmp_path / "user_dbs")


async def _reset_authnz_state() -> None:
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    await reset_db_pool()
    reset_settings()
    await reset_session_manager()


@pytest.mark.asyncio
async def test_backup_schedule_roundtrip_crud(tmp_path) -> None:
    _setup_env(tmp_path)
    await _reset_authnz_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}

    with TestClient(app, headers=headers) as client:
        create_resp = client.post(
            "/api/v1/admin/backup-schedules",
            json={
                "dataset": "authnz",
                "frequency": "daily",
                "time_of_day": "02:00",
                "retention_count": 30,
            },
        )
        assert create_resp.status_code == 200, create_resp.text
        created = create_resp.json()["item"]
        schedule_id = created["id"]
        assert created["dataset"] == "authnz"
        assert created["is_paused"] is False

        list_resp = client.get("/api/v1/admin/backup-schedules")
        assert list_resp.status_code == 200, list_resp.text
        payload = list_resp.json()
        assert payload["total"] == 1
        assert payload["items"][0]["id"] == schedule_id

        update_resp = client.patch(
            f"/api/v1/admin/backup-schedules/{schedule_id}",
            json={
                "frequency": "weekly",
                "time_of_day": "03:00",
                "retention_count": 21,
            },
        )
        assert update_resp.status_code == 200, update_resp.text
        updated = update_resp.json()["item"]
        assert updated["frequency"] == "weekly"
        assert updated["time_of_day"] == "03:00"
        assert updated["retention_count"] == 21

        pause_resp = client.post(f"/api/v1/admin/backup-schedules/{schedule_id}/pause")
        assert pause_resp.status_code == 200, pause_resp.text
        assert pause_resp.json()["item"]["is_paused"] is True

        resume_resp = client.post(f"/api/v1/admin/backup-schedules/{schedule_id}/resume")
        assert resume_resp.status_code == 200, resume_resp.text
        assert resume_resp.json()["item"]["is_paused"] is False

        delete_resp = client.delete(f"/api/v1/admin/backup-schedules/{schedule_id}")
        assert delete_resp.status_code == 200, delete_resp.text
        assert delete_resp.json()["status"] == "deleted"

        final_list = client.get("/api/v1/admin/backup-schedules")
        assert final_list.status_code == 200, final_list.text
        assert final_list.json()["total"] == 0


@pytest.mark.asyncio
async def test_create_backup_schedule_requires_target_user_for_per_user_dataset(tmp_path) -> None:
    _setup_env(tmp_path)
    await _reset_authnz_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}

    with TestClient(app, headers=headers) as client:
        response = client.post(
            "/api/v1/admin/backup-schedules",
            json={
                "dataset": "media",
                "frequency": "daily",
                "time_of_day": "02:00",
                "retention_count": 7,
            },
        )
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "target_user_required"


@pytest.mark.asyncio
async def test_create_backup_schedule_forbids_target_user_for_authnz(tmp_path) -> None:
    _setup_env(tmp_path)
    await _reset_authnz_state()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}

    with TestClient(app, headers=headers) as client:
        response = client.post(
            "/api/v1/admin/backup-schedules",
            json={
                "dataset": "authnz",
                "target_user_id": 9,
                "frequency": "daily",
                "time_of_day": "02:00",
                "retention_count": 14,
            },
        )
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "target_user_forbidden"


@pytest.mark.asyncio
async def test_create_backup_schedule_rejects_out_of_scope_user(tmp_path, monkeypatch) -> None:
    _setup_env(tmp_path)
    await _reset_authnz_state()

    principal = AuthPrincipal(
        kind="user",
        user_id=41,
        subject="user:41",
        roles=["admin"],
        is_admin=True,
    )

    async def _fake_scope_check(*args, **kwargs):
        raise HTTPException(status_code=403, detail="Not authorized to manage users outside your organization or team")

    app.dependency_overrides[get_auth_principal] = lambda: principal
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.admin.admin_data_ops._enforce_admin_user_scope",
        _fake_scope_check,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/admin/backup-schedules",
                json={
                    "dataset": "media",
                    "target_user_id": 99,
                    "frequency": "daily",
                    "time_of_day": "02:00",
                    "retention_count": 7,
                },
            )
            assert response.status_code == 403, response.text
            assert response.json()["detail"] == "Not authorized to manage users outside your organization or team"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_authnz_backup_schedule_requires_platform_admin(tmp_path) -> None:
    _setup_env(tmp_path)
    await _reset_authnz_state()

    principal = AuthPrincipal(
        kind="user",
        user_id=51,
        subject="user:51",
        roles=["admin"],
        is_admin=True,
    )

    app.dependency_overrides[get_auth_principal] = lambda: principal

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/admin/backup-schedules",
                json={
                    "dataset": "authnz",
                    "frequency": "daily",
                    "time_of_day": "02:00",
                    "retention_count": 14,
                },
            )
            assert response.status_code == 403, response.text
            assert response.json()["detail"] == "platform_admin_required"
    finally:
        app.dependency_overrides.clear()
