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
    # Explicitly simulate single-user profile mode so the helper takes
    # the synthetic org_id=1 path regardless of global defaults.
    monkeypatch.setattr(auth_deps, "is_single_user_mode", lambda: True, raising=False)
    monkeypatch.setattr(auth_deps, "is_single_user_profile_mode", lambda: True, raising=False)
    # Default (flag unset) uses principal/profile-driven path, but single-user principal
    # in a single-user profile still resolves to org_id=1.
    monkeypatch.delenv("ORG_POLICY_SINGLE_USER_PRINCIPAL", raising=False)

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
    # Force non-single-user profile so the helper raises 400 instead of
    # taking the synthetic org_id=1 path.
    monkeypatch.setattr(auth_deps, "is_single_user_mode", lambda: False, raising=False)
    monkeypatch.setattr(auth_deps, "is_single_user_profile_mode", lambda: False, raising=False)
    # Flag state should not matter when profile is not single-user: no org → 400.
    monkeypatch.setenv("ORG_POLICY_SINGLE_USER_PRINCIPAL", "1")

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


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_flag_enabled_principal_controls_fallback(monkeypatch):
    """When ORG_POLICY_SINGLE_USER_PRINCIPAL=1, fallback to org_id=1 is principal/profile-driven."""

    async def _fake_get_policy(db, org_id):
        return {"org_id": org_id}

    monkeypatch.setattr(auth_deps, "get_policy", _fake_get_policy)
    monkeypatch.setattr(
        auth_deps, "get_default_policy_from_env", lambda org_id: {"org_id": org_id, "source": "default"}
    )
    # Enable principal-driven fallback explicitly (default behaviour) and force single-user profile.
    monkeypatch.setenv("ORG_POLICY_SINGLE_USER_PRINCIPAL", "1")
    monkeypatch.setattr(auth_deps, "is_single_user_mode", lambda: True, raising=False)
    monkeypatch.setattr(auth_deps, "is_single_user_profile_mode", lambda: True, raising=False)

    # Principal that clearly represents the single-user bootstrap admin.
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
    assert result["org_id"] == 1


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_flag_enabled_non_single_user_principal_raises(monkeypatch):
    """When ORG_POLICY_SINGLE_USER_PRINCIPAL=1 and profile is single-user, non-single-user principals should not get org_id=1."""

    monkeypatch.setenv("ORG_POLICY_SINGLE_USER_PRINCIPAL", "1")
    monkeypatch.setattr(auth_deps, "is_single_user_mode", lambda: True, raising=False)
    monkeypatch.setattr(auth_deps, "is_single_user_profile_mode", lambda: True, raising=False)

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


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_flag_disabled_legacy_mode_driven(monkeypatch):
    """When ORG_POLICY_SINGLE_USER_PRINCIPAL=0, legacy mode/profile-driven fallback is used."""

    async def _fake_get_policy(db, org_id):
        return {"org_id": org_id}

    monkeypatch.setattr(auth_deps, "get_policy", _fake_get_policy)
    monkeypatch.setattr(
        auth_deps, "get_default_policy_from_env", lambda org_id: {"org_id": org_id, "source": "default"}
    )
    # Explicitly disable principal-driven path and mark profile as single-user.
    monkeypatch.setenv("ORG_POLICY_SINGLE_USER_PRINCIPAL", "0")
    monkeypatch.setattr(auth_deps, "is_single_user_mode", lambda: True, raising=False)
    monkeypatch.setattr(auth_deps, "is_single_user_profile_mode", lambda: True, raising=False)

    # Principal that is not explicitly single-user should still benefit from legacy synthetic org_id=1.
    principal = AuthPrincipal(
        kind="user",
        user_id=999,
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

    result = await auth_deps.get_org_policy_from_principal(db=None, principal=principal, current_user=current_user)
    assert result["org_id"] == 1
