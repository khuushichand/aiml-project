from starlette.requests import Request

from tldw_Server_API.app.api.v1.endpoints import mcp_unified_endpoint as mcp_mod
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


def _make_request_with_principal(principal: AuthPrincipal | None) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/mcp/tool_catalogs",
            "headers": [],
        }
    )
    if principal is not None:
        request.state.auth = principal
    return request


def _make_principal(*, is_admin: bool, roles: list[str] | None = None) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject="1",
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=[],
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


def _make_token_data(*, roles: list[str] | None = None) -> mcp_mod.TokenData:
    return mcp_mod.TokenData(
        sub="1",
        username="user1",
        roles=roles or [],
        permissions=[],
        token_type="access",
    )


def test_catalog_admin_context_prefers_principal_admin_claims():
    request = _make_request_with_principal(_make_principal(is_admin=True, roles=["user"]))
    token = _make_token_data(roles=["user"])
    assert mcp_mod._is_catalog_admin_context(request, token) is True


def test_catalog_admin_context_principal_non_admin_overrides_token_admin_role():
    request = _make_request_with_principal(_make_principal(is_admin=False, roles=["user"]))
    token = _make_token_data(roles=["admin"])
    assert mcp_mod._is_catalog_admin_context(request, token) is False


def test_catalog_admin_context_falls_back_to_token_roles_when_principal_absent():
    request = _make_request_with_principal(None)
    token = _make_token_data(roles=["admin"])
    assert mcp_mod._is_catalog_admin_context(request, token) is True


def test_catalog_admin_context_returns_false_without_admin_claims_or_roles():
    request = _make_request_with_principal(None)
    token = _make_token_data(roles=["user"])
    assert mcp_mod._is_catalog_admin_context(request, token) is False


def test_catalog_admin_context_prefers_explicit_principal_argument():
    request = _make_request_with_principal(None)
    token = _make_token_data(roles=["admin"])
    principal = _make_principal(is_admin=False, roles=["user"])
    assert mcp_mod._is_catalog_admin_context(request, token, principal=principal) is False
