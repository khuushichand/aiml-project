import pytest

from tldw_Server_API.app.api.v1.API_Deps import org_deps


class _DummyPrincipal:
    def __init__(self, user_id: int, *, is_admin: bool = False):
        self.user_id = user_id
        self.is_admin = is_admin


@pytest.mark.asyncio
async def test_get_active_org_id_returns_explicit_org_id(monkeypatch):
    principal = _DummyPrincipal(user_id=1)

    async def fake_membership(user_id: int, org_id: int):
        assert user_id == principal.user_id
        assert org_id == 42
        return {"org_id": org_id, "role": "member", "status": "active"}

    async def fake_get_user_orgs(_: object):
        raise AssertionError("get_user_orgs should not be called when org_id is provided")

    monkeypatch.setattr(org_deps, "_get_user_org_membership", fake_membership)
    monkeypatch.setattr(org_deps, "get_user_orgs", fake_get_user_orgs)

    org_id = await org_deps.get_active_org_id(
        principal=principal,
        x_tldw_org_id=None,
        org_id=42,
    )
    assert org_id == 42


@pytest.mark.asyncio
async def test_get_active_org_id_uses_primary_org(monkeypatch):
    principal = _DummyPrincipal(user_id=2)

    async def fake_get_user_orgs(p: object):
        assert p is principal
        return [{"org_id": 123}, {"org_id": 456}]

    async def fake_membership(*_args, **_kwargs):
        raise AssertionError("membership lookup should not be called without org_id/header")

    monkeypatch.setattr(org_deps, "_get_user_org_membership", fake_membership)
    monkeypatch.setattr(org_deps, "get_user_orgs", fake_get_user_orgs)

    org_id = await org_deps.get_active_org_id(
        principal=principal,
        x_tldw_org_id=None,
        org_id=None,
    )
    assert org_id == 123


@pytest.mark.asyncio
async def test_get_active_org_id_returns_none_when_no_orgs(monkeypatch):
    principal = _DummyPrincipal(user_id=3)

    async def fake_get_user_orgs(_: object):
        return []

    async def fake_membership(*_args, **_kwargs):
        raise AssertionError("membership lookup should not be called without org_id/header")

    monkeypatch.setattr(org_deps, "_get_user_org_membership", fake_membership)
    monkeypatch.setattr(org_deps, "get_user_orgs", fake_get_user_orgs)

    org_id = await org_deps.get_active_org_id(
        principal=principal,
        x_tldw_org_id=None,
        org_id=None,
    )
    assert org_id is None


@pytest.mark.parametrize(
    "membership, expected",
    [
        (None, False),
        ({}, False),
        ({"status": None}, False),
        ({"status": "active"}, True),
        ({"status": "inactive"}, False),
    ],
)
def test_is_membership_active_requires_explicit_status(membership, expected):
     assert org_deps._is_membership_active(membership) is expected
