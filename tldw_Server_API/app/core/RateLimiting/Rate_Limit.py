# tldw_Server_API/app/core/RateLimiting/Rate_Limit.py
# Description: Legacy rate limiting utilities aligned with Resource Governor.
#
# Imports
import asyncio
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional
#
# 3rd-party Libraries
from fastapi import Request, HTTPException, status
from loguru import logger
#
# Local Imports
from tldw_Server_API.app.core.config import settings, rg_enabled
from tldw_Server_API.app.core.Infrastructure.redis_factory import create_async_redis_client

try:  # pragma: no cover - RG is optional during early startup/tests
    from tldw_Server_API.app.core.Resource_Governance import (  # type: ignore
        MemoryResourceGovernor,
        RedisResourceGovernor,
        RGRequest,
    )
    from tldw_Server_API.app.core.Resource_Governance.policy_loader import (  # type: ignore
        PolicyLoader,
        PolicyReloadConfig,
        default_policy_loader,
    )
    from tldw_Server_API.app.core.Resource_Governance.deps import derive_entity_key  # type: ignore
    from tldw_Server_API.app.core.Resource_Governance.daily_caps import check_daily_cap  # type: ignore
except Exception:  # pragma: no cover - safe fallback when RG not installed
    MemoryResourceGovernor = None  # type: ignore
    RedisResourceGovernor = None  # type: ignore
    RGRequest = None  # type: ignore
    PolicyLoader = None  # type: ignore
    PolicyReloadConfig = None  # type: ignore
    default_policy_loader = None  # type: ignore
    derive_entity_key = None  # type: ignore
    check_daily_cap = None  # type: ignore
#
#######################################################################################################################
#
# Globals / Configuration:

# --- Redis fallback (legacy request limiter) ---
_REDIS_CLIENT = None
_REDIS_LOCK = asyncio.Lock()
_REDIS_STUB_RETRY_AT = 0.0
_REDIS_STUB_RETRY_INTERVAL = 15

# --- Resource Governor plumbing (optional) ---
_rg_governor = None
_rg_loader = None
_rg_lock = asyncio.Lock()

# --- Defaults for legacy fallback ---
RATE = 30                    # requests
WINDOW = 60                  # seconds
TOKENS_DAILY = 100_000       # model tokens per user per UTC day


def _coerce_non_negative_int(value: Any) -> int:
    try:
        val = int(value)
    except Exception:
        return 0
    return val if val > 0 else 0


def _rg_enabled() -> bool:
    if rg_enabled is None:
        return False
    try:
        return bool(rg_enabled(True))  # type: ignore[func-returns-value]
    except Exception:
        return False


async def _create_redis_client():
    try:
        url = settings.get("REDIS_URL", None)
    except Exception:
        url = None
    return await create_async_redis_client(
        preferred_url=url,
        context="rate_limit",
    )


async def _get_redis_client():
    global _REDIS_CLIENT, _REDIS_STUB_RETRY_AT
    if _REDIS_CLIENT is not None:
        if getattr(_REDIS_CLIENT, "_tldw_is_stub", False):
            now = time.time()
            if now >= _REDIS_STUB_RETRY_AT:
                _REDIS_STUB_RETRY_AT = now + _REDIS_STUB_RETRY_INTERVAL
                try:
                    candidate = await _create_redis_client()
                    if not getattr(candidate, "_tldw_is_stub", False):
                        _REDIS_CLIENT = candidate
                except Exception:
                    pass
        return _REDIS_CLIENT
    async with _REDIS_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT
        _REDIS_CLIENT = await _create_redis_client()
        return _REDIS_CLIENT


def _derive_entity(request: Request) -> str:
    if derive_entity_key is not None:
        try:
            return derive_entity_key(request)
        except Exception:
            pass
    try:
        user = getattr(request.state, "user", None)
        if user is not None and getattr(user, "id", None) is not None:
            return f"user:{user.id}"
    except Exception:
        pass
    try:
        uid = getattr(request.state, "user_id", None)
        if uid is not None:
            return f"user:{uid}"
    except Exception:
        pass
    try:
        key_id = getattr(request.state, "api_key_id", None)
        if key_id is not None:
            return f"api_key:{key_id}"
    except Exception:
        pass
    try:
        client = request.client
        if client and client.host:
            return f"ip:{client.host}"
    except Exception:
        pass
    return "ip:unknown"


