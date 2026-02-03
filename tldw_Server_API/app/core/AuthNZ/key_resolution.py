from __future__ import annotations

import hashlib
import hmac
import os

#
from typing import Any

#
# Third-Party-Libs
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.api_key_crypto import (
    is_kdf_hash,
    parse_api_key,
    verify_kdf_hash,
)
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo

#
# Local Imports
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


def _compute_legacy_hmac_digests(api_key: str, key_materials: list[bytes]) -> list[str]:
    """
    Compute legacy HMAC-SHA256 digests for an API key using the provided key materials.

    IMPORTANT: This helper is **deprecated** and exists solely for backward compatibility
    with historical `api_keys.key_hash` values that were stored as HMAC-SHA256 digests,
    prior to the introduction of the PBKDF2-based KDF scheme.

    - It MUST NOT be used for hashing new API keys, passwords, or other credentials.
    - All new keys MUST be stored and verified using `kdf_hash_api_key` and
      `verify_kdf_hash`, which use a computationally expensive KDF.

    The implementation MUST remain byte-for-byte compatible with the historical
    HMAC-SHA256 digests so that existing database rows continue to verify correctly.
    """
    digests: list[str] = []
    for key in key_materials:
        try:
            digest = hmac.new(key, api_key.encode("utf-8"), hashlib.sha256).hexdigest()
            if digest not in digests:
                digests.append(digest)
        except Exception as exc:
            logger.debug("resolve_api_key_by_hash: legacy HMAC derive failed: {}", exc)
    return digests


async def resolve_api_key_by_hash(api_key: str, *, settings=None) -> dict[str, Any] | None:
    """
    Resolve an API key to its database identity via key_id or legacy HMAC lookup.

    Attempts key-id parsing and KDF verification first. If no key-id is present,
    computes ordered HMAC-SHA256 digests using current and legacy HMAC key
    materials (derive_hmac_key_candidates) and performs a dialect-aware query
    against the `api_keys.key_hash` column. When a key-id is present but no row
    is found, this returns None without falling back to a full-table HMAC scan.

    Parameters:
        api_key: The raw API key string provided by the client.
        settings: Optional settings object; falls back to get_settings() when None.

    Returns:
        dict with keys `id` and `user_id` if a match is found; otherwise None.
    """
    if not api_key:
        return None

    s = settings or get_settings()
    pool = await get_db_pool()
    repo = AuthnzApiKeysRepo(pool)
    key_id_info = parse_api_key(api_key)
    if key_id_info:
        key_identifier, _secret = key_id_info
        try:
            row = await repo.fetch_active_by_key_id(key_identifier)
        except Exception as e:
            logger.warning("resolve_api_key_by_hash: key_id lookup failed: {}", e)
            raise

        if not row:
            # Key-id present but no row: do not fall back to full-table HMAC scan.
            return None

        stored_hash = row.get("key_hash")
        if stored_hash and is_kdf_hash(stored_hash):
            if not verify_kdf_hash(api_key, stored_hash):
                return None
            return {"id": row.get("id"), "user_id": row.get("user_id")}

        # Legacy hash stored with key_id: verify directly against HMAC candidates.
        try:
            key_materials = tuple(derive_hmac_key_candidates(s))
        except Exception as e:
            logger.warning(
                "resolve_api_key_by_hash: failed to derive HMAC materials; legacy lookup disabled: {}",
                e,
            )
            key_materials = ()

        digests = _compute_legacy_hmac_digests(api_key, list(key_materials))
        if stored_hash and stored_hash in digests:
            return {"id": row.get("id"), "user_id": row.get("user_id")}
        return None

    try:
        key_materials = tuple(derive_hmac_key_candidates(s))
        if os.getenv("BUDGET_MW_DEBUG", "").lower() in {"1", "true", "yes", "on"} or os.getenv("PYTEST_CURRENT_TEST"):
            try:
                logger.debug(f"resolve_api_key_by_hash: key_materials={len(key_materials)}")
            except Exception as _dbg_exc:
                logger.trace(f"resolve_api_key_by_hash: debug logging failed: {_dbg_exc}")
    except Exception as e:
        logger.warning(
            "resolve_api_key_by_hash: failed to derive HMAC materials; legacy lookup disabled: {}",
            e,
        )
        key_materials = ()

    # Important: mirror APIKeyManager.hash_candidates (HMAC-SHA256 with secret key)
    digests = _compute_legacy_hmac_digests(api_key, list(key_materials))

    if not digests:
        return None

    # Dialect-aware query (aligns with APIKeyManager.validate_api_key)
    try:
        row = await repo.fetch_active_by_hash_candidates(digests)
    except Exception as e:
        # Log at WARNING level to make database errors visible
        # Re-raise so callers can distinguish "not found" from "error"
        logger.warning("resolve_api_key_by_hash: DB lookup failed: {}", e)
        raise

    if not row:
        return None

    return {"id": row.get("id"), "user_id": row.get("user_id")}
