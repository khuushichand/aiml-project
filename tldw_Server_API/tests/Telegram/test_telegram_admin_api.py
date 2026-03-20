from __future__ import annotations

import base64

import pytest

from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


@pytest.fixture()
def auth_header(auth_headers):
    return auth_headers


@pytest.fixture()
def client(client_user_only, monkeypatch):
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"t"))
    monkeypatch.delenv("BYOK_SECONDARY_ENCRYPTION_KEY", raising=False)
    reset_settings()
    return client_user_only


def test_put_and_get_telegram_bot_config(client, auth_header, monkeypatch):
    payload = {
        "bot_token": ":".join(["123", "abc"]),
        "webhook_secret": "-".join(["secret", "123"]),
        "enabled": True,
    }
    put_res = client.put("/api/v1/telegram/admin/bot", json=payload, headers=auth_header)
    if put_res.status_code != 200:
        pytest.fail(f"expected 200 from PUT /api/v1/telegram/admin/bot, got {put_res.status_code}")

    get_res = client.get("/api/v1/telegram/admin/bot", headers=auth_header)
    if get_res.status_code != 200:
        pytest.fail(f"expected 200 from GET /api/v1/telegram/admin/bot, got {get_res.status_code}")
    body = get_res.json()
    if body["bot_username"] is None:
        pytest.fail("expected Telegram bot_username to be populated")
    if body["enabled"] is not True:
        pytest.fail("expected Telegram bot config to remain enabled")
