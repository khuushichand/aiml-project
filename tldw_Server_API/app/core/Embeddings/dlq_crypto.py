"""
DLQ payload optional encryption helpers.

Uses AES-GCM if `cryptography` is available and EMBEDDINGS_DLQ_ENCRYPTION_KEY is set.
Falls back to base64 encoding when crypto is unavailable (marked alg=none).
"""

from __future__ import annotations

import base64
import json
import os
from typing import Optional, Dict, Any, Tuple

from loguru import logger


_SCRYPT_PARAMS = {
    "n": 2**14,
    "r": 8,
    "p": 1,
    "dklen": 32,
}


def _derive_key_from_passphrase_legacy(passphrase: str) -> bytes:
    import hashlib
    return hashlib.sha256(passphrase.encode("utf-8")).digest()


def _derive_key_from_passphrase(passphrase: str, salt: bytes) -> Tuple[bytes, str]:
    import hashlib
    try:
        key = hashlib.scrypt(
            passphrase.encode("utf-8"),
            salt=salt,
            n=_SCRYPT_PARAMS["n"],
            r=_SCRYPT_PARAMS["r"],
            p=_SCRYPT_PARAMS["p"],
            dklen=_SCRYPT_PARAMS["dklen"],
        )
        return key, "scrypt"
    except (ValueError, MemoryError) as exc:
        allow_weak = str(os.getenv("EMBEDDINGS_DLQ_ALLOW_WEAK_KDF", "")).lower() in {"1", "true", "yes", "on"}
        logger.warning(
            "DLQ KDF scrypt failed; weak fallback %s. error=%s",
            "enabled" if allow_weak else "disabled",
            f"{type(exc).__name__}: {exc}",
        )
        if not allow_weak:
            raise
        return _derive_key_from_passphrase_legacy(passphrase), "sha256"


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
        salt = os.urandom(16)
        key, kdf_used = _derive_key_from_passphrase(key_str, salt)
        raw = json.dumps(payload_obj, default=str).encode("utf-8")
        obj = _aesgcm_encrypt(raw, key)
        if obj.get("alg") == "AESGCM":
            obj["kdf"] = kdf_used
            if kdf_used == "scrypt":
                obj["salt"] = base64.b64encode(salt).decode("utf-8")
                obj["kdf_params"] = _SCRYPT_PARAMS
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
        kdf = obj.get("kdf")
        if kdf == "scrypt":
            salt_b64 = obj.get("salt") or ""
            salt = base64.b64decode(salt_b64)
            stored_params = obj.get("kdf_params") or {}
            if not isinstance(stored_params, dict):
                stored_params = {}
            try:
                import hashlib
                key = hashlib.scrypt(
                    key_str.encode("utf-8"),
                    salt=salt,
                    n=int(stored_params.get("n", _SCRYPT_PARAMS["n"])),
                    r=int(stored_params.get("r", _SCRYPT_PARAMS["r"])),
                    p=int(stored_params.get("p", _SCRYPT_PARAMS["p"])),
                    dklen=int(stored_params.get("dklen", _SCRYPT_PARAMS["dklen"])),
                )
            except (ValueError, MemoryError, TypeError) as exc:
                logger.debug(
                    "DLQ decrypt scrypt failed, using legacy KDF: %s",
                    type(exc).__name__,
                )
                key = _derive_key_from_passphrase_legacy(key_str)
        else:
            key = _derive_key_from_passphrase_legacy(key_str)
        raw = _aesgcm_decrypt(obj, key)
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None
