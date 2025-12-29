from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _setup_env(tmp_path):
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-api-key"
    os.environ["TLDW_DB_BACKUP_PATH"] = str(tmp_path / "backups")


async def _seed_authnz_data() -> int:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, is_postgres_backend

    pool = await get_db_pool()
    username = "dataops_user"
    email = "dataops_user@example.com"
    if await is_postgres_backend():
        await pool.execute(
            """
            INSERT INTO users (uuid, username, email, password_hash, is_active)
            VALUES (?,?,?,?,1)
            ON CONFLICT (username) DO NOTHING
            """,
            str(uuid.uuid4()),
            username,
            email,
            "x",
        )
    else:
        await pool.execute(
            "INSERT OR IGNORE INTO users (uuid, username, email, password_hash, is_active) VALUES (?,?,?,?,1)",
            str(uuid.uuid4()),
            username,
            email,
            "x",
        )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = ?", username)
    await pool.execute(
        "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address, details) VALUES (?,?,?,?,?,?)",
        int(user_id),
        "dataops.test",
        "backup",
        1,
        "127.0.0.1",
        '{"ok": true}',
    )
    return int(user_id)


@pytest.mark.asyncio
async def test_admin_data_ops_backups_and_exports(tmp_path):
    _setup_env(tmp_path)

    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager

    await reset_db_pool()
    reset_settings()
    await reset_session_manager()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}

    with TestClient(app, headers=headers) as client:
        await _seed_authnz_data()

        create_resp = client.post(
            "/api/v1/admin/backups",
            json={"dataset": "authnz", "backup_type": "full"},
        )
        assert create_resp.status_code == 200, create_resp.text
        backup_id = create_resp.json()["item"]["id"]

        list_resp = client.get("/api/v1/admin/backups", params={"dataset": "authnz"})
        assert list_resp.status_code == 200, list_resp.text
        listed = list_resp.json()["items"]
        assert any(item["id"] == backup_id for item in listed)

        restore_resp = client.post(
            f"/api/v1/admin/backups/{backup_id}/restore",
            json={"dataset": "authnz", "confirm": True},
        )
        assert restore_resp.status_code == 200, restore_resp.text

        audit_export = client.get("/api/v1/admin/audit-log/export", params={"format": "csv"})
        assert audit_export.status_code == 200, audit_export.text
        assert "id,user_id,username,action" in audit_export.text.splitlines()[0]

        user_export = client.get("/api/v1/admin/users/export", params={"format": "csv"})
        assert user_export.status_code == 200, user_export.text
        assert "id,uuid,username,email,role" in user_export.text.splitlines()[0]


@pytest.mark.asyncio
async def test_admin_retention_policy_update(tmp_path):
    _setup_env(tmp_path)

    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager

    await reset_db_pool()
    reset_settings()
    await reset_session_manager()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}

    with TestClient(app, headers=headers) as client:
        list_resp = client.get("/api/v1/admin/retention-policies")
        assert list_resp.status_code == 200, list_resp.text
        policies = list_resp.json()["policies"]
        assert policies
        target = next(
            (policy["key"] for policy in policies if policy.get("key") == "audit_logs"),
            policies[0]["key"],
        )

        update_resp = client.put(
            f"/api/v1/admin/retention-policies/{target}",
            json={"days": 180},
        )
        assert update_resp.status_code == 200, update_resp.text
        payload = update_resp.json()
        assert payload["key"] == target
        assert payload["days"] == 180
