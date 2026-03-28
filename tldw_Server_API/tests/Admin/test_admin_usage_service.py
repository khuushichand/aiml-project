from __future__ import annotations

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_scope_service
from tldw_Server_API.app.services.admin_usage_service import get_cost_attribution


pytestmark = pytest.mark.unit


class _FailingUsageCursor:
    async def fetchall(self) -> list[dict]:
        raise AssertionError("fetchall should not be reached after execute failure")


class _FailingUsageDb:
    _is_sqlite = True

    async def execute(self, _query: str) -> _FailingUsageCursor:
        raise RuntimeError("llm_usage_v2 missing")


class _UsageCursorStub:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = list(rows)

    async def fetchall(self) -> list[dict[str, object]]:
        return list(self._rows)


class _ScopedSqliteUsageDb:
    _is_sqlite = True

    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, params: tuple[object, ...]) -> _UsageCursorStub:
        self.execute_calls.append((str(query), params))
        return _UsageCursorStub(
            [
                {
                    "entity_id": 42,
                    "request_count": 3,
                    "total_tokens": 1000,
                    "prompt_tokens": 400,
                    "completion_tokens": 600,
                }
            ]
        )


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
async def test_get_cost_attribution_surfaces_backend_failures() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_cost_attribution(
            principal=_admin_principal(),
            db=_FailingUsageDb(),
            group_by="user",
            range_days=7,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Cost attribution is currently unavailable"


@pytest.mark.asyncio
async def test_get_cost_attribution_sqlite_restricts_results_to_admin_org_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _ScopedSqliteUsageDb()

    async def _fake_get_admin_org_ids(_principal: AuthPrincipal) -> list[int] | None:
        return [42]

    monkeypatch.setattr(admin_scope_service, "get_admin_org_ids", _fake_get_admin_org_ids)

    result = await get_cost_attribution(
        principal=_admin_principal(),
        db=db,
        group_by="org",
        range_days=7,
    )

    assert result["items"][0]["entity_id"] == 42
    assert len(db.execute_calls) == 1
    query, params = db.execute_calls[0]
    assert "org_id IN (?)" in query
    assert params == ("-7 days", 42)


@pytest.mark.asyncio
async def test_get_cost_attribution_returns_empty_items_when_admin_scope_has_no_org_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _ScopedSqliteUsageDb()

    async def _fake_get_admin_org_ids(_principal: AuthPrincipal) -> list[int] | None:
        return []

    monkeypatch.setattr(admin_scope_service, "get_admin_org_ids", _fake_get_admin_org_ids)

    result = await get_cost_attribution(
        principal=_admin_principal(),
        db=db,
        group_by="user",
        range_days=7,
    )

    assert result == {"group_by": "user", "range_days": 7, "items": []}
    assert db.execute_calls == []
