import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_prefers_principal_org_ids(monkeypatch):
    async def _fake_get_policy(db, org_id):
        return {"org_id": org_id, "source": "policy"}

    monkeypatch.setattr(auth_deps, "get_policy", _fake_get_policy)
    monkeypatch.setattr(
        auth_deps, "get_default_policy_from_env", lambda org_id: {"org_id": org_id, "source": "default"}
    )

    principal = AuthPrincipal(
        kind="user",
        user_id=123,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=[],
        permissions=[],
        is_admin=False,
        org_ids=[42],
        team_ids=[],
    )
    current_user = {"org_memberships": [{"org_id": 7}]}

    result = await auth_deps.get_org_policy_from_principal(db=None, principal=principal, current_user=current_user)
    assert result["org_id"] == 42
    assert result["source"] == "policy"


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_falls_back_to_user_memberships(monkeypatch):
    async def _fake_get_policy(db, org_id):
        return {"org_id": org_id, "source": "policy"}

    monkeypatch.setattr(auth_deps, "get_policy", _fake_get_policy)
    monkeypatch.setattr(
        auth_deps, "get_default_policy_from_env", lambda org_id: {"org_id": org_id, "source": "default"}
    )

    principal = AuthPrincipal(
        kind="user",
        user_id=123,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=[],
        permissions=[],
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )
    current_user = {"org_memberships": [{"org_id": 7}]}

    result = await auth_deps.get_org_policy_from_principal(db=None, principal=principal, current_user=current_user)
    assert result["org_id"] == 7
    assert result["source"] == "policy"


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_single_user_fallback(monkeypatch):
    async def _fake_get_policy(db, org_id):
        return {"org_id": org_id}

    monkeypatch.setattr(auth_deps, "get_policy", _fake_get_policy)
    monkeypatch.setattr(
        auth_deps, "get_default_policy_from_env", lambda org_id: {"org_id": org_id, "source": "default"}
    )
    monkeypatch.setattr(auth_deps, "is_single_user_mode", lambda: True)

    principal = AuthPrincipal(
        kind="single_user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="api_key",
        jti=None,
        roles=["admin"],
        permissions=["*"],
        is_admin=True,
        org_ids=[],
        team_ids=[],
    )
    current_user = {"org_memberships": []}

    result = await auth_deps.get_org_policy_from_principal(db=None, principal=principal, current_user=current_user)
    # Synthetic org_id=1 is used to mirror legacy single-user behaviour.
    assert result["org_id"] == 1


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_raises_when_no_org(monkeypatch):
    monkeypatch.setattr(auth_deps, "is_single_user_mode", lambda: False)

    principal = AuthPrincipal(
        kind="user",
        user_id=123,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=[],
        permissions=[],
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )
    current_user = {"org_memberships": []}

    with pytest.raises(HTTPException) as exc_info:
        await auth_deps.get_org_policy_from_principal(db=None, principal=principal, current_user=current_user)

    err = exc_info.value
    assert err.status_code == 400
    assert "no organization memberships" in err.detail

