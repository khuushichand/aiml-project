from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    build_secret_payload,
    decrypt_byok_payload,
    dumps_envelope,
    encrypt_byok_payload,
    loads_envelope,
)


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


def _encrypted_row(payload: dict) -> dict:
    envelope = encrypt_byok_payload(payload)
    return {"encrypted_blob": dumps_envelope(envelope), "last_used_at": None}


def _decrypted_payload_from_row(row: dict) -> dict:
    return decrypt_byok_payload(loads_envelope(row["encrypted_blob"]))


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


@pytest.mark.asyncio
async def test_resolve_byok_credentials_v2_oauth_active_uses_access_token(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import byok_runtime
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))
    reset_settings()

    payload = {
        "credential_version": 2,
        "active_auth_source": "oauth",
        "credentials": {
            "oauth": {"access_token": "oauth-access-token-123"},
            "api_key": {"api_key": "sk-api-fallback-123"},
        },
    }
    row = _encrypted_row(payload)

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
    assert resolved.api_key == "oauth-access-token-123"
    assert resolved.auth_source == "oauth"


@pytest.mark.asyncio
async def test_resolve_byok_credentials_v2_missing_oauth_token_falls_back_to_api_key(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import byok_runtime
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))
    reset_settings()

    payload = {
        "credential_version": 2,
        "active_auth_source": "oauth",
        "credentials": {
            "oauth": {"access_token": ""},
            "api_key": {"api_key": "sk-api-key-usable-456"},
        },
    }
    row = _encrypted_row(payload)

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
    assert resolved.api_key == "sk-api-key-usable-456"
    assert resolved.auth_source == "api_key"


@pytest.mark.asyncio
async def test_resolve_byok_credentials_v2_oauth_refresh_success_updates_payload(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import byok_runtime
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))
    monkeypatch.setenv("OPENAI_OAUTH_ENABLED", "true")
    monkeypatch.setenv("OPENAI_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("OPENAI_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OPENAI_OAUTH_TOKEN_URL", "https://oauth.example/token")
    monkeypatch.setenv("OPENAI_OAUTH_REFRESH_SKEW_SECONDS", "120")
    reset_settings()

    payload = {
        "credential_version": 2,
        "active_auth_source": "oauth",
        "credentials": {
            "oauth": {
                "access_token": "stale-access-token",
                "refresh_token": "refresh-token-123",
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(seconds=30)
                ).isoformat(),
            },
            "api_key": {"api_key": "sk-api-fallback-123"},
        },
    }
    row = _encrypted_row(payload)
    row["metadata"] = None
    row["key_hint"] = "oauth"

    class _FakeUserRepo:
        async def fetch_secret_for_user(self, user_id: int, provider: str):
            return row

        async def upsert_secret(
            self,
            *,
            user_id: int,
            provider: str,
            encrypted_blob: str,
            key_hint: str | None,
            metadata,
            updated_at: datetime,
            created_by: int | None = None,
            updated_by: int | None = None,
        ):
            row["encrypted_blob"] = encrypted_blob
            row["key_hint"] = key_hint
            row["metadata"] = metadata
            row["updated_at"] = updated_at
            return {"updated_at": updated_at}

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "inference",
            }

        async def aclose(self):
            return None

    async def _fake_get_user_repo():
        return _FakeUserRepo()

    async def _fake_afetch(*_args, **_kwargs):
        return _FakeResponse()

    monkeypatch.setattr(byok_runtime, "_get_user_repo", _fake_get_user_repo)
    monkeypatch.setattr(byok_runtime, "_http_afetch", _fake_afetch)
    monkeypatch.setattr(byok_runtime, "is_byok_enabled", lambda: True)
    monkeypatch.setattr(byok_runtime, "is_provider_allowlisted", lambda _provider: True)

    resolved = await byok_runtime.resolve_byok_credentials("openai", user_id=1)

    assert resolved.source == "user"
    assert resolved.api_key == "new-access-token"
    assert resolved.auth_source == "oauth"

    stored_payload = _decrypted_payload_from_row(row)
    assert stored_payload["active_auth_source"] == "oauth"
    assert stored_payload["credentials"]["oauth"]["access_token"] == "new-access-token"
    assert stored_payload["credentials"]["oauth"]["refresh_token"] == "new-refresh-token"


