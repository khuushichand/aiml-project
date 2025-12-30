import json
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
    tmpdir = tempfile.mkdtemp(prefix="claims_monitoring_legacy_")
    db_path = os.path.join(tmpdir, "media.db")
    db = MediaDatabase(db_path=db_path, client_id="1")
    db.initialize_db()
    db.close_connection()
    return db_path


def test_claims_alerts_migrate_legacy_configs():
    from tldw_Server_API.app.main import app as fastapi_app

    class _User:
        def __init__(self) -> None:
            self.id = 1
            self.username = "tester"
            self.is_admin = True

    async def _override_user():
        return _User()

    db_path = _seed_monitoring_db()
    db = MediaDatabase(db_path=db_path, client_id="1")
    legacy = db.create_claims_monitoring_config(
        user_id="1",
        threshold_ratio=0.5,
        baseline_ratio=0.1,
        slack_webhook_url="https://example.com/slack",
        webhook_url="https://example.com/webhook",
        email_recipients=json.dumps(["legacy@example.com"]),
        enabled=True,
    )
    legacy_id = int(legacy["id"])
    db.close_connection()

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

    try:
        with TestClient(fastapi_app) as client:
            response = client.get("/api/v1/claims/alerts")
            assert response.status_code == 200, response.text
            items = response.json()
            assert len(items) == 1
            alert = items[0]
            assert int(alert["id"]) == legacy_id
            assert alert["name"].startswith("Legacy alert")
            assert alert["alert_type"] == "threshold_breach"
            assert alert["channels"]["slack"] is True
            assert alert["channels"]["webhook"] is True
            assert alert["channels"]["email"] is True

        db = MediaDatabase(db_path=db_path, client_id="1")
        assert db.list_claims_monitoring_configs("1") == []
        alerts = db.list_claims_monitoring_alerts("1")
        db.close_connection()
        assert len(alerts) == 1
        assert int(alerts[0]["id"]) == legacy_id
    finally:
        fastapi_app.dependency_overrides.pop(get_auth_principal, None)
        fastapi_app.dependency_overrides.pop(get_request_user, None)
        fastapi_app.dependency_overrides.pop(get_media_db_for_user, None)
