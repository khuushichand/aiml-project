from typing import Any

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    require_permissions,
    require_roles,
)
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
        subject=None,
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=permissions or [],
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


@pytest.mark.asyncio
async def test_require_permissions_allows_when_permission_present():
    principal = _make_principal(permissions=["media.create", "media.read"])
    dep = require_permissions("media.create")

    result = await dep(principal)  # type: ignore[arg-type]
    assert result is principal


@pytest.mark.asyncio
async def test_require_permissions_allows_admin_even_without_specific_perm():
    principal = _make_principal(is_admin=True, permissions=[])
    dep = require_permissions("system.configure")

    result = await dep(principal)  # type: ignore[arg-type]
    assert result is principal


@pytest.mark.asyncio
async def test_require_permissions_denies_when_missing_perm_and_not_admin():
    principal = _make_principal(permissions=["media.read"])
    dep = require_permissions("media.create")

    with pytest.raises(HTTPException) as exc_info:
        await dep(principal)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 403
    assert "media.create" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_require_roles_allows_when_role_present():
    principal = _make_principal(roles=["user", "editor"])
    dep = require_roles("editor")

    result = await dep(principal)  # type: ignore[arg-type]
    assert result is principal


@pytest.mark.asyncio
async def test_require_roles_denies_when_missing_role_and_not_admin():
    principal = _make_principal(roles=["user"])
    dep = require_roles("admin")

    with pytest.raises(HTTPException) as exc_info:
        await dep(principal)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 403
    assert "admin" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_require_roles_allows_admin_even_without_role():
    principal = _make_principal(is_admin=True, roles=["user"])
    dep = require_roles("admin")

    result: Any = await dep(principal)  # type: ignore[arg-type]
    assert result is principal

