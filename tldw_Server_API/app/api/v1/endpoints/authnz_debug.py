from __future__ import annotations

from fastapi import APIRouter, Request, Header
from typing import Optional, Dict, Any

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.virtual_keys import (
    get_key_limits,
    summarize_usage_for_key_day,
    summarize_usage_for_key_month,
    is_key_over_budget,
)

router = APIRouter()


async def _resolve_api_key_id(request: Request, x_api_key: Optional[str]) -> Dict[str, Any]:
    # Prefer earlier resolution from auth middlewares/deps
    key_id = getattr(request.state, "api_key_id", None)
    user_id = getattr(request.state, "user_id", None)
    if key_id:
        return {"api_key_id": int(key_id), "user_id": user_id}

    api_key = x_api_key
    if not api_key:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if isinstance(auth, str) and auth.lower().startswith("bearer "):
            api_key = auth.split(" ", 1)[1].strip()

    if not api_key:
        return {"api_key_id": None, "user_id": None}

    digests = []
    for key in derive_hmac_key_candidates(get_settings()):
        import hmac, hashlib
        digest = hmac.new(key, api_key.encode("utf-8"), hashlib.sha256).hexdigest()
        if digest not in digests:
            digests.append(digest)
    if not digests:
        return {"api_key_id": None, "user_id": None}

    pool = await get_db_pool()
    placeholders = ",".join("?" for _ in digests)
    row = await pool.fetchone(
        (
            f"SELECT id, user_id FROM api_keys "
            f"WHERE key_hash IN ({placeholders}) AND status = ? "
            f"ORDER BY created_at DESC LIMIT 1"
        ),
        (*digests, "active"),
    )
    if not row:
        return {"api_key_id": None, "user_id": None}

    return {"api_key_id": int(row.get("id") if isinstance(row, dict) else row[0]),
            "user_id": row.get("user_id") if isinstance(row, dict) else row[1]}


@router.get("/authnz/debug/api-key-id", tags=["authnz-debug"])
async def debug_api_key_id(request: Request, X_API_KEY: Optional[str] = Header(None, alias="X-API-KEY")):
    """Return the resolved api_key_id/user_id for the provided API key header.

    Only intended for test/debug use; no auth enforced.
    """
    resolved = await _resolve_api_key_id(request, X_API_KEY)
    return {"status": "ok", **resolved}


@router.get("/authnz/debug/budget-summary", tags=["authnz-debug"])
async def debug_budget_summary(request: Request, X_API_KEY: Optional[str] = Header(None, alias="X-API-KEY")):
    """Return limits and current day/month usage and over-budget flag for the key."""
    resolved = await _resolve_api_key_id(request, X_API_KEY)
    key_id = resolved.get("api_key_id")
    if not key_id:
        return {"status": "ok", "api_key_id": None, "message": "no api key resolved"}

    limits = await get_key_limits(int(key_id))
    day = await summarize_usage_for_key_day(int(key_id))
    month = await summarize_usage_for_key_month(int(key_id))
    decision = await is_key_over_budget(int(key_id))
    return {
        "status": "ok",
        "api_key_id": key_id,
        "limits": limits,
        "day": day,
        "month": month,
        "over_budget": decision.get("over"),
        "reasons": decision.get("reasons"),
    }

