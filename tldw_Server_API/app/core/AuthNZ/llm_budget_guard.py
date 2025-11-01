from __future__ import annotations

from typing import Optional
import hmac
import hashlib

from fastapi import Request, HTTPException

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.virtual_keys import get_key_limits, is_key_over_budget


async def enforce_llm_budget(request: Request) -> None:
    """FastAPI dependency to enforce LLM budgets for virtual API keys.

    - Resolves the API key ID from headers (X-API-KEY or Authorization: Bearer) via
      HMAC-SHA256 hash lookup in the AuthNZ DB. This avoids reliance on any
      singleton manager state and works across reset settings during tests.
    - If the key is virtual and over budget (token or USD, day or month), raises
      HTTPException 402 before the handler executes.
    - If no API key is present (e.g., JWT flow), this dependency is a no-op.
    """
    settings = get_settings()
    if not getattr(settings, "VIRTUAL_KEYS_ENABLED", True):
        return
    if not getattr(settings, "LLM_BUDGET_ENFORCE", True):
        return

    # Already bound by earlier auth dependency?
    key_id: Optional[int] = getattr(request.state, "api_key_id", None)

    # Otherwise, resolve from headers deterministically
    if not key_id:
        api_key = request.headers.get("X-API-KEY") or request.headers.get("x-api-key")
        if not api_key:
            auth = request.headers.get("authorization") or request.headers.get("Authorization")
            if isinstance(auth, str) and auth.lower().startswith("bearer "):
                api_key = auth.split(" ", 1)[1].strip()

        if api_key:
            digests: list[str] = []
            for key in derive_hmac_key_candidates(settings):
                digest = hmac.new(key, api_key.encode("utf-8"), hashlib.sha256).hexdigest()
                if digest not in digests:
                    digests.append(digest)
            if digests:
                pool = await get_db_pool()
                placeholders = ",".join("?" for _ in digests)
                query = (
                    f"SELECT id, user_id FROM api_keys "
                    f"WHERE key_hash IN ({placeholders}) AND status = ? "
                    f"ORDER BY created_at DESC LIMIT 1"
                )
                row = await pool.fetchone(query, (*digests, "active"))
                if row:
                    key_id = row.get("id") if isinstance(row, dict) else row[0]
                    try:
                        request.state.api_key_id = key_id
                        request.state.user_id = row.get("user_id") if isinstance(row, dict) else row[1]
                    except Exception:
                        pass

    if not key_id:
        # JWT or anonymous path; budgets apply only to API keys
        return

    limits = await get_key_limits(int(key_id))
    if not limits or not limits.get("is_virtual"):
        return

    result = await is_key_over_budget(int(key_id))
    if result.get("over"):
        raise HTTPException(status_code=402, detail={
            "error": "budget_exceeded",
            "message": "Virtual key budget exceeded",
            "details": result,
        })

