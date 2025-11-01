from __future__ import annotations

from typing import Optional, Dict, Any
import hmac
import hashlib

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool


async def resolve_api_key_by_hash(api_key: str, *, settings=None) -> Optional[Dict[str, Any]]:
    """
    Resolve an API key to its database identity via HMAC hash lookup.

    Computes HMAC-SHA256 digests of the provided API key against all configured
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
    digests: list[str] = []
    try:
        candidates = tuple(derive_hmac_key_candidates(s))
    except Exception as e:
        logger.debug("resolve_api_key_by_hash: failed to derive candidates: {}", e)
        candidates = ()

    for key in candidates:
        try:
            digest = hmac.new(key, api_key.encode("utf-8"), hashlib.sha256).hexdigest()
            if digest not in digests:
                digests.append(digest)
        except Exception as _e:
            logger.debug("resolve_api_key_by_hash: digest calc failed: {}", _e)

    if not digests:
        return None

    pool = await get_db_pool()
    placeholders = ",".join("?" for _ in digests)
    query = (
        f"SELECT id, user_id FROM api_keys "
        f"WHERE key_hash IN ({placeholders}) AND status = ? "
        f"ORDER BY created_at DESC LIMIT 1"
    )
    row = await pool.fetchone(query, (*digests, "active"))
    if not row:
        return None

    if isinstance(row, dict):
        return {"id": row.get("id"), "user_id": row.get("user_id")}
    # tuple-like row
    try:
        return {"id": row[0], "user_id": row[1]}
    except Exception:
        return None

