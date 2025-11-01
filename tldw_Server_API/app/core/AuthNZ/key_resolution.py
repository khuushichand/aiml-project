from __future__ import annotations
#
from typing import Optional, Dict, Any
import os
#
# Third-Party-Libs
from argon2 import PasswordHasher
from loguru import logger
from passlib.handlers import digests

#
# Local Imports
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool


async def resolve_api_key_by_hash(api_key: str, *, settings=None) -> Optional[Dict[str, Any]]:
    """
    Resolve an API key to its database identity via Argon2 password hash lookup.

    Attempts Argon2 verification of the provided API key against all configured
    key-derivation candidates and queries the `api_keys` table for a matching
    active key. Returns a mapping with `id` and `user_id` when found, otherwise
    None.

    Parameters:
        api_key: The raw API key string provided by the client.
        settings: Optional settings object; falls back to get_settings() when None.

    Returns:
        dict with keys `id` and `user_id` if a match is found; otherwise None.
    """
    if not api_key:
        return None

    s = settings or get_settings()
    hashes: list[str] = []
    try:
        candidates = tuple(derive_hmac_key_candidates(s))
        # Minimal debug insight with safe fallback
        if os.getenv("BUDGET_MW_DEBUG", "").lower() in {"1", "true", "yes", "on"} or os.getenv("PYTEST_CURRENT_TEST"):
            try:
                logger.debug(f"resolve_api_key_by_hash: hash candidates={len(candidates)}")
            except Exception as _dbg_exc:
                logger.trace(f"resolve_api_key_by_hash: debug logging failed: {_dbg_exc}")
    except Exception as e:
        logger.debug("resolve_api_key_by_hash: failed to derive candidates: {}", e)
        candidates = ()
    ph = PasswordHasher()

    for key in candidates:
        try:
            # Instead of deriving HMAC digests, assume key is an argon2 hash candidate.
            # In legacy case, adapt accordingly; here we treat 'key' as stored Argon2 hash
            # Attempt Argon2 verification:
            if ph.verify(key, api_key):
                hashes.append(key)
        except Exception as _e:
            logger.debug("resolve_api_key_by_hash: Argon2 verify failed: {}", _e)

    if not hashes:
        return None

    pool = await get_db_pool()
    # Dialect-aware query (match api_key_manager implementation)
    if getattr(pool, 'pool', None) is not None:
        # Postgres
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
        # SQLite
        placeholders = ",".join("?" for _ in digests)
        query = (
            f"SELECT id, user_id FROM api_keys "
            f"WHERE key_hash IN ({placeholders}) AND status = ? "
            f"ORDER BY created_at DESC LIMIT 1"
        )
        row = await pool.fetchone(query, (*digests, "active"))
    placeholders = ",".join("?" for _ in hashes)
    query = (
        f"SELECT id, user_id FROM api_keys "
        f"WHERE key_hash IN ({placeholders}) AND status = ? "
        f"ORDER BY created_at DESC LIMIT 1"
    )
    row = await pool.fetchone(query, (*hashes, "active"))
    if not row:
        return None

    if isinstance(row, dict):
        return {"id": row.get("id"), "user_id": row.get("user_id")}
    # tuple-like row
    try:
        return {"id": row[0], "user_id": row[1]}
    except Exception:
        return None
