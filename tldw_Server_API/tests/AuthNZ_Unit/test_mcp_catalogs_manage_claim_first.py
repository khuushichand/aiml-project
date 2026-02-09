from __future__ import annotations

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.endpoints import mcp_catalogs_manage
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


def _principal(*, user_id: int | None, roles: list[str] | None = None, is_admin: bool = False) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=user_id,
        roles=roles or [],
        permissions=[],
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


@pytest.mark.asyncio
async def test_require_org_manager_allows_admin_without_membership_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fail_if_called(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("admin principal should bypass org membership lookup")

    monkeypatch.setattr(mcp_catalogs_manage, "list_org_members", _fail_if_called)

    await mcp_catalogs_manage._require_org_manager(
        _principal(user_id=None, roles=["user"], is_admin=True),
        org_id=12,
    )


@pytest.mark.asyncio
async def test_require_org_manager_denies_missing_user_id_for_non_admin() -> None:
    with pytest.raises(HTTPException) as exc:
        await mcp_catalogs_manage._require_org_manager(
            _principal(user_id=None, roles=["user"], is_admin=False),
            org_id=7,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "Org manager role required"


@pytest.mark.asyncio
async def test_require_team_manager_allows_lead_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_team_members(team_id: int):
        assert team_id == 88
        return [
            {"user_id": 5, "role": "member"},
            {"user_id": 42, "role": "lead"},
        ]

    monkeypatch.setattr(mcp_catalogs_manage, "list_team_members", _fake_team_members)

    await mcp_catalogs_manage._require_team_manager(
        _principal(user_id=42, roles=["user"], is_admin=False),
        team_id=88,
    )


@pytest.mark.asyncio
async def test_require_team_manager_denies_non_manager_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_team_members(team_id: int):
        assert team_id == 3
        return [{"user_id": 42, "role": "member"}]

    monkeypatch.setattr(mcp_catalogs_manage, "list_team_members", _fake_team_members)

    with pytest.raises(HTTPException) as exc:
        await mcp_catalogs_manage._require_team_manager(
            _principal(user_id=42, roles=["user"], is_admin=False),
            team_id=3,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "Team manager role required"
