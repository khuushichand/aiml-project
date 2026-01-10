from __future__ import annotations

import base64


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


def test_byok_encrypt_decrypt_roundtrip(monkeypatch) -> None:


     from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
        encrypt_byok_payload,
        decrypt_byok_payload,
    )

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"a"))
    monkeypatch.delenv("BYOK_SECONDARY_ENCRYPTION_KEY", raising=False)
    reset_settings()

    payload = {"api_key": "sk-test", "credential_fields": {"org_id": "org-1"}}
    envelope = encrypt_byok_payload(payload)
    assert decrypt_byok_payload(envelope) == payload


def test_byok_decrypt_with_secondary_key(monkeypatch) -> None:


     from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
        encrypt_byok_payload,
        decrypt_byok_payload,
    )

    primary_key = _b64_key(b"p")
    secondary_key = _b64_key(b"s")

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", secondary_key)
    monkeypatch.delenv("BYOK_SECONDARY_ENCRYPTION_KEY", raising=False)
    reset_settings()

    payload = {"api_key": "sk-test", "credential_fields": {"org_id": "org-2"}}
    envelope = encrypt_byok_payload(payload)

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", primary_key)
    monkeypatch.setenv("BYOK_SECONDARY_ENCRYPTION_KEY", secondary_key)
    reset_settings()

    assert decrypt_byok_payload(envelope) == payload
