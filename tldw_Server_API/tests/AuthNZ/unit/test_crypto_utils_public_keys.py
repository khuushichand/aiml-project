import os

import pytest

from tldw_Server_API.app.core.AuthNZ.crypto_utils import (
    derive_hmac_key_candidates,
    derive_hmac_key_from_source,
)
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings


@pytest.mark.unit
def test_public_keys_excluded_when_secret_present(monkeypatch):
    # Ensure a clean settings instance
    reset_settings()
    monkeypatch.setenv("TEST_MODE", "true")

    # Configure multi-user with a real secret and a public key present
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    # Must be >=32 chars to satisfy validator
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-key-for-tests-0123456789")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "PUBLIC-KEY-DATA")
    monkeypatch.delenv("API_KEY_PEPPER", raising=False)
    monkeypatch.delenv("JWT_PRIVATE_KEY", raising=False)

    s = get_settings()
    candidates = derive_hmac_key_candidates(s)

    # Expect the secret-derived key to be present
    h_secret = derive_hmac_key_from_source("super-secret-key-for-tests-0123456789")
    assert h_secret in candidates

    # Public key material must NOT contribute to HMAC candidates
    h_public = derive_hmac_key_from_source("PUBLIC-KEY-DATA")
    assert h_public not in candidates


@pytest.mark.unit
def test_only_public_key_uses_test_fallback_in_pytest(monkeypatch):
    # Ensure clean settings
    reset_settings()
    monkeypatch.setenv("TEST_MODE", "true")

    # Only public key is set; in pytest context, fallback key should be used
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "PUBLIC-ONLY")
    # Clear secrets
    for key in ("JWT_SECRET_KEY", "JWT_PRIVATE_KEY", "API_KEY_PEPPER"):
        monkeypatch.delenv(key, raising=False)

    s = get_settings()
    candidates = derive_hmac_key_candidates(s)

    # Must not include the public key material
    h_public = derive_hmac_key_from_source("PUBLIC-ONLY")
    assert h_public not in candidates

    # Should include the deterministic test fallback in pytest context
    h_fallback = derive_hmac_key_from_source("tldw_default_api_key_hmac")
    assert candidates and h_fallback in candidates
