"""
DLQ payload optional encryption helpers.

Uses AES-GCM if `cryptography` is available and EMBEDDINGS_DLQ_ENCRYPTION_KEY is set.
Falls back to base64 encoding when crypto is unavailable (marked alg=none).
"""

from __future__ import annotations

import base64
import json
import os
from typing import Optional, Dict, Any


def _derive_key_from_passphrase(passphrase: str) -> bytes:
    import hashlib
    return hashlib.sha256(passphrase.encode("utf-8")).digest()


def _aesgcm_encrypt(plaintext: bytes, key: bytes) -> Dict[str, str]:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    except Exception:
        # Fallback to base64-only marker
        return {"alg": "none", "b64": base64.b64encode(plaintext).decode("utf-8")}
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    return {
        "alg": "AESGCM",
        "nonce": base64.b64encode(nonce).decode("utf-8"),
        "ct": base64.b64encode(ct).decode("utf-8"),
    }


def _aesgcm_decrypt(obj: Dict[str, str], key: bytes) -> Optional[bytes]:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    except Exception:
        # Fallback: base64-only marker
        if obj.get("alg") == "none" and obj.get("b64"):
            try:
                return base64.b64decode(obj.get("b64") or "")
            except Exception:
                return None
        return None
    try:
        if obj.get("alg") != "AESGCM":
            if obj.get("alg") == "none" and obj.get("b64"):
                return base64.b64decode(obj.get("b64") or "")
            return None
        nonce = base64.b64decode(obj.get("nonce") or "")
        ct = base64.b64decode(obj.get("ct") or "")
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, associated_data=None)
    except Exception:
        return None


def encrypt_payload_if_configured(payload_obj: Dict[str, Any]) -> Optional[str]:
    """Return JSON string of encrypted blob when configured; else None.

    When EMBEDDINGS_DLQ_ENCRYPTION_KEY is set, encrypts with AES-GCM (or base64 fallback).
    """
    key_str = os.getenv("EMBEDDINGS_DLQ_ENCRYPTION_KEY")
    if not key_str:
        return None
    try:
        key = _derive_key_from_passphrase(key_str)
        raw = json.dumps(payload_obj, default=str).encode("utf-8")
        obj = _aesgcm_encrypt(raw, key)
        return json.dumps(obj)
    except Exception:
        return None


def decrypt_payload_if_present(enc_json: Optional[str]) -> Optional[Dict[str, Any]]:
    """Attempt to decrypt an encrypted payload blob; returns dict or None."""
    if not enc_json:
        return None
    try:
        obj = json.loads(enc_json)
    except Exception:
        return None
    key_str = os.getenv("EMBEDDINGS_DLQ_ENCRYPTION_KEY")
    if not key_str:
        # Without key, cannot decrypt; return None
        return None
    try:
        key = _derive_key_from_passphrase(key_str)
        raw = _aesgcm_decrypt(obj, key)
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None
