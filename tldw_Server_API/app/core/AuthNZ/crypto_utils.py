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
    """
    s = settings or get_settings()
    auth_mode = getattr(s, "AUTH_MODE", "single_user")

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
        add_source(getattr(s, "JWT_SECRET_KEY", None))
        add_source(getattr(s, "JWT_PRIVATE_KEY", None))
        add_source(getattr(s, "JWT_PUBLIC_KEY", None))

    # Secondary / legacy material to support key rotations
    add_source(getattr(s, "JWT_SECONDARY_SECRET", None))
    add_source(getattr(s, "JWT_SECONDARY_PRIVATE_KEY", None))
    add_source(getattr(s, "JWT_SECONDARY_PUBLIC_KEY", None))

    if not digest_sources:
        # Allow fallback only in explicit automated test scenarios to preserve fixture behaviour.
        test_mode = os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
        pytest_active = os.getenv("PYTEST_CURRENT_TEST") is not None
        if not (test_mode or pytest_active):
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
