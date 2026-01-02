from __future__ import annotations
#
from typing import Optional, Dict, Any, List
import os
#
# Third-Party-Libs
from loguru import logger
import hmac
import hashlib

#
# Local Imports
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.api_key_crypto import (
    is_kdf_hash,
    parse_api_key,
    verify_kdf_hash,
)


async def resolve_api_key_by_hash(api_key: str, *, settings=None) -> Optional[Dict[str, Any]]:
    """
    Resolve an API key to its database identity via key_id or legacy HMAC lookup.

    Attempts key-id parsing and KDF verification first. If unavailable or no
    match is found, computes ordered HMAC-SHA256 digests using current and
    legacy HMAC key materials (derive_hmac_key_candidates) and performs a
    dialect-aware query against the `api_keys.key_hash` column.

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
    key_id_info = parse_api_key(api_key)
    if key_id_info:
        key_identifier, _secret = key_id_info
        try:
            if getattr(pool, "pool", None) is not None:
                row = await pool.fetchone(
                    """
                    SELECT id, user_id, key_hash
                    FROM api_keys
                    WHERE key_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    key_identifier,
                    "active",
                )
            else:
                row = await pool.fetchone(
                    """
                    SELECT id, user_id, key_hash
                    FROM api_keys
                    WHERE key_id = ? AND status = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (key_identifier, "active"),
                )
        except Exception as e:
            logger.warning("resolve_api_key_by_hash: key_id lookup failed: {}", e)
            raise

        if not row:
            return None

        stored_hash = row.get("key_hash") if isinstance(row, dict) else row[2]
        if stored_hash and is_kdf_hash(stored_hash):
            if not verify_kdf_hash(api_key, stored_hash):
                return None
            if isinstance(row, dict):
                return {"id": row.get("id"), "user_id": row.get("user_id")}
            return {"id": row[0], "user_id": row[1]}

        # Legacy hash stored with key_id: verify directly against HMAC candidates.
        digests: List[str] = []
        try:
            key_materials = tuple(derive_hmac_key_candidates(s))
        except Exception as e:
            logger.debug("resolve_api_key_by_hash: failed to derive HMAC materials: {}", e)
            key_materials = ()

        for key in key_materials:
            try:
                d = hmac.new(key, api_key.encode("utf-8"), hashlib.sha256).hexdigest()
                if d not in digests:
                    digests.append(d)
            except Exception as _e:
                logger.debug("resolve_api_key_by_hash: HMAC derive failed: {}", _e)

        if stored_hash and stored_hash in digests:
            if isinstance(row, dict):
                return {"id": row.get("id"), "user_id": row.get("user_id")}
            return {"id": row[0], "user_id": row[1]}
        return None

    digests: List[str] = []
    try:
        key_materials = tuple(derive_hmac_key_candidates(s))
        if os.getenv("BUDGET_MW_DEBUG", "").lower() in {"1", "true", "yes", "on"} or os.getenv("PYTEST_CURRENT_TEST"):
            try:
                logger.debug(f"resolve_api_key_by_hash: key_materials={len(key_materials)}")
            except Exception as _dbg_exc:
                logger.trace(f"resolve_api_key_by_hash: debug logging failed: {_dbg_exc}")
    except Exception as e:
        logger.debug("resolve_api_key_by_hash: failed to derive HMAC materials: {}", e)
        key_materials = ()

    # Important: mirror APIKeyManager.hash_candidates (HMAC-SHA256 with secret key)
    for key in key_materials:
        try:
            d = hmac.new(key, api_key.encode("utf-8"), hashlib.sha256).hexdigest()
            if d not in digests:
                digests.append(d)
        except Exception as _e:
            logger.debug("resolve_api_key_by_hash: HMAC derive failed: {}", _e)

    if not digests:
        return None

    # Dialect-aware query (aligns with APIKeyManager.validate_api_key)
    try:
        if getattr(pool, 'pool', None) is not None:
            # PostgreSQL
            row = await pool.fetchone(
                """
                SELECT id, user_id
                FROM api_keys
                WHERE key_hash = ANY($1::text[]) AND status = $2
                ORDER BY created_at DESC
                LIMIT 1
                """,
                digests,
                "active",
            )
        else:
            # SQLite - uses parameterized query with ? placeholders
            # Note: f-string is safe here because we only interpolate the placeholder count,
            # not any user data. The actual values are passed as the second argument to fetchone().
            num_placeholders = len(digests)
            placeholders = ",".join(["?"] * num_placeholders)
            query = (
                f"SELECT id, user_id FROM api_keys "
                f"WHERE key_hash IN ({placeholders}) AND status = ? "
                f"ORDER BY created_at DESC LIMIT 1"
            )
            row = await pool.fetchone(query, (*digests, "active"))
    except Exception as e:
        # Log at WARNING level to make database errors visible
        # Re-raise so callers can distinguish "not found" from "error"
        logger.warning("resolve_api_key_by_hash: DB lookup failed: {}", e)
        raise

    if not row:
        return None

    if isinstance(row, dict):
        return {"id": row.get("id"), "user_id": row.get("user_id")}
    # tuple-like row
    try:
        return {"id": row[0], "user_id": row[1]}
    except Exception:
        return None
