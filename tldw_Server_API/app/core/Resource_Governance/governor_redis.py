from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from .governor import ResourceGovernor, RGRequest, RGDecision
from .metrics_rg import ensure_rg_metrics_registered, _labels
from .governor import _ReservationHandle  # reuse structure for handle hashing
from .governor import _Lease  # type: ignore  # not directly used, kept for type parity

from tldw_Server_API.app.core.Infrastructure.redis_factory import create_async_redis_client
from tldw_Server_API.app.core.config import rg_redis_fail_mode


TimeSource = callable


@dataclass
class _RedisKeys:
    ns: str

    def win(self, policy_id: str, category: str, scope: str, entity_value: str) -> str:
        return f"{self.ns}:win:{policy_id}:{category}:{scope}:{entity_value}"

    def lease(self, policy_id: str, category: str, scope: str, entity_value: str) -> str:
        return f"{self.ns}:lease:{policy_id}:{category}:{scope}:{entity_value}"

    def handle(self, handle_id: str) -> str:
        return f"{self.ns}:handle:{handle_id}"

    def op(self, op_id: str) -> str:
        return f"{self.ns}:op:{op_id}"


class RedisResourceGovernor(ResourceGovernor):
    """
    Redis-backed Resource Governor using sliding window for requests and
    fixed-window counters for tokens. Concurrency implemented via ZSET leases.

    Notes:
      - For requests: uses ZSET per (policy/category/scope/entity) with window=60s.
      - For tokens: uses fixed-window INCRBY + TTL of 60s as initial implementation.
      - Concurrency: per-lease ZSET storing expiry timestamps; purge on access.
      - Idempotency: stored as 'rg:op:{op_id}' → JSON with {type, handle_id} and TTL.
      - Handles: stored as 'rg:handle:{handle_id}' → JSON with policy/entity/categories/exp.
    """

    def __init__(
        self,
        *,
        policy_loader: Any,
        ns: str = "rg",
        time_source: Any = time.time,
    ) -> None:
        self._policy_loader = policy_loader
        self._time = time_source
        self._keys = _RedisKeys(ns=ns)
        self._client = None
        self._client_lock = asyncio.Lock()
        self._fail_mode = rg_redis_fail_mode()
        self._local_handles: Dict[str, Dict[str, Any]] = {}
        self._tokens_lua_sha: Optional[str] = None
        ensure_rg_metrics_registered()

    async def _client_get(self):
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is None:
                self._client = await create_async_redis_client(context="resource_governor", fallback_to_fake=True)
        return self._client

    def _get_policy(self, policy_id: str) -> Dict[str, Any]:
        try:
            pol = self._policy_loader.get_policy(policy_id)
            return pol or {}
        except Exception:
            return {}

    def _effective_fail_mode(self, policy: Dict[str, Any], category: Optional[str] = None) -> str:
        """Resolve fail_mode with per-category override, then policy, then global default."""
        try:
            if category:
                cat_cfg = policy.get(category) or {}
                fm = str((cat_cfg.get("fail_mode") or "")).strip().lower()
                if fm in ("fail_closed", "fail_open", "fallback_memory"):
                    return fm
            fm_pol = str((policy.get("fail_mode") or "")).strip().lower()
            if fm_pol in ("fail_closed", "fail_open", "fallback_memory"):
                return fm_pol
        except Exception:
            pass
        return self._fail_mode

    @staticmethod
    def _parse_entity(entity: str) -> Tuple[str, str]:
        if ":" in entity:
            s, v = entity.split(":", 1)
            return s.strip() or "entity", v.strip()
        return "entity", entity

    def _scopes(self, policy: Dict[str, Any]) -> list[str]:
        s = policy.get("scopes")
        if isinstance(s, list) and s:
            return [str(x) for x in s]
        return ["global", "entity"]

    async def _allow_requests_sliding(self, *, key: str, limit: int, window: int, units: int, now: float, fail_mode: str) -> Tuple[bool, int]:
        client = await self._client_get()
        # Use script heuristic in in-memory stub (supports retry_after); loop for each unit
        allow_all = True
        retry_after = 0
        for _ in range(units):
            # Direct emulate: purge expired, check count, add now
            try:
                await client.zremrangebyscore(key, float("-inf"), now - window)
                count = await client.zcard(key)
                if count < limit:
                    member = f"{now}:{uuid.uuid4().hex}"
                    await client.zadd(key, {member: now})
                    allow = True
                    ra = 0
                else:
                    # best-effort retry_after = window
                    allow = False
                    ra = window
            except Exception as e:
                if fail_mode == "fail_open":
                    allow = True
                    ra = 0
                elif fail_mode == "fallback_memory":
                    allow = True
                    ra = 0
                else:
                    allow = False
                    ra = window
            allow_all = allow_all and allow
            retry_after = max(retry_after, int(ra))
            if not allow:
                break
        return allow_all, retry_after

    async def _ensure_tokens_lua(self) -> Optional[str]:
        """Load a Lua sliding-window limiter script for tokens and cache SHA."""
        if self._tokens_lua_sha:
            return self._tokens_lua_sha
        client = await self._client_get()
        # Script implements: purge expired; if count < limit then add now; else return retry_after
        # Includes ZRANGE + ZREMRANGEBYSCORE to trigger stub recognition.
        script = """
        local key = KEYS[1]
        local limit = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local cutoff = now - window
        -- purge expired window entries
        redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
        local count = tonumber(redis.call('ZCARD', key))
        if count < limit then
          local member = tostring(now) .. ':' .. tostring(count + 1)
          redis.call('ZADD', key, now, member)
          return {1, 0}
        else
          local oldest = redis.call('ZRANGE', key, 0, 0, 'BYSCORE', 'REV')
          -- if no BYSCORE, fallback to simple oldest via ZRANGE 0 0
          if oldest == nil or #oldest == 0 then
            oldest = redis.call('ZRANGE', key, 0, 0)
          end
          local oldest_score = tonumber(redis.call('ZSCORE', key, oldest[1])) or now
          local ra = math.max(0, math.floor(oldest_score + window - now))
          if ra <= 0 then ra = window end
          return {0, ra}
        end
        """
        try:
            sha = await client.script_load(script)
            self._tokens_lua_sha = sha
            return sha
        except Exception:
            return None

    async def _allow_tokens_lua(self, *, key: str, limit: int, window: int, units: int, now: float, fail_mode: str) -> Tuple[bool, int]:
        client = await self._client_get()
        sha = await self._ensure_tokens_lua()
        allow_all = True
        retry_after = 0
        for _ in range(units):
            try:
                if sha:
                    res = await client.evalsha(sha, 1, key, int(limit), int(window), float(now))
                    ok = int(res[0]) == 1
                    ra = int(res[1]) if len(res) > 1 else 0
                else:
                    # Fallback to simple sliding window using primitives
                    await client.zremrangebyscore(key, float("-inf"), now - window)
                    count = await client.zcard(key)
                    if count < limit:
                        await client.zadd(key, {f"{now}:{uuid.uuid4().hex}": now})
                        ok, ra = True, 0
                    else:
                        ok, ra = False, window
            except Exception:
                if fail_mode == "fail_open":
                    ok, ra = True, 0
                elif fail_mode == "fallback_memory":
                    ok, ra = True, 0
                else:
                    ok, ra = False, window
            allow_all = allow_all and ok
            retry_after = max(retry_after, int(ra))
            if not ok:
                break
        return allow_all, retry_after

    async def check(self, req: RGRequest) -> RGDecision:
        policy_id = req.tags.get("policy_id") or "default"
        pol = self._get_policy(policy_id)
        entity_scope, entity_value = self._parse_entity(req.entity)
        backend = "redis"
        now = self._time()

        overall_allowed = True
        retry_after_overall = 0
        per_category: Dict[str, Any] = {}

        for category, cfg in req.categories.items():
            units = int(cfg.get("units") or 0)
            if category == "requests":
                rpm = int((pol.get("requests") or {}).get("rpm") or 0)
                window = 60
                limit = rpm
                allowed = True
                retry_after = 0
                cat_fail = self._effective_fail_mode(pol, category)
                for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                    if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                        continue
                    key = self._keys.win(policy_id, category, sc, ev)
                    ok, ra = await self._allow_requests_sliding(key=key, limit=limit, window=window, units=units, now=now, fail_mode=cat_fail)
                    allowed = allowed and ok
                    retry_after = max(retry_after, ra)
                per_category[category] = {"allowed": allowed, "limit": limit, "retry_after": retry_after}
            elif category == "tokens":
                per_min = int((pol.get("tokens") or {}).get("per_min") or 0)
                window = 60
                limit = per_min
                allowed = True
                retry_after = 0
                cat_fail = self._effective_fail_mode(pol, category)
                for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                    if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                        continue
                    key = self._keys.win(policy_id, category, sc, ev)
                    ok, ra = await self._allow_tokens_lua(key=key, limit=limit, window=window, units=units, now=now, fail_mode=cat_fail)
                    allowed = allowed and ok
                    retry_after = max(retry_after, ra)
                per_category[category] = {"allowed": allowed, "limit": limit, "retry_after": retry_after}
            elif category in ("streams", "jobs"):
                limit = int((pol.get(category) or {}).get("max_concurrent") or 0)
                ttl_sec = int((pol.get(category) or {}).get("ttl_sec") or 60)
                allowed = True
                retry_after = 0
                cat_fail = self._effective_fail_mode(pol, category)
                for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                    if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                        continue
                    key = self._keys.lease(policy_id, category, sc, ev)
                    try:
                        client = await self._client_get()
                        await client.zremrangebyscore(key, float("-inf"), now)
                        active = await client.zcard(key)
                        remaining = max(0, limit - active)
                        if remaining <= 0:
                            allowed = False
                            retry_after = max(retry_after, ttl_sec)
                    except Exception:
                        if cat_fail == "fail_open":
                            allowed = True
                        else:
                            allowed = False
                            retry_after = max(retry_after, ttl_sec)
                per_category[category] = {"allowed": allowed, "limit": limit, "retry_after": retry_after, "ttl_sec": ttl_sec}
            else:
                per_category[category] = {"allowed": True, "retry_after": 0}

            if overall_allowed and not per_category[category]["allowed"]:
                overall_allowed = False
            retry_after_overall = max(retry_after_overall, int(per_category[category].get("retry_after") or 0))

        # Record decision metric (summary per-category already emitted via caller ideally)
        return RGDecision(allowed=overall_allowed, retry_after=(retry_after_overall or None), details={"policy_id": policy_id, "categories": per_category})

    async def reserve(self, req: RGRequest, op_id: Optional[str] = None) -> Tuple[RGDecision, Optional[str]]:
        client = await self._client_get()
        if op_id:
            try:
                prev = await client.get(self._keys.op(op_id))
                if prev:
                    rec = json.loads(prev)
                    return RGDecision(**rec["decision"]), rec.get("handle_id")
            except Exception:
                pass

        dec = await self.check(req)
        if not dec.allowed:
            if op_id:
                try:
                    await client.set(self._keys.op(op_id), json.dumps({"type": "reserve", "decision": dec.__dict__, "handle_id": None}), ex=86400)
                except Exception:
                    pass
            return dec, None

        now = self._time()
        policy_id = dec.details.get("policy_id") or req.tags.get("policy_id") or "default"
        pol = self._get_policy(policy_id)
        entity_scope, entity_value = self._parse_entity(req.entity)
        handle_id = str(uuid.uuid4())

        # Concurrency: acquire leases (global and entity)
        for category, cfg in req.categories.items():
            if category in ("streams", "jobs"):
                ttl_sec = int((pol.get(category) or {}).get("ttl_sec") or 60)
                cat_fail = self._effective_fail_mode(pol, category)
                for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                    if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                        continue
                    key = self._keys.lease(policy_id, category, sc, ev)
                    try:
                        await client.zremrangebyscore(key, float("-inf"), now)
                        await client.zadd(key, {f"{handle_id}:{sc}:{ev}": now + ttl_sec})
                    except Exception as e:
                        if cat_fail == "fail_open":
                            pass
                        else:
                            logger.debug(f"lease add failed: {e}")

        # Persist handle
        try:
            await client.hset(
                self._keys.handle(handle_id),
                {
                    "entity": req.entity,
                    "policy_id": policy_id,
                    "categories": json.dumps({k: int((v or {}).get("units") or 0) for k, v in req.categories.items()}),
                    "created_at": str(now),
                },
            )
            await client.expire(self._keys.handle(handle_id), 86400)
        except Exception:
            pass
        # Also keep local map for best-effort release in tests / single-process
        self._local_handles[handle_id] = {
            "entity": req.entity,
            "policy_id": policy_id,
            "categories": {k: int((v or {}).get("units") or 0) for k, v in req.categories.items()},
        }

        if op_id:
            try:
                await client.set(self._keys.op(op_id), json.dumps({"type": "reserve", "decision": dec.__dict__, "handle_id": handle_id}), ex=86400)
            except Exception:
                pass
        return dec, handle_id

    async def commit(self, handle_id: str, actuals: Optional[Dict[str, int]] = None, op_id: Optional[str] = None) -> None:
        client = await self._client_get()
        try:
            hkey = self._keys.handle(handle_id)
            data = await client.hgetall(hkey)
            if not data:
                data = self._local_handles.get(handle_id) or {}
                if not data:
                    return
            policy_id = data.get("policy_id") or "default"
            entity = data.get("entity") or data.get("entity") or ""
            entity_scope, entity_value = self._parse_entity(entity)
            pol = self._get_policy(policy_id)
            cats_raw = data.get("categories")
            if isinstance(cats_raw, str):
                cats = json.loads(cats_raw or "{}")
            else:
                cats = dict(cats_raw or {})
            # Release concurrency leases for this handle
            now = self._time()
            for category in cats.keys():
                if category in ("streams", "jobs"):
                    cat_fail = self._effective_fail_mode(pol, category)
                    for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                        if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                            continue
                        key = self._keys.lease(policy_id, category, sc, ev)
                        # Remove leases for this handle
                        try:
                            await client.zrem(key, f"{handle_id}:{sc}:{ev}")
                        except Exception:
                            if cat_fail == "fail_open":
                                continue
                            # best-effort fallback: clear entire key if precise removal not supported
                            try:
                                await client.delete(key)
                            except Exception:
                                pass
            # Delete handle record
            try:
                await client.delete(hkey)
            except Exception:
                pass
            self._local_handles.pop(handle_id, None)
        except Exception as e:
            if self._fail_mode == "fail_open":
                return
            logger.debug(f"commit failed: {e}")
            return

        if op_id:
            try:
                await client.set(self._keys.op(op_id), json.dumps({"type": "commit", "handle_id": handle_id}), ex=86400)
            except Exception:
                pass

    async def refund(self, handle_id: str, deltas: Optional[Dict[str, int]] = None, op_id: Optional[str] = None) -> None:
        client = await self._client_get()
        try:
            # For Redis fixed-window counters, refunds are no-ops (counters only increase within window)
            await client.set(self._keys.op(op_id or f"refund:{handle_id}"), json.dumps({"type": "refund", "handle_id": handle_id}), ex=3600)
        except Exception:
            pass

    async def renew(self, handle_id: str, ttl_s: int) -> None:
        client = await self._client_get()
        try:
            hkey = self._keys.handle(handle_id)
            data = await client.hgetall(hkey)
            if not data:
                return
            policy_id = data.get("policy_id") or "default"
            entity = data.get("entity") or ""
            entity_scope, entity_value = self._parse_entity(entity)
            pol = self._get_policy(policy_id)
            cats = json.loads(data.get("categories") or "{}")
            now = self._time()
            for category in cats.keys():
                if category in ("streams", "jobs"):
                    for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                        if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                            continue
                        key = self._keys.lease(policy_id, category, sc, ev)
                        try:
                            await client.zadd(key, {f"{handle_id}:{sc}:{ev}": now + max(1, int(ttl_s))})
                        except Exception:
                            pass
        except Exception:
            pass

    async def release(self, handle_id: str) -> None:
        await self.commit(handle_id, actuals=None)

    async def peek(self, entity: str, categories: list[str]) -> Dict[str, Any]:
        # Minimal peek returning None; detailed usage tracking requires richer store
        return {c: {"remaining": None} for c in categories}

    async def query(self, entity: str, category: str) -> Dict[str, Any]:
        return {"detail": None}

    async def reset(self, entity: str, category: Optional[str] = None) -> None:
        # Not implemented in Redis backend for now
        return None
