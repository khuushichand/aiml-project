from __future__ import annotations

import os
import time
from typing import Optional, Tuple

from fastapi import Depends, HTTPException
from fastapi import Request, Response
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.AuthNZ.settings import (
    is_single_user_mode,
    get_settings,
    reset_settings,
)
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.Infrastructure.redis_factory import (
    create_async_redis_client,
    ensure_async_client_closed,
)

import redis.asyncio as aioredis


async def _get_redis_client() -> aioredis.Redis:
    return await create_async_redis_client(context="ingest_backpressure")


def _cfg_int(name: str, default_val: int) -> int:
    try:
        v = settings.get(name, None)
        if isinstance(v, (int, float)):
            return int(v)
    except Exception:
        pass
    try:
        env = os.getenv(name)
        if env is not None and str(env).strip() != "":
            return int(env)
    except Exception:
        pass
    return int(default_val)


def _cfg_float(name: str, default_val: float) -> float:
    try:
        v = settings.get(name, None)
        if isinstance(v, (int, float)):
            return float(v)
    except Exception:
        pass
    try:
        env = os.getenv(name)
        if env is not None and str(env).strip() != "":
            return float(env)
    except Exception:
        pass
    return float(default_val)


def _bp_limits() -> Tuple[int, float]:
    """Return the current backpressure limits using latest config/env overrides."""
    max_depth = _cfg_int("EMB_BACKPRESSURE_MAX_DEPTH", 25000)
    max_age = _cfg_float("EMB_BACKPRESSURE_MAX_AGE_SECONDS", 300.0)
    return max_depth, max_age


def _is_single_user_mode_runtime() -> bool:
    """Determine auth mode, allowing env overrides to take effect without restart."""
    env_mode = os.getenv("AUTH_MODE")
    if env_mode:
        normalized = env_mode.strip().lower()
        try:
            settings_obj = get_settings()
            if settings_obj.AUTH_MODE.lower() != normalized:
                reset_settings()
        except Exception:
            try:
                reset_settings()
            except Exception:
                pass
        return normalized != "multi_user"
    return is_single_user_mode()


async def _orchestrator_depth_and_age(client: aioredis.Redis) -> Tuple[int, float]:
    queues = ["embeddings:chunking", "embeddings:embedding", "embeddings:storage"]
    depths = []
    ages = []
    now = time.time()
    for q in queues:
        try:
            d = await client.xlen(q)
        except Exception:
            d = 0
        depths.append(int(d or 0))
        try:
            items = await client.xrange(q, "-", "+", count=1)
            if items:
                first_id = items[0][0]
                ts_ms = float(first_id.split("-", 1)[0])
                ages.append(max(0.0, now - (ts_ms / 1000.0)))
            else:
                ages.append(0.0)
        except Exception:
            ages.append(0.0)
    return (max(depths) if depths else 0, max(ages) if ages else 0.0)


async def guard_backpressure_and_quota(
    request: Request,
    response: Response,
    current_user: User = Depends(get_request_user),
):
    # Backpressure by orchestrator depth/age
    client: Optional[aioredis.Redis] = None
    try:
        try:
            client = await _get_redis_client()
        except Exception:
            client = None
        if client is not None:
            max_depth, max_age = _bp_limits()
            depth, age = await _orchestrator_depth_and_age(client)
            if depth >= max_depth or age >= max_age:
                retry_after = 5
                if age >= max_age:
                    retry_after = min(60, int(max(5, age / 2)))
                raise HTTPException(status_code=429, detail="Backpressure: queue overload", headers={"Retry-After": str(retry_after)})
    finally:
        try:
            if client is not None:
                await ensure_async_client_closed(client)
        except Exception:
            pass

    # Tenant quota (allow override key for ingestion; fallback to embeddings quota)
    rps = _cfg_int("INGEST_TENANT_RPS", 0) or _cfg_int("EMBEDDINGS_TENANT_RPS", 0)
    if not _is_single_user_mode_runtime() and rps > 0:
        client2: Optional[aioredis.Redis] = None
        try:
            client2 = await _get_redis_client()
            ts = int(time.time())
            key = f"ingest:tenant:rps:{getattr(current_user, 'id', 'anon')}:{ts}"
            current = await client2.incr(key)
            await client2.expire(key, 2)
            remaining = max(0, rps - int(current or 0))
            if current > rps:
                raise HTTPException(status_code=429, detail="Tenant quota exceeded", headers={"Retry-After": "1", "X-RateLimit-Limit": str(rps), "X-RateLimit-Remaining": str(0)})
            else:
                try:
                    response.headers["X-RateLimit-Limit"] = str(rps)
                    response.headers["X-RateLimit-Remaining"] = str(remaining)
                except Exception:
                    pass
        finally:
            try:
                if client2 is not None:
                    await ensure_async_client_closed(client2)
            except Exception:
                pass

    # No return value; dependency completes
    return None
