from __future__ import annotations

"""
Lightweight AES-GCM helpers for field-level encryption of JSON blobs.

Uses PyCryptodome (pycryptodomex) which is already a dependency of this project.

Env:
  - WORKFLOWS_ARTIFACT_ENC_KEY: base64-encoded 32-byte key (AES-256)
"""

import base64
import hashlib
import json
import os
from typing import Any, Dict, Optional

try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Random import get_random_bytes
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


def _get_key_from_env() -> Optional[bytes]:
    key_b64 = os.getenv("WORKFLOWS_ARTIFACT_ENC_KEY", "").strip()
    if not key_b64:
        return None
    # Try strict base64 decode first
    raw: Optional[bytes]
    try:
        raw = base64.b64decode(key_b64)
    except Exception:
        raw = None
    # If base64 failed, derive from the literal string
    if raw is None or len(raw) == 0:
        # Treat provided env var as passphrase; derive a 32-byte key deterministically
        return hashlib.sha256(key_b64.encode("utf-8")).digest()
    # Accept standard AES key sizes directly; otherwise derive via SHA-256
    if len(raw) in (16, 24, 32):
        return raw
    return hashlib.sha256(raw).digest()


def _get_secondary_key_from_env() -> Optional[bytes]:
    """Optional fallback key for dual-read stage during key rotation."""
    key_b64 = os.getenv("JOBS_CRYPTO_SECONDARY_KEY", "").strip()
    if not key_b64:
        return None
    try:
        raw = base64.b64decode(key_b64)
    except Exception:
        raw = None
    if raw is None or len(raw) == 0:
        return hashlib.sha256(key_b64.encode("utf-8")).digest()
    if len(raw) in (16, 24, 32):
        return raw
    return hashlib.sha256(raw).digest()


def encrypt_json_blob(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Encrypt a JSON-serializable dict and return an envelope, or None if disabled/unsupported."""
    if not _HAS_CRYPTO:
        return None
    key = _get_key_from_env()
    if not key:
        return None
    try:
        pt = json.dumps(data, default=str).encode("utf-8")
        nonce = get_random_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ct, tag = cipher.encrypt_and_digest(pt)
        return {
            "_enc": "aesgcm:v1",
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ct": base64.b64encode(ct).decode("ascii"),
            "tag": base64.b64encode(tag).decode("ascii"),
        }
    except Exception:
        return None


def decrypt_json_blob(envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Attempt to decrypt an envelope back to dict; returns None on failure."""
    if not _HAS_CRYPTO:
        return None
    if not isinstance(envelope, dict) or envelope.get("_enc") != "aesgcm:v1":
        return None
    primary = _get_key_from_env()
    secondary = _get_secondary_key_from_env()
    if not primary and not secondary:
        return None
    nonce_b = base64.b64decode(envelope.get("nonce", ""))
    ct_b = base64.b64decode(envelope.get("ct", ""))
    tag_b = base64.b64decode(envelope.get("tag", ""))
    # Try primary key first
    for key in (primary, secondary):
        if not key:
            continue
        try:
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce_b)
            pt = cipher.decrypt_and_verify(ct_b, tag_b)
            return json.loads(pt.decode("utf-8"))
        except Exception:
            continue
    return None


def _decode_key_b64(key_b64: str) -> Optional[bytes]:
    try:
        raw = base64.b64decode(key_b64)
    except Exception:
        raw = None
    if raw is None or len(raw) == 0:
        # Derive from literal if not valid base64
        return hashlib.sha256(key_b64.encode("utf-8")).digest()
    if len(raw) in (16, 24, 32):
        return raw
    # For non-standard lengths, derive a 32-byte AES key deterministically
    return hashlib.sha256(raw).digest()


def encrypt_json_blob_with_key(data: Dict[str, Any], key_b64: str) -> Optional[Dict[str, Any]]:
    """Encrypt using an explicit base64-encoded key (AES-GCM)."""
    if not _HAS_CRYPTO:
        return None
    key = _decode_key_b64(key_b64)
    if not key:
        return None
    try:
        pt = json.dumps(data, default=str).encode("utf-8")
        nonce = get_random_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ct, tag = cipher.encrypt_and_digest(pt)
        return {
            "_enc": "aesgcm:v1",
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ct": base64.b64encode(ct).decode("ascii"),
            "tag": base64.b64encode(tag).decode("ascii"),
        }
    except Exception:
        return None


def decrypt_json_blob_with_key(envelope: Dict[str, Any], key_b64: str) -> Optional[Dict[str, Any]]:
    """Decrypt using an explicit base64-encoded key; returns dict or None."""
    if not _HAS_CRYPTO:
        return None
    if not isinstance(envelope, dict) or envelope.get("_enc") != "aesgcm:v1":
        return None
    key = _decode_key_b64(key_b64)
    if not key:
        return None
    try:
        nonce = base64.b64decode(envelope.get("nonce", ""))
        ct = base64.b64decode(envelope.get("ct", ""))
        tag = base64.b64decode(envelope.get("tag", ""))
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        pt = cipher.decrypt_and_verify(ct, tag)
        return json.loads(pt.decode("utf-8"))
    except Exception:
        return None
