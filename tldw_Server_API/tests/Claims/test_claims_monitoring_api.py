import os
import tempfile
from typing import AsyncGenerator

from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext
from tldw_Server_API.app.core.AuthNZ.permissions import CLAIMS_ADMIN
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.config import settings


def _principal_override_admin():
    async def _override(request=None):
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="admin",
            token_type="access",
            jti=None,
            roles=["admin"],
            permissions=[CLAIMS_ADMIN],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        if request is not None:
            try:
                request.state.auth = AuthContext(
                    principal=principal,
                    ip=None,
                    user_agent=None,
                    request_id=None,
                )
            except Exception:
                pass
        return principal

    return _override


def _seed_monitoring_db() -> str:
    tmpdir = tempfile.mkdtemp(prefix="claims_monitoring_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()
    db.close_connection()
    return db_path


def test_claims_monitoring_config_and_alerts():
    from tldw_Server_API.app.main import app as fastapi_app

    class _User:
        def __init__(self) -> None:
            self.id = 1
            self.username = "tester"
            self.is_admin = True

    async def _override_user():
        return _User()

    db_path = _seed_monitoring_db()

    async def _override_db() -> AsyncGenerator[MediaDatabase, None]:
        override_db = MediaDatabase(db_path=db_path, client_id="1")
        try:
            yield override_db
        finally:
            try:
                override_db.close_connection()
            except Exception:
                pass

    fastapi_app.dependency_overrides[get_auth_principal] = _principal_override_admin()
    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_media_db_for_user] = _override_db

    original = {
        "CLAIMS_MONITORING_ENABLED": settings.get("CLAIMS_MONITORING_ENABLED"),
        "CLAIMS_ALERT_THRESHOLD_DEFAULT": settings.get("CLAIMS_ALERT_THRESHOLD_DEFAULT"),
    }
    try:
        with TestClient(fastapi_app) as client:
            r = client.get("/api/v1/claims/monitoring/config")
            assert r.status_code == 200, r.text
            data = r.json()
            assert "claims_monitoring_enabled" in data

            payload = {
                "claims_monitoring_enabled": True,
                "claims_alert_threshold_default": 0.4,
                "persist": False,
            }
            r2 = client.patch("/api/v1/claims/monitoring/config", json=payload)
            assert r2.status_code == 200, r2.text
            data2 = r2.json()
            assert data2["claims_monitoring_enabled"] is True

            alert_payload = {
                "threshold_ratio": 0.6,
                "email_recipients": ["alerts@example.com"],
            }
            r3 = client.post("/api/v1/claims/alerts", json=alert_payload)
            assert r3.status_code == 200, r3.text
            alert = r3.json()
            assert alert["threshold_ratio"] == 0.6
            alert_id = int(alert["id"])

            r4 = client.get("/api/v1/claims/alerts")
            assert r4.status_code == 200, r4.text
            assert any(int(item["id"]) == alert_id for item in r4.json())

            r5 = client.patch(f"/api/v1/claims/alerts/{alert_id}", json={"enabled": False})
            assert r5.status_code == 200, r5.text
            assert r5.json()["enabled"] is False

            r6 = client.delete(f"/api/v1/claims/alerts/{alert_id}")
            assert r6.status_code == 200, r6.text
    finally:
        for key, value in original.items():
            if value is None:
                settings.pop(key, None)
            else:
                settings[key] = value
        fastapi_app.dependency_overrides.pop(get_auth_principal, None)
        fastapi_app.dependency_overrides.pop(get_request_user, None)
        fastapi_app.dependency_overrides.pop(get_media_db_for_user, None)
