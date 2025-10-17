"""
crypto_utils.py

Shared cryptographic helpers for AuthNZ components.

Currently exposes a uniform HMAC key derivation routine to avoid drift
between JWTService, APIKeyManager, CSRF, and SessionManager.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings


def derive_hmac_key(settings: Optional[Settings] = None) -> bytes:
    """Derive a 32-byte HMAC key from configured secrets.

    Order of preference:
    - single_user: derive from SHA256(SINGLE_USER_API_KEY)
    - otherwise: API_KEY_PEPPER if set
    - otherwise: JWT_SECRET_KEY if set
    - fallback: project-safe default constant

    The returned key is SHA256(material_bytes).digest() to produce
    a uniform 32-byte key suitable for HMAC-SHA256.
    """
    s = settings or get_settings()
    # Single-user mode: derive from the API key (hashed first)
    if getattr(s, "AUTH_MODE", "single_user") == "single_user" and getattr(s, "SINGLE_USER_API_KEY", None):
        material_bytes = hashlib.sha256(s.SINGLE_USER_API_KEY.encode("utf-8")).digest()
    else:
        source = s.API_KEY_PEPPER or s.JWT_SECRET_KEY or "tldw_default_api_key_hmac"
        material_bytes = source.encode("utf-8")
    return hashlib.sha256(material_bytes).digest()


__all__ = ["derive_hmac_key"]

