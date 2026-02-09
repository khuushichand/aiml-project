import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


def _principal(*, org_ids: list[int], subject: str | None = None, user_id: int = 123) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=user_id,
        api_key_id=None,
        subject=subject,
        token_type="access",
        jti=None,
        roles=[],
        permissions=[],
        is_admin=False,
        org_ids=org_ids,
        team_ids=[],
    )


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_prefers_principal_org_ids(monkeypatch):
    async def _fake_get_policy(db, org_id):
        return {"org_id": org_id, "source": "policy"}

    monkeypatch.setattr(auth_deps, "get_policy", _fake_get_policy)
    monkeypatch.setattr(
        auth_deps, "get_default_policy_from_env", lambda org_id: {"org_id": org_id, "source": "default"}
    )

    result = await auth_deps.get_org_policy_from_principal(db=None, principal=_principal(org_ids=[42]))
    assert result["org_id"] == 42
    assert result["source"] == "policy"


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_raises_without_org_claims():
    with pytest.raises(HTTPException) as exc_info:
        await auth_deps.get_org_policy_from_principal(db=None, principal=_principal(org_ids=[]))

    err = exc_info.value
    assert err.status_code == 400
    assert "no organization memberships" in err.detail


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_single_user_subject_fallback(monkeypatch):
    async def _fake_get_policy(db, org_id):
        return {"org_id": org_id}

    monkeypatch.setattr(auth_deps, "get_policy", _fake_get_policy)
    monkeypatch.setattr(
        auth_deps, "get_default_policy_from_env", lambda org_id: {"org_id": org_id, "source": "default"}
    )

    principal = _principal(org_ids=[], subject="single_user", user_id=1)
    result = await auth_deps.get_org_policy_from_principal(db=None, principal=principal)
    assert result["org_id"] == 1


@pytest.mark.asyncio
async def test_get_org_policy_from_principal_ignores_legacy_flag_and_stays_principal_only(monkeypatch):
    # Stage 4 tightening: legacy mode/profile fallback is retired for this helper.
    monkeypatch.setenv("ORG_POLICY_SINGLE_USER_PRINCIPAL", "0")

    with pytest.raises(HTTPException) as exc_info:
        await auth_deps.get_org_policy_from_principal(db=None, principal=_principal(org_ids=[]))

    err = exc_info.value
    assert err.status_code == 400
    assert "no organization memberships" in err.detail


@pytest.mark.asyncio
async def test_get_user_org_policy_delegates_to_principal(monkeypatch):
    sentinel = {"org_id": 99, "source": "delegate"}

    async def _fake_get_org_policy_from_principal(db=None, principal=None):
        return sentinel

    monkeypatch.setattr(auth_deps, "get_org_policy_from_principal", _fake_get_org_policy_from_principal)

    result = await auth_deps.get_user_org_policy(
        db=None,
        principal=_principal(org_ids=[]),
        current_user={"id": 1, "is_active": True, "is_verified": True},
    )
    assert result == sentinel
