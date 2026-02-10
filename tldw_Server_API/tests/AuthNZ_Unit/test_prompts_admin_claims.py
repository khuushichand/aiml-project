from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.endpoints import prompts as prompts_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


def _make_user(
    *,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    is_admin: bool = False,
    is_superuser: bool = False,
) -> User:
    return User(
        id=1,
        username="prompts-user",
        email="prompts@example.com",
        is_active=True,
        roles=list(roles or []),
        permissions=list(permissions or []),
        is_admin=is_admin,
        is_superuser=is_superuser,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_prompts_auth_allows_admin_role_claim(monkeypatch):
    async def _fake_resolve(*_args, **_kwargs):
        return _make_user(roles=["admin"], permissions=[], is_admin=False)

    monkeypatch.setattr(prompts_mod, "_resolve_prompts_auth_user", _fake_resolve, raising=True)

    allowed = await prompts_mod.verify_prompts_auth(
        request=SimpleNamespace(),
        Token="token",
    )
    assert allowed is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_prompts_auth_rejects_legacy_admin_flags_without_claims(monkeypatch):
    async def _fake_resolve(*_args, **_kwargs):
        return _make_user(
            roles=["user"],
            permissions=["prompts.read"],
            is_admin=True,
            is_superuser=True,
        )

    monkeypatch.setattr(prompts_mod, "_resolve_prompts_auth_user", _fake_resolve, raising=True)

    with pytest.raises(HTTPException) as excinfo:
        await prompts_mod.verify_prompts_auth(
            request=SimpleNamespace(),
            Token="token",
        )
    assert excinfo.value.status_code == 403
