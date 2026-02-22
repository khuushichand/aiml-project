from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import tldw_Server_API.app.api.v1.endpoints.sandbox as sandbox_ep

pytestmark = pytest.mark.sandbox_ws_auth


class _WS:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.client = SimpleNamespace(host="127.0.0.1")


class _Settings:
    AUTH_MODE = "single_user"
    SINGLE_USER_API_KEY = "primary-live-key"
    SINGLE_USER_FIXED_ID = 42


@pytest.mark.asyncio
async def test_sandbox_ws_rejects_test_api_key_without_explicit_pytest_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sandbox_ep, "is_explicit_pytest_runtime", lambda: False)
    monkeypatch.setenv("SINGLE_USER_TEST_API_KEY", "test-sandbox-api-key-123456")
    monkeypatch.setattr(sandbox_ep, "get_settings", lambda: _Settings())
    monkeypatch.setattr(sandbox_ep, "resolve_client_ip", lambda _ws, _settings: "127.0.0.1")
    monkeypatch.setattr(sandbox_ep, "is_single_user_ip_allowed", lambda _ip, _settings: True)

    with pytest.raises(HTTPException) as exc_info:
        await sandbox_ep._resolve_sandbox_ws_user_id(
            _WS(),
            token=None,
            api_key="test-sandbox-api-key-123456",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid_api_key"


@pytest.mark.asyncio
async def test_sandbox_ws_accepts_test_api_key_in_explicit_pytest_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sandbox_ep, "is_explicit_pytest_runtime", lambda: True)
    monkeypatch.setenv("SINGLE_USER_TEST_API_KEY", "test-sandbox-api-key-123456")
    monkeypatch.setattr(sandbox_ep, "get_settings", lambda: _Settings())
    monkeypatch.setattr(sandbox_ep, "resolve_client_ip", lambda _ws, _settings: "127.0.0.1")
    monkeypatch.setattr(sandbox_ep, "is_single_user_ip_allowed", lambda _ip, _settings: True)

    user_id = await sandbox_ep._resolve_sandbox_ws_user_id(
        _WS(),
        token=None,
        api_key="test-sandbox-api-key-123456",
    )

    assert user_id == 42
