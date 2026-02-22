from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import tldw_Server_API.app.api.v1.endpoints.watchlists as watchlists_ep


class _WS:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.client = SimpleNamespace(host="127.0.0.1")


class _Settings:
    AUTH_MODE = "single_user"
    SINGLE_USER_API_KEY = "primary-live-key"
    SINGLE_USER_FIXED_ID = 77


@pytest.mark.asyncio
async def test_watchlists_ws_rejects_test_api_key_without_explicit_pytest_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("SINGLE_USER_TEST_API_KEY", "test-watchlists-api-key-123456")
    monkeypatch.setattr(watchlists_ep, "get_settings", lambda: _Settings())
    monkeypatch.setattr(watchlists_ep, "resolve_client_ip", lambda _ws, _settings: "127.0.0.1")
    monkeypatch.setattr(watchlists_ep, "is_single_user_ip_allowed", lambda _ip, _settings: True)

    with pytest.raises(HTTPException) as exc_info:
        await watchlists_ep._resolve_watchlists_ws_user_id(
            _WS(),
            token=None,
            api_key="test-watchlists-api-key-123456",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid_api_key"


@pytest.mark.asyncio
async def test_watchlists_ws_accepts_test_api_key_in_explicit_pytest_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "watchlists::ws_auth")
    monkeypatch.setenv("SINGLE_USER_TEST_API_KEY", "test-watchlists-api-key-123456")
    monkeypatch.setattr(watchlists_ep, "get_settings", lambda: _Settings())
    monkeypatch.setattr(watchlists_ep, "resolve_client_ip", lambda _ws, _settings: "127.0.0.1")
    monkeypatch.setattr(watchlists_ep, "is_single_user_ip_allowed", lambda _ip, _settings: True)

    user_id = await watchlists_ep._resolve_watchlists_ws_user_id(
        _WS(),
        token=None,
        api_key="test-watchlists-api-key-123456",
    )

    assert user_id == 77
