import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.API_Deps import org_deps


class _DummyPrincipal:
    def __init__(self, user_id: int):
        self.user_id = user_id


@pytest.mark.asyncio
async def test_resolve_org_id_or_default_returns_explicit_org_id(monkeypatch):
    principal = _DummyPrincipal(user_id=1)

    async def fake_get_user_orgs(_: object):
        raise AssertionError("get_user_orgs should not be called when org_id is provided")

    monkeypatch.setattr(org_deps, "get_user_orgs", fake_get_user_orgs)

    org_id = await org_deps.resolve_org_id_or_default(42, principal)
    assert org_id == 42


@pytest.mark.asyncio
async def test_resolve_org_id_or_default_uses_primary_org(monkeypatch):
    principal = _DummyPrincipal(user_id=2)

    async def fake_get_user_orgs(p: object):
        assert p is principal
        return [{"org_id": 123}, {"org_id": 456}]

    monkeypatch.setattr(org_deps, "get_user_orgs", fake_get_user_orgs)

    org_id = await org_deps.resolve_org_id_or_default(None, principal)
    assert org_id == 123


@pytest.mark.asyncio
async def test_resolve_org_id_or_default_raises_when_no_orgs(monkeypatch):
    principal = _DummyPrincipal(user_id=3)

    async def fake_get_user_orgs(_: object):
        return []

    monkeypatch.setattr(org_deps, "get_user_orgs", fake_get_user_orgs)

    with pytest.raises(HTTPException) as exc_info:
        await org_deps.resolve_org_id_or_default(None, principal)

    exc = exc_info.value
    assert exc.status_code == 404
    assert "not a member of any organization" in exc.detail

