from __future__ import annotations

import base64

import pytest

from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    build_secret_payload,
    dumps_envelope,
    encrypt_byok_payload,
)


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


@pytest.mark.asyncio
async def test_resolve_byok_credentials_invalid_fields_returns_invalid(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import byok_runtime
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))
    reset_settings()

    payload = build_secret_payload("sk-test", credential_fields={"bad_field": "nope"})
    envelope = encrypt_byok_payload(payload)
    row = {"encrypted_blob": dumps_envelope(envelope), "last_used_at": None}

    class _FakeUserRepo:
        async def fetch_secret_for_user(self, user_id: int, provider: str):
            return row

    async def _fake_get_user_repo():
        return _FakeUserRepo()

    monkeypatch.setattr(byok_runtime, "_get_user_repo", _fake_get_user_repo)
    monkeypatch.setattr(byok_runtime, "is_byok_enabled", lambda: True)
    monkeypatch.setattr(byok_runtime, "is_provider_allowlisted", lambda _provider: True)

    resolved = await byok_runtime.resolve_byok_credentials("openai", user_id=1)

    assert resolved.source == "user"
    assert resolved.api_key is None
    assert resolved.credential_fields == {}
