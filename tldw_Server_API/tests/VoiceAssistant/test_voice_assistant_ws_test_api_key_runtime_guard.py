from __future__ import annotations

from types import SimpleNamespace

import pytest

import tldw_Server_API.app.api.v1.endpoints.voice_assistant as voice_assistant
import tldw_Server_API.app.core.AuthNZ.ip_allowlist as ip_allowlist
import tldw_Server_API.app.core.AuthNZ.settings as auth_settings


class _WS:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.client = SimpleNamespace(host="127.0.0.1")


class _Settings:
    AUTH_MODE = "single_user"
    SINGLE_USER_API_KEY = "primary-live-key"
    SINGLE_USER_FIXED_ID = 99


@pytest.mark.asyncio
async def test_voice_assistant_ws_rejects_test_api_key_without_explicit_pytest_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("SINGLE_USER_TEST_API_KEY", "test-voice-api-key-123456")
    monkeypatch.setattr(auth_settings, "get_settings", lambda: _Settings(), raising=True)
    monkeypatch.setattr(ip_allowlist, "resolve_client_ip", lambda _ws, _settings: "127.0.0.1", raising=True)
    monkeypatch.setattr(ip_allowlist, "is_single_user_ip_allowed", lambda _ip, _settings: True, raising=True)

    authenticated, user_id = await voice_assistant._authenticate_websocket(
        _WS(),
        token="test-voice-api-key-123456",
    )

    assert authenticated is False
    assert user_id is None


@pytest.mark.asyncio
async def test_voice_assistant_ws_accepts_test_api_key_in_explicit_pytest_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "voice::ws_auth")
    monkeypatch.setenv("SINGLE_USER_TEST_API_KEY", "test-voice-api-key-123456")
    monkeypatch.setattr(auth_settings, "get_settings", lambda: _Settings(), raising=True)
    monkeypatch.setattr(ip_allowlist, "resolve_client_ip", lambda _ws, _settings: "127.0.0.1", raising=True)
    monkeypatch.setattr(ip_allowlist, "is_single_user_ip_allowed", lambda _ip, _settings: True, raising=True)

    authenticated, user_id = await voice_assistant._authenticate_websocket(
        _WS(),
        token="test-voice-api-key-123456",
    )

    assert authenticated is True
    assert user_id == 99
