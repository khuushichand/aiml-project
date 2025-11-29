from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.types import Scope

from tldw_Server_API.app.core.AuthNZ.auth_governor import AuthGovernor
from tldw_Server_API.app.core.AuthNZ.llm_budget_guard import enforce_llm_budget
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext


def _make_request(headers: dict[str, str] | None = None) -> Request:
    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/chat/completions",
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_auth_governor_decorates_over_budget_result_with_principal(monkeypatch):
    async def _fake_is_key_over_budget(key_id: int):
        return {
            "over": True,
            "reasons": ["day_tokens_exceeded:100/10"],
            "day": {"tokens": 100, "usd": 0.5},
            "month": {"tokens": 2000, "usd": 10.0},
            "limits": {"is_virtual": True},
        }

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_governor.is_key_over_budget",
        _fake_is_key_over_budget,
    )

    principal = AuthPrincipal(
        kind="api_key",
        user_id=1,
        api_key_id=123,
        subject=None,
        token_type="api_key",
        jti=None,
        roles=[],
        permissions=[],
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )

    gov = AuthGovernor()
    result = await gov.check_llm_budget_for_api_key(principal, 123)

    assert result["over"] is True
    assert result["limits"]["is_virtual"] is True
    meta = result.get("principal") or {}
    assert meta.get("principal_id")
    assert meta.get("api_key_id") == 123
    assert meta.get("user_id") == 1


@pytest.mark.asyncio
async def test_enforce_llm_budget_uses_auth_governor_and_raises_402(monkeypatch):
    # Settings with budget enforcement enabled and virtual keys enabled
    fake_settings = SimpleNamespace(
        VIRTUAL_KEYS_ENABLED=True,
        LLM_BUDGET_ENFORCE=True,
    )

    def _fake_get_settings():
        return fake_settings

    async def _fake_resolve_api_key_by_hash(api_key: str, settings=None):
        return {"id": 123, "user_id": 7}

    async def _fake_get_auth_governor():
        class _FakeGov:
            async def check_llm_budget_for_api_key(self, principal, api_key_id: int):
                return {
                    "over": True,
                    "reasons": ["day_tokens_exceeded:100/10"],
                    "day": {"tokens": 100, "usd": 0.5},
                    "month": {"tokens": 2000, "usd": 10.0},
                    "limits": {"is_virtual": True},
                    "principal": {
                        "principal_id": principal.principal_id,
                        "kind": principal.kind,
                        "user_id": principal.user_id,
                        "api_key_id": principal.api_key_id,
                    },
                }

        return _FakeGov()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.llm_budget_guard.get_settings",
        _fake_get_settings,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.llm_budget_guard.resolve_api_key_by_hash",
        _fake_resolve_api_key_by_hash,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.llm_budget_guard.get_auth_governor",
        _fake_get_auth_governor,
    )

    req = _make_request(headers={"X-API-KEY": "vk-key"})

    # Pre-populate a minimal AuthContext so the guard can reuse it if desired
    principal = AuthPrincipal(
        kind="api_key",
        user_id=7,
        api_key_id=123,
        subject=None,
        token_type="api_key",
        jti=None,
        roles=[],
        permissions=[],
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )
    req.state.auth = AuthContext(
        principal=principal,
        ip="127.0.0.1",
        user_agent="pytest-agent",
        request_id="req-llm-budget",
    )

    with pytest.raises(HTTPException) as exc_info:
        await enforce_llm_budget(req)

    assert exc_info.value.status_code == 402
    detail = exc_info.value.detail
    assert detail.get("error") == "budget_exceeded"
    assert detail.get("details", {}).get("over") is True

