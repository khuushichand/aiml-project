from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


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


def test_claims_extractors_list():


    from tldw_Server_API.app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_auth_principal] = _principal_override_admin()
    try:
        with TestClient(fastapi_app) as client:
            response = client.get("/api/v1/claims/extractors")
            assert response.status_code == 200, response.text
            data = response.json()
            assert data.get("default_mode")
            assert data.get("auto_mode") == "auto"
            extractors = data.get("extractors")
            assert isinstance(extractors, list)
            modes = {item.get("mode") for item in extractors}
            assert "heuristic" in modes
            assert "ner" in modes
    finally:
        fastapi_app.dependency_overrides.pop(get_auth_principal, None)
