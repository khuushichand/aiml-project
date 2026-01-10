from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
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
            permissions=[SYSTEM_CONFIGURE],
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


def test_claims_settings_get_and_update():


     from tldw_Server_API.app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_auth_principal] = _principal_override_admin()

    original = {
        "ENABLE_INGESTION_CLAIMS": settings.get("ENABLE_INGESTION_CLAIMS"),
        "CLAIMS_MAX_PER_CHUNK": settings.get("CLAIMS_MAX_PER_CHUNK"),
    }
    try:
        with TestClient(fastapi_app) as client:
            r = client.get("/api/v1/claims/settings")
            assert r.status_code == 200, r.text
            data = r.json()
            assert "enable_ingestion_claims" in data

            payload = {
                "enable_ingestion_claims": True,
                "claims_max_per_chunk": 4,
                "persist": False,
            }
            r2 = client.put("/api/v1/claims/settings", json=payload)
            assert r2.status_code == 200, r2.text
            data2 = r2.json()
            assert data2.get("enable_ingestion_claims") is True
            assert int(data2.get("claims_max_per_chunk")) == 4
    finally:
        for key, value in original.items():
            if value is None:
                try:
                    settings.pop(key, None)
                except Exception:
                    pass
            else:
                settings[key] = value
        fastapi_app.dependency_overrides.pop(get_auth_principal, None)
