from __future__ import annotations

from fastapi import APIRouter, Request, Header
from typing import Optional, Dict, Any

from tldw_Server_API.app.core.AuthNZ.key_resolution import resolve_api_key_by_hash
from tldw_Server_API.app.core.AuthNZ.virtual_keys import (
    get_key_limits,
    summarize_usage_for_key_day,
    summarize_usage_for_key_month,
    is_key_over_budget,
)

router = APIRouter()


async def _resolve_api_key_id(request: Request, x_api_key: Optional[str]) -> Dict[str, Any]:
    # Prefer earlier resolution from auth middlewares/deps
    """
    Resolve an API key to its `api_key_id` and associated `user_id` for the incoming request.

    Prefers values previously set on `request.state` by auth middleware. Otherwise
    extracts an API key from the provided `x_api_key` parameter or a Bearer token
    in the Authorization header and resolves it via `resolve_api_key_by_hash`.

    Parameters:
        request (Request): The incoming FastAPI request; may contain pre-resolved `state.api_key_id` and `state.user_id`.
        x_api_key (Optional[str]): An explicit API key (typically from the X-API-KEY header) to resolve; if omitted, the Authorization header is inspected.

    Returns:
        dict: A mapping with keys:
            - "api_key_id": int or None - the resolved API key ID as an integer when found, otherwise None.
            - "user_id": Any or None - the associated user identifier when available, otherwise None.
    """
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

    result = await resolve_api_key_by_hash(api_key)
    if not result:
        return {"api_key_id": None, "user_id": None}

    return {"api_key_id": int(result["id"]), "user_id": result["user_id"]}


@router.get("/authnz/debug/api-key-id", tags=["authnz-debug"])
async def debug_api_key_id(request: Request, X_API_KEY: Optional[str] = Header(None, alias="X-API-KEY")):
    """
    Resolve the provided API key and return its associated api_key_id and user_id.

    This endpoint is for debugging and does not enforce authentication.

    Returns:
        result (dict): A dictionary with `"status": "ok"` plus `api_key_id` (int or None) and `user_id` (user identifier or None).
    """
    resolved = await _resolve_api_key_id(request, X_API_KEY)
    return {"status": "ok", **resolved}


@router.get("/authnz/debug/budget-summary", tags=["authnz-debug"])
async def debug_budget_summary(request: Request, X_API_KEY: Optional[str] = Header(None, alias="X-API-KEY")):
    """
    Provide limits, daily and monthly usage summaries, and an over-budget evaluation for the resolved API key.

    If no API key is resolved from the request or headers, returns a response with `"api_key_id": None` and a `"message"` explaining no key was resolved.

    Returns:
        dict: A response object containing:
            - status (str): Always `"ok"`.
            - api_key_id (int | None): The resolved API key ID, or `None` if no key was resolved.
            - message (str, optional): Present when no API key was resolved.
            - limits (Any): Key limits as returned by `get_key_limits`.
            - day (Any): Daily usage summary as returned by `summarize_usage_for_key_day`.
            - month (Any): Monthly usage summary as returned by `summarize_usage_for_key_month`.
            - over_budget (bool): `true` if the key is over its budget, `false` otherwise.
            - reasons (Any): Explanation or list of reasons from `is_key_over_budget`.
    """
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
