from __future__ import annotations

import json
from typing import Any

import pytest

from tldw_Server_API.app.api.v1.schemas.org_team_schemas import OrganizationWatchlistsSettingsUpdate
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_orgs_service


class _CursorStub:
    def __init__(self, *, row: Any = None) -> None:
        self._row = row

    async def fetchone(self) -> Any:
        return self._row


class _SQLiteTxConnWithFetchrowTrap:
    def __init__(self, *, metadata_json: str | None) -> None:
        self._is_sqlite = True
        self.metadata_json = metadata_json
        self.execute_calls: list[tuple[str, Any]] = []
        self.fetchrow_called = False

    async def fetchrow(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - should never run
        self.fetchrow_called = True
        raise AssertionError("sqlite path should not use fetchrow()")

    async def execute(self, query: str, params: Any) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        q = str(query).lower()
        if "select metadata from organizations" in q:
            return _CursorStub(row=(self.metadata_json,))
        if "update organizations set metadata" in q:
            return _CursorStub(row=None)
        raise AssertionError(f"Unexpected query: {query!r}")


class _PostgresTxConnWithSqliteTrap:
    def __init__(self, *, metadata_json: str | None) -> None:
        self._is_sqlite = False
        self.metadata_json = metadata_json
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, Any]] = []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls.append((str(query), tuple(args)))
        q = str(query).lower()
        if "select metadata from organizations" in q:
            return {"metadata": self.metadata_json}
        return None

    async def execute(self, query: str, *args: Any) -> Any:
        self.execute_calls.append((str(query), args))
        if "?" in str(query):
            raise AssertionError("postgres path should not use sqlite placeholders")
        return "OK"


def _admin_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        roles=["admin"],
        permissions=[],
        is_admin=True,
        org_ids=[],
        team_ids=[],
    )


@pytest.mark.asyncio
async def test_update_org_watchlists_settings_sqlite_path_ignores_fetchrow_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allow_org_access(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(admin_orgs_service.admin_scope_service, "enforce_admin_org_access", _allow_org_access)

    db = _SQLiteTxConnWithFetchrowTrap(metadata_json="{}")
    payload = OrganizationWatchlistsSettingsUpdate(require_include_default=True)

    response = await admin_orgs_service.update_org_watchlists_settings(
        org_id=55,
        payload=payload,
        principal=_admin_principal(),
        db=db,
    )

    assert response.org_id == 55
    assert response.require_include_default is True
    assert db.fetchrow_called is False
    assert any("select metadata from organizations" in q.lower() for q, _ in db.execute_calls)
    update_calls = [call for call in db.execute_calls if "update organizations set metadata" in call[0].lower()]
    assert update_calls, "sqlite update path should use execute()"
    persisted_json = update_calls[0][1][0]
    persisted_meta = json.loads(persisted_json)
    assert persisted_meta["watchlists"]["require_include_default"] is True


@pytest.mark.asyncio
async def test_get_org_watchlists_settings_sqlite_path_ignores_fetchrow_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allow_org_access(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(admin_orgs_service.admin_scope_service, "enforce_admin_org_access", _allow_org_access)

    db = _SQLiteTxConnWithFetchrowTrap(
        metadata_json=json.dumps({"watchlists": {"require_include_default": True}})
    )

    response = await admin_orgs_service.get_org_watchlists_settings(
        org_id=99,
        principal=_admin_principal(),
        db=db,
    )

    assert response.org_id == 99
    assert response.require_include_default is True
    assert db.fetchrow_called is False
    assert db.execute_calls and "select metadata from organizations" in db.execute_calls[0][0].lower()


@pytest.mark.asyncio
async def test_update_org_watchlists_settings_postgres_path_uses_fetchrow_and_pg_placeholders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allow_org_access(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(admin_orgs_service.admin_scope_service, "enforce_admin_org_access", _allow_org_access)

    db = _PostgresTxConnWithSqliteTrap(metadata_json="{}")
    payload = OrganizationWatchlistsSettingsUpdate(require_include_default=True)

    response = await admin_orgs_service.update_org_watchlists_settings(
        org_id=77,
        payload=payload,
        principal=_admin_principal(),
        db=db,
    )

    assert response.org_id == 77
    assert response.require_include_default is True
    assert db.fetchrow_calls and "$1" in db.fetchrow_calls[0][0]
    assert db.execute_calls and "$1" in db.execute_calls[0][0]
    assert all("?" not in q for q, _ in db.fetchrow_calls)


@pytest.mark.asyncio
async def test_get_org_watchlists_settings_postgres_path_uses_fetchrow_and_pg_placeholders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allow_org_access(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(admin_orgs_service.admin_scope_service, "enforce_admin_org_access", _allow_org_access)

    db = _PostgresTxConnWithSqliteTrap(
        metadata_json=json.dumps({"watchlists": {"require_include_default": True}})
    )

    response = await admin_orgs_service.get_org_watchlists_settings(
        org_id=88,
        principal=_admin_principal(),
        db=db,
    )

    assert response.org_id == 88
    assert response.require_include_default is True
    assert db.fetchrow_calls and "$1" in db.fetchrow_calls[0][0]
    assert not db.execute_calls
