from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _setup_env(tmp_path) -> None:
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-api-key"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'users_test_admin_monitoring.db'}"


async def _seed_assignable_user() -> int:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

    pool = await get_db_pool()
    username = "monitoring_assignee"
    email = "monitoring_assignee@example.com"
    await pool.execute(
        "INSERT OR IGNORE INTO users (uuid, username, email, password_hash, is_active) VALUES (?,?,?,?,1)",
        str(uuid.uuid4()),
        username,
        email,
        "x",
    )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = ?", username)
    return int(user_id)


@pytest.mark.asyncio
async def test_admin_monitoring_rules_and_actions(tmp_path) -> None:
    _setup_env(tmp_path)

    from tldw_Server_API.app.api.v1.endpoints import monitoring as monitoring_endpoints
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    os.environ["MONITORING_ALERTS_DB"] = str(tmp_path / "monitoring_alerts.db")

    await reset_db_pool()
    reset_settings()
    await reset_session_manager()
    monitoring_endpoints._TOPIC_MONITORING_DB = None

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}

    with TestClient(app, headers=headers) as client:
        assignee_id = await _seed_assignable_user()

        create_rule_resp = client.post(
            "/api/v1/admin/monitoring/alert-rules",
            json={
                "metric": "cpu_percent",
                "operator": "gte",
                "threshold": 90.0,
                "duration_minutes": 10,
                "severity": "warning",
                "enabled": True,
            },
        )
        assert create_rule_resp.status_code == 200, create_rule_resp.text
        rule_id = create_rule_resp.json()["item"]["id"]

        list_rules_resp = client.get("/api/v1/admin/monitoring/alert-rules")
        assert list_rules_resp.status_code == 200, list_rules_resp.text
        assert any(item["id"] == rule_id for item in list_rules_resp.json()["items"])

        assign_resp = client.post(
            "/api/v1/admin/monitoring/alerts/alert:7/assign",
            json={"assigned_to_user_id": assignee_id},
        )
        assert assign_resp.status_code == 200, assign_resp.text
        assert assign_resp.json()["item"]["assigned_to_user_id"] == assignee_id

        unassign_resp = client.post(
            "/api/v1/admin/monitoring/alerts/alert:7/assign",
            json={"assigned_to_user_id": None},
        )
        assert unassign_resp.status_code == 200, unassign_resp.text
        assert unassign_resp.json()["item"]["assigned_to_user_id"] is None

        snooze_resp = client.post(
            "/api/v1/admin/monitoring/alerts/alert:7/snooze",
            json={"snoozed_until": "2026-03-10T11:00:00Z"},
        )
        assert snooze_resp.status_code == 200, snooze_resp.text
        assert snooze_resp.json()["item"]["snoozed_until"] == "2026-03-10T11:00:00Z"

        escalate_resp = client.post(
            "/api/v1/admin/monitoring/alerts/alert:7/escalate",
            json={"severity": "critical"},
        )
        assert escalate_resp.status_code == 200, escalate_resp.text
        assert escalate_resp.json()["item"]["escalated_severity"] == "critical"

        public_alerts_resp = client.get("/api/v1/monitoring/alerts")
        assert public_alerts_resp.status_code == 200, public_alerts_resp.text
        assert all(item["alert_identity"] != "alert:7" for item in public_alerts_resp.json()["items"])

        history_resp = client.get(
            "/api/v1/admin/monitoring/alerts/history",
            params={"alert_identity": "alert:7"},
        )
        assert history_resp.status_code == 200, history_resp.text
        assert [item["action"] for item in history_resp.json()["items"][:4]] == [
            "escalated",
            "snoozed",
            "unassigned",
            "assigned",
        ]

        delete_resp = client.delete(f"/api/v1/admin/monitoring/alert-rules/{rule_id}")
        assert delete_resp.status_code == 200, delete_resp.text
        assert delete_resp.json()["status"] == "deleted"
