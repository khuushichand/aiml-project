from __future__ import annotations

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.endpoints.evaluations import evaluations_auth
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


def _make_user(
    *,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    is_admin: bool = False,
) -> User:
    return User(
        id=1,
        username="eval-user",
        email="eval@example.com",
        is_active=True,
        is_admin=is_admin,
        roles=list(roles or []),
        permissions=list(permissions or []),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_eval_permissions_allows_roles_admin_without_legacy_bool():
    checker = evaluations_auth.require_eval_permissions("evaluations.manage")
    user = _make_user(roles=["admin"], permissions=[], is_admin=False)

    resolved = await checker(current_user=user)
    assert resolved is user


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_eval_permissions_allows_system_configure_claim():
    checker = evaluations_auth.require_eval_permissions("evaluations.manage")
    user = _make_user(roles=["user"], permissions=["system.configure"], is_admin=False)

    resolved = await checker(current_user=user)
    assert resolved is user


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_eval_permissions_rejects_legacy_is_admin_without_claims():
    checker = evaluations_auth.require_eval_permissions("evaluations.manage")
    user = _make_user(roles=["user"], permissions=[], is_admin=True)

    with pytest.raises(HTTPException) as excinfo:
        await checker(current_user=user)
    assert excinfo.value.status_code == 403
