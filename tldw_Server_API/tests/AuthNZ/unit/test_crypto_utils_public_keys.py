import os
import hashlib

import pytest

from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings


def _derive_expected_key(raw: str) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        raw.encode("utf-8"),
        b"tldw_authnz_hmac_kdf_v1",
        100_000,
        dklen=32,
    )


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
    h_secret = _derive_expected_key("super-secret-key-for-tests-0123456789")
    assert h_secret in candidates

    # Public key material must NOT contribute to HMAC candidates
    h_public = _derive_expected_key("PUBLIC-KEY-DATA")
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
    h_public = _derive_expected_key("PUBLIC-ONLY")
    assert h_public not in candidates

    # Should include the deterministic test fallback in pytest context
    h_fallback = _derive_expected_key("tldw_default_api_key_hmac")
    assert candidates and h_fallback in candidates
