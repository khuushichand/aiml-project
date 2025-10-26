"""
crypto_utils.py

Shared cryptographic helpers for AuthNZ components.

Currently exposes a uniform HMAC key derivation routine to avoid drift
between JWTService, APIKeyManager, CSRF, and SessionManager.
"""

from __future__ import annotations

import hashlib
import os
from typing import List, Optional

from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings


def _ensure_secret_bytes(secret: Optional[str]) -> Optional[bytes]:
    if secret is None:
        return None
    if isinstance(secret, bytes):
        return secret
    return str(secret).encode("utf-8")


def derive_hmac_key(settings: Optional[Settings] = None) -> bytes:
    """Derive a 32-byte HMAC key from configured secrets.

    Order of preference:
    - single_user: derive from SHA256(SINGLE_USER_API_KEY)
    - otherwise: API_KEY_PEPPER if set
    - otherwise: JWT secrets/keys (HS or RS/ES)
    - fallback: only in explicit test contexts

    The returned key is SHA256(material_bytes).digest() to produce
    a uniform 32-byte key suitable for HMAC-SHA256.
    """
    keys = derive_hmac_key_candidates(settings)
    if not keys:
        raise ValueError("derive_hmac_key_candidates returned no usable keys")
    return keys[0]


def derive_hmac_key_candidates(settings: Optional[Settings] = None) -> List[bytes]:
    """Return ordered HMAC key candidates derived from configured secrets.

    The first item represents the *current* secret material. Subsequent entries
    capture legacy/secondary secrets that should remain valid during rotations.

    Important: Public keys are intentionally excluded from HMAC/encryption key
    derivation to avoid using non-secret material as cryptographic input.
    """
    s = settings or get_settings()
    auth_mode = getattr(s, "AUTH_MODE", "single_user")

    # Detect pytest context and known deterministic JWT secret used only for testing
    test_mode_env = os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
    pytest_active = os.getenv("PYTEST_CURRENT_TEST") is not None
    in_test_context = test_mode_env or pytest_active
    test_secret_env = os.getenv("JWT_SECRET_TEST_KEY", "test-secret-jwt-key-please-change-1234567890")

    digest_sources: list[bytes] = []
    seen: set[bytes] = set()

    def add_source(raw: Optional[str], *, prehash: bool = False) -> None:
        if not raw:
            return
        data = raw if isinstance(raw, bytes) else str(raw).encode("utf-8")
        if prehash:
            data = hashlib.sha256(data).digest()
        if data in seen:
            return
        seen.add(data)
        digest_sources.append(data)

    # Single-user mode prefers the configured API key (double hashed for parity with legacy logic)
    if auth_mode == "single_user" and getattr(s, "SINGLE_USER_API_KEY", None):
        add_source(s.SINGLE_USER_API_KEY, prehash=True)
        # Allow optional pepper override afterwards
        add_source(getattr(s, "API_KEY_PEPPER", None))
    else:
        # Multi-user (or single-user without explicit key): enforce real secret material
        add_source(getattr(s, "API_KEY_PEPPER", None))
        # If only a public key is configured and the JWT secret was auto-filled by
        # the test fallback, ignore that secret and use the deterministic fallback
        # later to keep test behavior stable.
        jwt_secret_candidate = getattr(s, "JWT_SECRET_KEY", None)
        only_public_key = bool(getattr(s, "JWT_PUBLIC_KEY", None)) and not getattr(s, "JWT_PRIVATE_KEY", None)
        auto_test_secret = in_test_context and jwt_secret_candidate == test_secret_env
        if not (only_public_key and auto_test_secret):
            add_source(jwt_secret_candidate)
        add_source(getattr(s, "JWT_PRIVATE_KEY", None))

    # Secondary / legacy material to support key rotations
    add_source(getattr(s, "JWT_SECONDARY_SECRET", None))
    add_source(getattr(s, "JWT_SECONDARY_PRIVATE_KEY", None))
    # Note: secondary public keys are also excluded by design

    if not digest_sources:
        # Allow fallback only in explicit automated test scenarios to preserve fixture behaviour.
        if not in_test_context:
            raise ValueError(
                "derive_hmac_key could not locate a configured secret. "
                "Set API_KEY_PEPPER (recommended) or provide JWT_SECRET_KEY / JWT_PRIVATE_KEY."
            )
        digest_sources.append(b"tldw_default_api_key_hmac")

    # Hash each material to produce uniform 32-byte HMAC keys
    keys: list[bytes] = []
    for source in digest_sources:
        hashed = hashlib.sha256(source).digest()
        if hashed not in keys:
            keys.append(hashed)
    return keys


__all__ = ["derive_hmac_key", "derive_hmac_key_candidates"]
