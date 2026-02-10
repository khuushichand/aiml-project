from __future__ import annotations

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


def _make_principal(
    *,
    is_admin: bool = False,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject="user:1",
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=permissions or [],
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


def test_legacy_require_admin_shim_is_removed() -> None:
    assert not hasattr(auth_deps, "require_admin")


def test_legacy_require_role_shim_is_removed() -> None:
    assert not hasattr(auth_deps, "require_role")


@pytest.mark.asyncio
async def test_claim_first_require_roles_rejects_boolean_only_admin_flag() -> None:
    checker = auth_deps.require_roles("admin")
    principal = _make_principal(is_admin=True, roles=["user"], permissions=[])
    with pytest.raises(HTTPException) as exc_info:
        await checker(principal)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_claim_first_require_permissions_allows_admin_claim_permission() -> None:
    checker = auth_deps.require_permissions("system.configure")
    principal = _make_principal(is_admin=False, roles=["user"], permissions=["system.configure"])
    resolved = await checker(principal)
    assert resolved is principal
