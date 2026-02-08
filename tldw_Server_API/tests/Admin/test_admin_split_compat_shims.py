from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_admin_rbac_repo_factory_uses_root_compat_shim(monkeypatch) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod
    from tldw_Server_API.app.api.v1.endpoints.admin import admin_rbac

    sentinel_repo = object()
    monkeypatch.setattr(admin_mod, "_get_rbac_repo", lambda: sentinel_repo)

    assert admin_rbac._get_rbac_repo() is sentinel_repo


@pytest.mark.asyncio
async def test_admin_rbac_scope_enforcement_uses_root_compat_shim(monkeypatch) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod
    from tldw_Server_API.app.api.v1.endpoints.admin import admin_rbac

    calls: dict[str, object] = {}

    async def _fake_scope_check(principal, target_user_id: int, *, require_hierarchy: bool) -> None:
        calls["principal"] = principal
        calls["target_user_id"] = target_user_id
        calls["require_hierarchy"] = require_hierarchy

    monkeypatch.setattr(admin_mod, "_enforce_admin_user_scope", _fake_scope_check)

    principal = SimpleNamespace(user_id=1)
    await admin_rbac._enforce_admin_user_scope(principal, 42, require_hierarchy=True)

    assert calls == {
        "principal": principal,
        "target_user_id": 42,
        "require_hierarchy": True,
    }


def test_admin_backend_detector_is_loaded_via_root_compat_shim(monkeypatch) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod
    from tldw_Server_API.app.api.v1.endpoints.admin import admin_rate_limits, admin_rbac

    async def _fake_is_postgres_backend() -> bool:
        return True

    monkeypatch.setattr(admin_mod, "_is_postgres_backend", _fake_is_postgres_backend)

    assert admin_rbac._get_is_postgres_backend_fn() is _fake_is_postgres_backend
    assert admin_rate_limits._get_is_postgres_backend_fn() is _fake_is_postgres_backend


def test_admin_ops_platform_admin_check_uses_root_compat_shim(monkeypatch) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod
    from tldw_Server_API.app.api.v1.endpoints.admin import admin_ops

    calls: dict[str, object] = {}

    def _fake_require_platform_admin(principal) -> None:
        calls["principal"] = principal

    monkeypatch.setattr(admin_mod, "_require_platform_admin", _fake_require_platform_admin)

    principal = SimpleNamespace(user_id=99)
    admin_ops._require_platform_admin(principal)

    assert calls["principal"] is principal


@pytest.mark.asyncio
async def test_admin_ops_org_scope_loader_uses_root_compat_shim(monkeypatch) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod
    from tldw_Server_API.app.api.v1.endpoints.admin import admin_ops

    calls: dict[str, object] = {}

    async def _fake_get_admin_org_ids(principal) -> list[int]:
        calls["principal"] = principal
        return [11, 22]

    monkeypatch.setattr(admin_mod, "_get_admin_org_ids", _fake_get_admin_org_ids)

    principal = SimpleNamespace(user_id=7)
    org_ids = await admin_ops._get_admin_org_ids(principal)

    assert org_ids == [11, 22]
    assert calls["principal"] is principal


@pytest.mark.asyncio
async def test_admin_data_ops_scope_enforcement_uses_root_compat_shim(monkeypatch) -> None:
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod
    from tldw_Server_API.app.api.v1.endpoints.admin import admin_data_ops

    calls: dict[str, object] = {}

    async def _fake_scope_check(principal, target_user_id: int, *, require_hierarchy: bool) -> None:
        calls["principal"] = principal
        calls["target_user_id"] = target_user_id
        calls["require_hierarchy"] = require_hierarchy

    monkeypatch.setattr(admin_mod, "_enforce_admin_user_scope", _fake_scope_check)

    principal = SimpleNamespace(user_id=5)
    await admin_data_ops._enforce_admin_user_scope(principal, 123, require_hierarchy=False)

    assert calls == {
        "principal": principal,
        "target_user_id": 123,
        "require_hierarchy": False,
    }
