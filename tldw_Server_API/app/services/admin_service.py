from __future__ import annotations

from typing import Any, Dict, Optional
from loguru import logger
import json as _json

from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend


async def update_api_key_metadata(
    db,
    *,
    user_id: int,
    key_id: int,
    rate_limit: Optional[int] = None,
    allowed_ips: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """Update per-key limits/metadata for an API key and return normalized row.

    Handles Postgres and SQLite parameterization and returns a dict suitable for
    APIKeyMetadata construction.
    """
    is_pg = await is_postgres_backend()
    fields: list[str] = []
    params: list[Any] = []

    if rate_limit is not None:
        fields.append("rate_limit = ${}" if is_pg else "rate_limit = ?")
        params.append(rate_limit)
    if allowed_ips is not None:
        fields.append("allowed_ips = ${}" if is_pg else "allowed_ips = ?")
        params.append(_json.dumps(allowed_ips))

    if not fields:
        raise ValueError("No updates provided")

    if is_pg:
        set_clause = ", ".join(fields[i].format(i + 1) for i in range(len(fields)))
        query = f"UPDATE api_keys SET {set_clause} WHERE id = $ {len(fields) + 1} AND user_id = $ {len(fields) + 2}"
        query = query.replace('$ ', '$')
        await db.execute(query, *params, key_id, user_id)
        row = await db.fetchrow("SELECT * FROM api_keys WHERE id = $1 AND user_id = $2", key_id, user_id)
    else:
        set_clause = ", ".join(fields)
        params2 = list(params) + [key_id, user_id]
        await db.execute(f"UPDATE api_keys SET {set_clause} WHERE id = ? AND user_id = ?", params2)
        commit = getattr(db, "commit", None)
        if callable(commit):
            await commit()
        cursor = await db.execute("SELECT * FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id))
        row = await cursor.fetchone()

    if not row:
        raise LookupError("API key not found")

    # Normalize row
    if not isinstance(row, dict):
        try:
            row = dict(row)
        except Exception:
            cols = [
                'id','user_id','key_hash','key_prefix','name','description','scope','status','created_at','expires_at',
                'last_used_at','last_used_ip','usage_count','rate_limit','allowed_ips','metadata','rotated_from','rotated_to',
                'revoked_at','revoked_by','revoke_reason'
            ]
            row = {cols[i]: row[i] for i in range(min(len(cols), len(row)))}

    row.pop('key_hash', None)
    return row