def _resolve_policy_id(request: Request, override: Optional[str] = None) -> str:
    if override:
        return str(override)
    try:
        policy_id = getattr(request.state, "rg_policy_id", None)
        if policy_id:
            return str(policy_id)
    except Exception:
        pass
    try:
        loader = getattr(request.app.state, "rg_policy_loader", None)
        if loader is not None:
            snap = loader.get_snapshot()
            route_map = getattr(snap, "route_map", {}) or {}
            by_path = dict(route_map.get("by_path") or {})
            path = request.url.path or "/"
            for pat, pol in by_path.items():
                pat = str(pat)
                if pat.endswith("*"):
                    if path.startswith(pat[:-1]):
                        return str(pol)
                elif path == pat:
                    return str(pol)
            by_tag = dict(route_map.get("by_tag") or {})
            route = request.scope.get("route")
            tags = list(getattr(route, "tags", []) or [])
            for tag in tags:
                if tag in by_tag:
                    return str(by_tag[tag])
    except Exception:
        pass
    return os.getenv("RG_RATE_LIMIT_POLICY_ID", "core.default")


def _build_rate_limit_headers(limit: Optional[int], remaining: Optional[int], retry_after: Optional[int]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if retry_after is not None:
        headers["Retry-After"] = str(int(retry_after))
        headers["X-RateLimit-Reset"] = str(int(retry_after))
    if limit is not None:
        headers["X-RateLimit-Limit"] = str(int(limit))
    if remaining is not None:
        headers["X-RateLimit-Remaining"] = str(int(max(0, remaining)))
    return headers


async def _get_rg_governor(request: Optional[Request] = None):
    global _rg_governor, _rg_loader
    if not _rg_enabled():
        return None
    if request is not None:
        try:
            gov = getattr(request.app.state, "rg_governor", None)
            if gov is not None:
                return gov
        except Exception:
            pass
    if RGRequest is None or PolicyLoader is None:
        return None
    if _rg_governor is not None:
        return _rg_governor
    async with _rg_lock:
        if _rg_governor is not None:
            return _rg_governor
        try:
            loader = default_policy_loader() if default_policy_loader else PolicyLoader(
                os.getenv(
                    "RG_POLICY_PATH",
                    "tldw_Server_API/Config_Files/resource_governor_policies.yaml",
                ),
                PolicyReloadConfig(
                    enabled=True,
                    interval_sec=int(os.getenv("RG_POLICY_RELOAD_INTERVAL_SEC", "10") or "10"),
                ),
            )
            await loader.load_once()
            _rg_loader = loader
            backend = os.getenv("RG_BACKEND", "memory").lower()
            if backend == "redis" and RedisResourceGovernor is not None:
                gov = RedisResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            else:
                gov = MemoryResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            _rg_governor = gov
            return gov
        except Exception as exc:  # pragma: no cover - optional path
            logger.debug("RateLimit RG governor init failed: {}", exc)
            return None


async def _enforce_requests_legacy(entity: str) -> None:
    if RATE <= 0 or WINDOW <= 0:
        return
    client = await _get_redis_client()
    now = time.time()
    window_id = int(now // WINDOW)
    curr_key = f"rl:req:{entity}:{window_id}"
    prev_key = f"rl:req:{entity}:{window_id - 1}"
    pipe = client.pipeline()
    pipe.incr(curr_key, 1)
    pipe.expire(curr_key, WINDOW * 2)
    pipe.expire(prev_key, WINDOW * 2)
    results = await pipe.execute()
    curr_count = _coerce_non_negative_int(results[0] if results else 0)
    prev_raw = await client.get(prev_key)
    prev_count = _coerce_non_negative_int(prev_raw)
    elapsed = now - (window_id * WINDOW)
    weight = max(0.0, float(WINDOW - elapsed) / float(WINDOW))
    effective = curr_count + (prev_count * weight)
    if effective > RATE:
        retry_after = max(1, int(WINDOW - elapsed))
        headers = _build_rate_limit_headers(RATE, 0, retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate-limit exceeded",
            headers=headers,
        )


async def _enforce_requests_rg(request: Request, policy_id: str, entity: str) -> bool:
    if RGRequest is None:
        return False
    try:
        if getattr(request.state, "rg_policy_id", None):
            return True
    except Exception:
        pass
    gov = await _get_rg_governor(request)
    if gov is None:
        return False
    op_id = (
        getattr(getattr(request, "state", None), "request_id", None)
        or request.headers.get("X-Request-ID")
        or str(uuid.uuid4())
    )
    decision, handle = await gov.reserve(
        RGRequest(
            entity=entity,
            categories={"requests": {"units": 1}},
            tags={"policy_id": policy_id, "endpoint": request.url.path},
        ),
        op_id=op_id,
    )
    if not bool(getattr(decision, "allowed", False)):
        retry_after = int(getattr(decision, "retry_after", None) or 1)
        limit = None
        remaining = None
        try:
            cat = (decision.details or {}).get("categories", {}).get("requests", {})  # type: ignore[union-attr]
            limit = _coerce_non_negative_int(cat.get("limit"))
            remaining = _coerce_non_negative_int(cat.get("remaining"))
        except Exception:
            pass
        headers = _build_rate_limit_headers(limit or None, remaining or None, retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate-limit exceeded",
            headers=headers,
        )
    if handle:
        try:
            await gov.commit(handle, actuals={"requests": 1}, op_id=op_id)
        except Exception:
            logger.debug("RateLimit RG commit failed", exc_info=True)
    return True


async def _enforce_tokens_rg(request: Request, policy_id: str, entity: str, tokens_used: int) -> bool:
    if RGRequest is None:
        return False
    gov = await _get_rg_governor(request)
    if gov is None:
        return False
    tokens_units = _coerce_non_negative_int(tokens_used)
    if tokens_units <= 0:
        return True
    op_id = (
        getattr(getattr(request, "state", None), "request_id", None)
        or request.headers.get("X-Request-ID")
        or str(uuid.uuid4())
    )
    decision, handle = await gov.reserve(
        RGRequest(
            entity=entity,
            categories={"tokens": {"units": tokens_units}},
            tags={"policy_id": policy_id, "endpoint": request.url.path},
        ),
        op_id=op_id,
    )
    if not bool(getattr(decision, "allowed", False)):
        retry_after = int(getattr(decision, "retry_after", None) or 1)
        limit = None
        remaining = None
        try:
            cat = (decision.details or {}).get("categories", {}).get("tokens", {})  # type: ignore[union-attr]
            limit = _coerce_non_negative_int(cat.get("limit"))
            remaining = _coerce_non_negative_int(cat.get("remaining"))
        except Exception:
            pass
        headers = _build_rate_limit_headers(limit or None, remaining or None, retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="token quota exceeded",
            headers=headers,
        )
    if handle:
        try:
            await gov.commit(handle, actuals={"tokens": tokens_units}, op_id=op_id)
        except Exception:
            logger.debug("RateLimit RG token commit failed", exc_info=True)
    return True


async def _enforce_tokens_legacy(entity: str, tokens_used: int) -> None:
    tokens_units = _coerce_non_negative_int(tokens_used)
    if tokens_units <= 0:
        return
    if check_daily_cap is None:
        return
    try:
        entity_scope, entity_value = entity.split(":", 1)
    except Exception:
        entity_scope, entity_value = "entity", entity
    allowed, retry_after, details = await check_daily_cap(
        entity_scope=entity_scope,
        entity_value=entity_value,
        category="tokens",
        daily_cap=TOKENS_DAILY,
        units=tokens_units,
    )
    if allowed:
        return
    remaining = None
    try:
        remaining = int((details or {}).get("daily_remaining") or 0)
    except Exception:
        remaining = None
    headers = _build_rate_limit_headers(TOKENS_DAILY, remaining, retry_after or 1)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="daily token quota exhausted",
        headers=headers,
    )


@dataclass
class RateLimitContext:
    """Rate limit context that allows handlers to report server-side token usage."""

    request: Request
    policy_id: str
    entity: str
    tokens_used: int = 0

    def add_tokens(self, tokens: Any) -> None:
        self.tokens_used += _coerce_non_negative_int(tokens)


# --- Dependency ------------------------------------------------------------ #

async def ratelimit_dependency(request: Request, policy_id: Optional[str] = None):
    """
    Enforce request limits and expose a context for server-side token usage.

    Usage:
        ctx: RateLimitContext = Depends(ratelimit_dependency)
        ctx.add_tokens(total_tokens)  # call after tokens are known
    """
    entity = _derive_entity(request)
    resolved_policy = _resolve_policy_id(request, policy_id)
    ctx = RateLimitContext(request=request, policy_id=resolved_policy, entity=entity)

    error: Optional[BaseException] = None
    try:
        # Prefer RG for request enforcement when enabled.
        used_rg = False
        if _rg_enabled():
            try:
                used_rg = await _enforce_requests_rg(request, resolved_policy, entity)
            except HTTPException:
                raise
            except Exception as exc:
                logger.debug("RateLimit RG request enforcement failed; falling back: {}", exc)
                used_rg = False
        if not used_rg:
            await _enforce_requests_legacy(entity)
        yield ctx
    except BaseException as exc:
        error = exc
        raise
    finally:
        # Token enforcement must use server-side usage (ctx.add_tokens).
        if error is None and ctx.tokens_used:
            try:
                used_rg = False
                if _rg_enabled():
                    used_rg = await _enforce_tokens_rg(request, resolved_policy, entity, ctx.tokens_used)
                if not used_rg:
                    await _enforce_tokens_legacy(entity, ctx.tokens_used)
            except HTTPException:
                raise
            except Exception as exc:
                logger.debug("RateLimit token enforcement failed; skipping: {}", exc)

#
# End of Rate_Limit.py
#######################################################################################################################
