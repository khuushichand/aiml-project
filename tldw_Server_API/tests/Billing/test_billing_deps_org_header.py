"""
Unit tests for billing dependency org resolution logic.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.API_Deps import billing_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


class _FakeRepoIgnoreHeader:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def get_org_member(self, org_id: int, user_id: int):
        return None

    async def list_org_memberships_for_user(self, user_id: int):
        return [{"org_id": 42}]


class _FakeRepoAdminHeader:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def get_org_member(self, org_id: int, user_id: int):
        return None

    async def list_org_memberships_for_user(self, user_id: int):
        return [{"org_id": 11}]


class _FakeRepoMemberHeader:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def get_org_member(self, org_id: int, user_id: int):
        if org_id == 999:
            return {"org_id": org_id, "user_id": user_id}
        return None

    async def list_org_memberships_for_user(self, user_id: int):
        return [{"org_id": 42}]


@pytest.mark.asyncio
async def test_resolve_org_id_rejects_header_for_non_member(monkeypatch) -> None:
    """Non-members should not be able to force org selection via header."""

    async def _fake_get_db_pool():
        return object()

    monkeypatch.setattr(billing_deps, "get_db_pool", _fake_get_db_pool, raising=False)
    monkeypatch.setattr(billing_deps, "AuthnzOrgsTeamsRepo", _FakeRepoIgnoreHeader, raising=False)

    principal = AuthPrincipal(kind="user", user_id=7, is_admin=False)
    with pytest.raises(HTTPException) as exc_info:
        await billing_deps._resolve_org_id(principal, x_tldw_org_id=999)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_resolve_org_id_allows_header_for_admin(monkeypatch) -> None:
    """Admins should be allowed to specify org via header."""

    async def _fake_get_db_pool():
        return object()

    monkeypatch.setattr(billing_deps, "get_db_pool", _fake_get_db_pool, raising=False)
    monkeypatch.setattr(billing_deps, "AuthnzOrgsTeamsRepo", _FakeRepoAdminHeader, raising=False)

    principal = AuthPrincipal(kind="user", user_id=8, is_admin=True)
    org_id = await billing_deps._resolve_org_id(principal, x_tldw_org_id=999)

    assert org_id == 999


@pytest.mark.asyncio
async def test_resolve_org_id_allows_header_for_member(monkeypatch) -> None:
    """Members should be able to select their org via header."""

    async def _fake_get_db_pool():
        return object()

    monkeypatch.setattr(billing_deps, "get_db_pool", _fake_get_db_pool, raising=False)
    monkeypatch.setattr(billing_deps, "AuthnzOrgsTeamsRepo", _FakeRepoMemberHeader, raising=False)

    principal = AuthPrincipal(kind="user", user_id=9, is_admin=False)
    org_id = await billing_deps._resolve_org_id(principal, x_tldw_org_id=999)

    assert org_id == 999


@pytest.mark.asyncio
async def test_resolve_org_id_allows_query_param_for_member(monkeypatch) -> None:
    """Members should be able to select their org via query param."""

    async def _fake_get_db_pool():
        return object()

    monkeypatch.setattr(billing_deps, "get_db_pool", _fake_get_db_pool, raising=False)
    monkeypatch.setattr(billing_deps, "AuthnzOrgsTeamsRepo", _FakeRepoMemberHeader, raising=False)

    principal = AuthPrincipal(kind="user", user_id=10, is_admin=False)
    org_id = await billing_deps._resolve_org_id(principal, org_id=999)

    assert org_id == 999
