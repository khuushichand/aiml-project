import pytest
from fastapi import HTTPException
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import setup_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


def _make_request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/setup/status",
        "headers": [],
        "client": ("127.0.0.1", 1234),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_require_admin_for_remote_rejects_non_admin(monkeypatch):
    async def fake_get_auth_principal(_request):
        return AuthPrincipal(kind="user", user_id=999, roles=[], permissions=[], is_admin=False)

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.API_Deps.auth_deps.get_auth_principal",
        fake_get_auth_principal,
    )

    with pytest.raises(HTTPException) as excinfo:
        await setup_deps._require_admin_for_remote(_make_request())

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_require_admin_for_remote_allows_admin_role(monkeypatch):
    async def fake_get_auth_principal(_request):
        return AuthPrincipal(
            kind="user",
            user_id=999,
            roles=["admin"],
            permissions=["system.configure"],
            is_admin=False,
        )

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.API_Deps.auth_deps.get_auth_principal",
        fake_get_auth_principal,
    )

    await setup_deps._require_admin_for_remote(_make_request())


@pytest.mark.asyncio
async def test_require_local_setup_access_calls_admin_guard(monkeypatch):
    called = {"value": False}

    async def fake_guard(_request):
        called["value"] = True

    monkeypatch.setenv("TLDW_SETUP_ALLOW_REMOTE", "1")
    monkeypatch.setattr(setup_deps, "_config_allows_remote", lambda: False)
    monkeypatch.setattr(setup_deps, "_require_admin_for_remote", fake_guard)

    await setup_deps.require_local_setup_access(_make_request())

    assert called["value"] is True
