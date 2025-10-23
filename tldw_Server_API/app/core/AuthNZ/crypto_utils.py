"""
crypto_utils.py

Shared cryptographic helpers for AuthNZ components.

Currently exposes a uniform HMAC key derivation routine to avoid drift
between JWTService, APIKeyManager, CSRF, and SessionManager.
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional

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
    s = settings or get_settings()
    auth_mode = getattr(s, "AUTH_MODE", "single_user")

    # Single-user mode: derive from the API key (hashed first)
    if auth_mode == "single_user" and getattr(s, "SINGLE_USER_API_KEY", None):
        material_bytes = hashlib.sha256(s.SINGLE_USER_API_KEY.encode("utf-8")).digest()
        return hashlib.sha256(material_bytes).digest()

    # Multi-user (or single-user without explicit key): enforce a real secret
    candidate_sources = (
        getattr(s, "API_KEY_PEPPER", None),
        getattr(s, "JWT_SECRET_KEY", None),
        getattr(s, "JWT_PRIVATE_KEY", None),
    )
    material_bytes: Optional[bytes] = None
    for candidate in candidate_sources:
        material_bytes = _ensure_secret_bytes(candidate)
        if material_bytes:
            break

    if not material_bytes:
        # Allow fallback only in explicit automated test scenarios to preserve fixture behaviour.
        test_mode = os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
        pytest_active = os.getenv("PYTEST_CURRENT_TEST") is not None
        if not (test_mode or pytest_active):
            raise ValueError(
                "derive_hmac_key could not locate a configured secret. "
                "Set API_KEY_PEPPER (recommended) or provide JWT_SECRET_KEY / JWT_PRIVATE_KEY."
            )
        material_bytes = b"tldw_default_api_key_hmac"

    return hashlib.sha256(material_bytes).digest()


__all__ = ["derive_hmac_key"]
