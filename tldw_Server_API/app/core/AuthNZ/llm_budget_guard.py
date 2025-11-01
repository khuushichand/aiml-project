from __future__ import annotations

from typing import Optional
import hmac
import hashlib

from fastapi import Request, HTTPException
import os

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key_candidates
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.virtual_keys import get_key_limits, is_key_over_budget


async def enforce_llm_budget(request: Request) -> None:
    """
    Enforces LLM budgets for virtual API keys on incoming requests.
    
    If budget enforcement is enabled and the request is associated with an API key that is marked virtual, verifies the key's token and USD limits and raises HTTPException(402) with a detail payload when the key is over its budget. This dependency is a no-op for requests without an API key or when virtual keys or budget enforcement are disabled.
    """
    settings = get_settings()
    _dbg = (
        os.getenv("BUDGET_MW_DEBUG", "").lower() in {"1", "true", "yes", "on"}
        or os.getenv("PYTEST_CURRENT_TEST") is not None
    )
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
            candidates = list(derive_hmac_key_candidates(settings))
            if _dbg:
                from loguru import logger
                logger.debug(f"LLM guard: hash candidates={len(candidates)}")
            for key in candidates:
                digest = hmac.new(key, api_key.encode("utf-8"), hashlib.sha256).hexdigest()
                if digest not in digests:
                    digests.append(digest)
            if _dbg and digests:
                from loguru import logger
                logger.debug(f"LLM guard: first digest={digests[0][:12]}… total={len(digests)}")
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
                elif _dbg:
                    from loguru import logger
                    logger.debug("LLM guard: no key_id found via hash lookup")

    if not key_id:
        # JWT or anonymous path; budgets apply only to API keys
        if _dbg:
            from loguru import logger
            logger.debug("LLM guard: skipping budget enforcement (no api_key_id)")
        return

    limits = await get_key_limits(int(key_id))
    if not limits or not limits.get("is_virtual"):
        if _dbg:
            from loguru import logger
            logger.debug(f"LLM guard: key {key_id} not virtual or limits missing; skipping")
        return

    result = await is_key_over_budget(int(key_id))
    if _dbg:
        from loguru import logger
        limits = result.get('limits', {}) or {}
        subset = {
            'llm_budget_day_tokens': limits.get('llm_budget_day_tokens'),
            'llm_budget_day_usd': limits.get('llm_budget_day_usd'),
            'llm_budget_month_tokens': limits.get('llm_budget_month_tokens'),
            'llm_budget_month_usd': limits.get('llm_budget_month_usd'),
        }
        logger.debug(
            f"LLM guard: over_budget={result.get('over')} reasons={result.get('reasons')} "
            f"day={result.get('day')} month={result.get('month')} limits={subset}"
        )
    if result.get("over"):
        raise HTTPException(status_code=402, detail={
            "error": "budget_exceeded",
            "message": "Virtual key budget exceeded",
            "details": result,
        })