import os
import hashlib

import pytest

from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings


@pytest.mark.unit
def test_public_keys_excluded_when_secret_present(monkeypatch):
    # Ensure a clean settings instance
    reset_settings()

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
    h_secret = hashlib.sha256(b"super-secret-key-for-tests-0123456789").digest()
    assert h_secret in candidates

    # Public key material must NOT contribute to HMAC candidates
    h_public = hashlib.sha256(b"PUBLIC-KEY-DATA").digest()
    assert h_public not in candidates


@pytest.mark.unit
def test_only_public_key_uses_test_fallback_in_pytest(monkeypatch):
    # Ensure clean settings
    reset_settings()

    # Only public key is set; in pytest context, fallback key should be used
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "PUBLIC-ONLY")
    # Clear secrets
    for key in ("JWT_SECRET_KEY", "JWT_PRIVATE_KEY", "API_KEY_PEPPER"):
        monkeypatch.delenv(key, raising=False)

    s = get_settings()
    candidates = derive_hmac_key_candidates(s)

    # Must not include the public key material
    h_public = hashlib.sha256(b"PUBLIC-ONLY").digest()
    assert h_public not in candidates

    # Should include the deterministic test fallback in pytest context
    h_fallback = hashlib.sha256(b"tldw_default_api_key_hmac").digest()
    assert candidates and h_fallback in candidates