@pytest.mark.asyncio
async def test_resolve_byok_credentials_v2_oauth_refresh_failure_falls_back_to_api_key(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import byok_runtime
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))
    monkeypatch.setenv("OPENAI_OAUTH_ENABLED", "true")
    monkeypatch.setenv("OPENAI_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("OPENAI_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OPENAI_OAUTH_TOKEN_URL", "https://oauth.example/token")
    monkeypatch.setenv("OPENAI_OAUTH_REFRESH_SKEW_SECONDS", "120")
    reset_settings()

    payload = {
        "credential_version": 2,
        "active_auth_source": "oauth",
        "credentials": {
            "oauth": {
                "access_token": "expired-access-token",
                "refresh_token": "refresh-token-123",
                "expires_at": (
                    datetime.now(timezone.utc) - timedelta(seconds=10)
                ).isoformat(),
            },
            "api_key": {"api_key": "sk-api-fallback-xyz"},
        },
    }
    row = _encrypted_row(payload)
    row["metadata"] = None
    row["key_hint"] = "oauth"

    class _FakeUserRepo:
        async def fetch_secret_for_user(self, user_id: int, provider: str):
            return row

        async def upsert_secret(
            self,
            *,
            user_id: int,
            provider: str,
            encrypted_blob: str,
            key_hint: str | None,
            metadata,
            updated_at: datetime,
            created_by: int | None = None,
            updated_by: int | None = None,
        ):
            row["encrypted_blob"] = encrypted_blob
            row["key_hint"] = key_hint
            row["metadata"] = metadata
            row["updated_at"] = updated_at
            return {"updated_at": updated_at}

    class _FakeResponse:
        status_code = 400

        def json(self):
            return {"error": "invalid_grant"}

        async def aclose(self):
            return None

    async def _fake_get_user_repo():
        return _FakeUserRepo()

    async def _fake_afetch(*_args, **_kwargs):
        return _FakeResponse()

    monkeypatch.setattr(byok_runtime, "_get_user_repo", _fake_get_user_repo)
    monkeypatch.setattr(byok_runtime, "_http_afetch", _fake_afetch)
    monkeypatch.setattr(byok_runtime, "is_byok_enabled", lambda: True)
    monkeypatch.setattr(byok_runtime, "is_provider_allowlisted", lambda _provider: True)

    resolved = await byok_runtime.resolve_byok_credentials("openai", user_id=1)

    assert resolved.source == "user"
    assert resolved.api_key == "sk-api-fallback-xyz"
    assert resolved.auth_source == "api_key"

    stored_payload = _decrypted_payload_from_row(row)
    assert stored_payload["active_auth_source"] == "api_key"
    assert stored_payload["credentials"]["api_key"]["api_key"] == "sk-api-fallback-xyz"


@pytest.mark.asyncio
async def test_resolve_byok_credentials_v2_oauth_refresh_failure_without_api_key_fails_closed(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import byok_runtime
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))
    monkeypatch.setenv("OPENAI_OAUTH_ENABLED", "true")
    monkeypatch.setenv("OPENAI_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("OPENAI_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OPENAI_OAUTH_TOKEN_URL", "https://oauth.example/token")
    monkeypatch.setenv("OPENAI_OAUTH_REFRESH_SKEW_SECONDS", "120")
    reset_settings()

    payload = {
        "credential_version": 2,
        "active_auth_source": "oauth",
        "credentials": {
            "oauth": {
                "access_token": "expired-access-token",
                "refresh_token": "refresh-token-123",
                "expires_at": (
                    datetime.now(timezone.utc) - timedelta(seconds=10)
                ).isoformat(),
            },
        },
    }
    row = _encrypted_row(payload)
    row["metadata"] = None
    row["key_hint"] = "oauth"

    class _FakeUserRepo:
        async def fetch_secret_for_user(self, user_id: int, provider: str):
            return row

    class _FakeResponse:
        status_code = 400

        def json(self):
            return {"error": "invalid_grant"}

        async def aclose(self):
            return None

    async def _fake_get_user_repo():
        return _FakeUserRepo()

    async def _fake_afetch(*_args, **_kwargs):
        return _FakeResponse()

    monkeypatch.setattr(byok_runtime, "_get_user_repo", _fake_get_user_repo)
    monkeypatch.setattr(byok_runtime, "_http_afetch", _fake_afetch)
    monkeypatch.setattr(byok_runtime, "is_byok_enabled", lambda: True)
    monkeypatch.setattr(byok_runtime, "is_provider_allowlisted", lambda _provider: True)

    resolved = await byok_runtime.resolve_byok_credentials("openai", user_id=1)

    assert resolved.source == "user"
    assert resolved.api_key is None
    assert resolved.auth_source is None
