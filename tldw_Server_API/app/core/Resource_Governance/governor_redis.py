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
        self._multi_lua_sha: Optional[str] = None
        self._last_used_tokens_lua: Optional[bool] = None
        self._last_used_multi_lua: Optional[bool] = None
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

    # --- Sliding window helpers (non-mutating and mutating) ---
    async def _purge_and_count(self, *, key: str, now: float, window: int) -> int:
        client = await self._client_get()
        try:
            await client.zremrangebyscore(key, float("-inf"), now - window)
        except Exception:
            # ignore purge errors; counting may still work or fail downstream
            pass
        try:
            return int(await client.zcard(key))
        except Exception:
            return 0

    async def _add_members(self, *, key: str, members: list[str], now: float) -> None:
        client = await self._client_get()
        try:
            await client.zadd(key, {m: now for m in members})
        except Exception:
            pass

    async def _zrem_members(self, *, key: str, members: list[str]) -> None:
        client = await self._client_get()
        for m in members:
            try:
                # best-effort removal
                await client.zrem(key, m)
            except Exception:
                pass

    async def _allow_requests_sliding_check_only(self, *, key: str, limit: int, window: int, units: int, now: float, fail_mode: str) -> Tuple[bool, int, int]:
        """Non-mutating check: returns (allowed, retry_after, current_count)."""
        try:
            count = await self._purge_and_count(key=key, now=now, window=window)
            if count + units <= limit:
                return True, 0, count
            # compute retry_after based on oldest item expiry within window
            # best-effort: approximate to full window if primitives not available
            ra = window
            try:
                client = await self._client_get()
                # Try to estimate oldest score
                rng = await client.evalsha(await self._ensure_tokens_lua(), 1, key, int(limit), int(window), float(now))
                # When window is full, eval returns [0, ra]
                if isinstance(rng, (list, tuple)) and len(rng) >= 2 and int(rng[0]) == 0:
                    ra = int(rng[1])
            except Exception:
                pass
            return False, int(ra), count
        except Exception:
            if fail_mode in ("fail_open", "fallback_memory"):
                return True, 0, 0
            return False, window, 0

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

    async def _ensure_multi_reserve_lua(self) -> Optional[str]:
        """
        Load a Lua script that atomically checks and inserts members across multiple keys.

        KEYS: [k1, k2, ...]
        ARGV: [now, key_count, (limit1, window1, units1, members_csv1), (limit2, window2, units2, members_csv2), ...]

        Returns: {1, 0} if all allowed and inserted, otherwise {0, max_retry_after}.

        Note: This is only used for real Redis; the in-memory stub cannot handle
        this shape, so callers must guard and fallback accordingly.
        """
        if self._multi_lua_sha:
            return self._multi_lua_sha
        client = await self._client_get()
        # Include ZRANGE/ZREMRANGEBYSCORE/ZSCORE to ensure broad compatibility;
        # stub recognition is not used here (we guard against stub outside).
        script = """
        local now = tonumber(ARGV[1])
        local kcount = tonumber(ARGV[2])
        local base = 3
        local max_ra = 0
        -- first pass: purge + check
        for i = 1, kcount do
          local key = KEYS[i]
          local limit = tonumber(ARGV[base]);
          local window = tonumber(ARGV[base+1]);
          local units = tonumber(ARGV[base+2]);
          -- purge expired
          redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
          local count = tonumber(redis.call('ZCARD', key))
          if count + units > limit then
            -- compute retry_after using oldest item
            local oldest = redis.call('ZRANGE', key, 0, 0)
            local oldest_score = now
            if oldest and #oldest > 0 then
              local os = redis.call('ZSCORE', key, oldest[1])
              if os then oldest_score = tonumber(os) end
            end
            local ra = math.max(0, math.floor(oldest_score + window - now))
            if ra <= 0 then ra = window end
            if ra > max_ra then max_ra = ra end
          end
          base = base + 4
        end
        if max_ra > 0 then
          return {0, max_ra}
        end
        -- second pass: insert provided members
        base = 3
        for i = 1, kcount do
          local key = KEYS[i]
          local limit = tonumber(ARGV[base]);
          local window = tonumber(ARGV[base+1]);
          local units = tonumber(ARGV[base+2]);
          local csv = ARGV[base+3]
          local inserted = 0
          for member in string.gmatch(csv or '', '([^,]+)') do
            if inserted >= units then break end
            redis.call('ZADD', key, now, member)
            inserted = inserted + 1
          end
          base = base + 4
        end
        return {1, 0}
        """
        try:
            sha = await client.script_load(script)
            self._multi_lua_sha = sha
            return sha
        except Exception:
            return None

    async def _is_real_redis(self) -> bool:
        try:
            client = await self._client_get()
            return client.__class__.__name__ != "InMemoryAsyncRedis"
        except Exception:
            return False

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
                    self._last_used_tokens_lua = True
                else:
                    # Fallback to simple sliding window using primitives
                    await client.zremrangebyscore(key, float("-inf"), now - window)
                    count = await client.zcard(key)
                    if count < limit:
                        await client.zadd(key, {f"{now}:{uuid.uuid4().hex}": now})
                        ok, ra = True, 0
                    else:
                        ok, ra = False, window
                    self._last_used_tokens_lua = False
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
                    ok, ra, _cnt = await self._allow_requests_sliding_check_only(key=key, limit=limit, window=window, units=units, now=now, fail_mode=cat_fail)
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
                    # Non-mutating: count + units <= limit; compute RA via lua helper if full
                    ok, ra, _cnt = await self._allow_requests_sliding_check_only(key=key, limit=limit, window=window, units=units, now=now, fail_mode=cat_fail)
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

        # First, try to atomically add request/token units across scopes; track members for rollback/refund
        added_members: Dict[str, Dict[Tuple[str, str], list[str]]] = {}
        add_failed = False
        used_lua = False

        # Attempt real-Redis multi-key Lua script when available
        try:
            if await self._is_real_redis():
                # Collect keys and ARGV for all request/token categories
                keys: list[str] = []
                argv: list[Any] = []
                # ARGV[1]=now, ARGV[2]=kcount; rest per-key quads
                now_f = float(now)
                # We'll build a temporary structure to also populate added_members on success
                tmp_members: list[Tuple[str, str, str, str, list[str]]] = []  # (category, sc, ev, key, members)
                for category, cfg in req.categories.items():
                    units = int(cfg.get("units") or 0)
                    if units <= 0:
                        continue
                    if category in ("requests", "tokens"):
                        limit = int((pol.get(category) or {}).get("rpm") or 0) if category == "requests" else int((pol.get(category) or {}).get("per_min") or 0)
                        window = 60
                        for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                            if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                                continue
                            key = self._keys.win(policy_id, category, sc, ev)
                            keys.append(key)
                            members = [f"{handle_id}:{sc}:{ev}:{i}:{uuid.uuid4().hex}" for i in range(units)]
                            tmp_members.append((category, sc, ev, key, members))
                            argv.extend([int(limit), int(window), int(units), ",".join(members)])
                if keys:
                    sha = await self._ensure_multi_reserve_lua()
                    if sha:
                        client = await self._client_get()
                        res = await client.evalsha(sha, len(keys), *keys, now_f, len(keys), *argv)
                        ok = bool(res and int(res[0]) == 1)
                        if ok:
                            used_lua = True
                            self._last_used_multi_lua = True
                            # Populate added_members from tmp_members
                            for category, sc, ev, key, members in tmp_members:
                                added_members.setdefault(category, {})[(sc, ev)] = list(members)
                        else:
                            add_failed = True
        except Exception:
            # fall through to Python fallback
            used_lua = False
            self._last_used_multi_lua = False
        if not used_lua:
            for category, cfg in req.categories.items():
                units = int(cfg.get("units") or 0)
                if units <= 0:
                    continue
                if category in ("requests", "tokens"):
                    limit = int((pol.get(category) or {}).get("rpm") or 0) if category == "requests" else int((pol.get(category) or {}).get("per_min") or 0)
                    window = 60
                    cat_fail = self._effective_fail_mode(pol, category)
                    added_members.setdefault(category, {})
                    for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                        if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                            continue
                        key = self._keys.win(policy_id, category, sc, ev)
                        # Ensure window cleanup
                        _ = await self._purge_and_count(key=key, now=now, window=window)
                        # Add members one by one to respect units and allow rollback
                        added_for_scope: list[str] = []
                        for i in range(units):
                            try:
                                cnt = await self._purge_and_count(key=key, now=now, window=window)
                                if cnt >= limit:
                                    add_failed = True
                                    break
                                member = f"{handle_id}:{sc}:{ev}:{i}:{uuid.uuid4().hex}"
                                await self._add_members(key=key, members=[member], now=now)
                                added_for_scope.append(member)
                            except Exception:
                                if cat_fail == "fail_open":
                                    continue
                                add_failed = True
                                break
                        added_members[category][(sc, ev)] = added_for_scope
                        if add_failed:
                            break
                    if add_failed:
                        break

        if add_failed:
            # Rollback any added members
            for category, scopes in added_members.items():
                for (sc, ev), mems in scopes.items():
                    key = self._keys.win(policy_id, category, sc, ev)
                    await self._zrem_members(key=key, members=mems)
            if op_id:
                try:
                    await client.set(self._keys.op(op_id), json.dumps({"type": "reserve", "decision": dec.__dict__, "handle_id": None}), ex=86400)
                except Exception:
                    pass
            return dec, None

        # Concurrency: acquire leases (global and entity) after rate counters
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
                    "members": json.dumps({
                        cat: {f"{sc}:{ev}": mems for (sc, ev), mems in scopes.items()} for cat, scopes in added_members.items()
                    }),
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
            "members": {cat: {f"{sc}:{ev}": mems for (sc, ev), mems in scopes.items()} for cat, scopes in added_members.items()},
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
            members_raw = data.get("members")
            try:
                members = json.loads(members_raw or "{}") if isinstance(members_raw, str) else (members_raw or {})
            except Exception:
                members = {}
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
            # Handle refunds for requests/tokens based on actuals
            try:
                actuals = actuals or {}
                for category, reserved in list(cats.items()):
                    if category not in ("requests", "tokens"):
                        continue
                    requested_actual = int(actuals.get(category, reserved))
                    requested_actual = max(0, min(requested_actual, reserved))
                    refund_units = max(0, reserved - requested_actual)
                    if refund_units <= 0:
                        continue
                    # Remove up to refund_units members per scope (LIFO of what we added)
                    scope_map = members.get(category) or {}
                    for key_scope, mem_list in scope_map.items():
                        try:
                            sc, ev = key_scope.split(":", 1)
                        except Exception:
                            continue
                        key = self._keys.win(policy_id, category, sc, ev)
                        # Pop last N members to reduce usage
                        to_remove = []
                        for _ in range(min(refund_units, len(mem_list))):
                            to_remove.append(str(mem_list.pop()))
                        await self._zrem_members(key=key, members=to_remove)
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
            hkey = self._keys.handle(handle_id)
            data = await client.hgetall(hkey)
            if not data:
                data = self._local_handles.get(handle_id) or {}
                if not data:
                    return
            policy_id = data.get("policy_id") or "default"
            members_raw = data.get("members")
            try:
                members = json.loads(members_raw or "{}") if isinstance(members_raw, str) else (members_raw or {})
            except Exception:
                members = {}
            deltas = deltas or {}
            for category, delta in deltas.items():
                if category not in ("requests", "tokens"):
                    continue
                units = max(0, int(delta))
                if units <= 0:
                    continue
                scope_map = members.get(category) or {}
                for key_scope, mem_list in scope_map.items():
                    try:
                        sc, ev = key_scope.split(":", 1)
                    except Exception:
                        continue
                    key = self._keys.win(policy_id, category, sc, ev)
                    to_remove = []
                    for _ in range(min(units, len(mem_list))):
                        to_remove.append(str(mem_list.pop()))
                    await self._zrem_members(key=key, members=to_remove)
            if op_id:
                await client.set(self._keys.op(op_id), json.dumps({"type": "refund", "handle_id": handle_id}), ex=3600)
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
        # Without policy context, we cannot compute limits; return None placeholders
        return {c: {"remaining": None, "reset": None} for c in categories}

    async def peek_with_policy(self, entity: str, categories: list[str], policy_id: str) -> Dict[str, Any]:
        pol = self._get_policy(policy_id)
        entity_scope, entity_value = self._parse_entity(entity)
        now = self._time()
        out: Dict[str, Any] = {}
        for category in categories:
            if category not in ("requests", "tokens"):
                out[category] = {"remaining": None, "reset": None}
                continue
            limit = int((pol.get(category) or {}).get("rpm") or 0) if category == "requests" else int((pol.get(category) or {}).get("per_min") or 0)
            window = 60
            remainings = []
            resets = []
            for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                    continue
                key = self._keys.win(policy_id, category, sc, ev)
                cnt = await self._purge_and_count(key=key, now=now, window=window)
                remainings.append(max(0, limit - cnt))
                if cnt >= limit:
                    # estimate reset via oldest expiry
                    try:
                        res = await self._ensure_tokens_lua()
                        if res:
                            pair = await (await self._client_get()).evalsha(res, 1, key, int(limit), int(window), float(now))
                            if isinstance(pair, (list, tuple)) and int(pair[0]) == 0:
                                resets.append(int(pair[1]))
                            else:
                                resets.append(window)
                        else:
                            resets.append(window)
                    except Exception:
                        resets.append(window)
                else:
                    resets.append(0)
            remaining = min(remainings) if remainings else None
            reset = max(resets) if resets else None
            out[category] = {"remaining": remaining, "reset": reset}
        return out

    async def query(self, entity: str, category: str) -> Dict[str, Any]:
        return {"detail": None}

    async def reset(self, entity: str, category: Optional[str] = None) -> None:
        # Not implemented in Redis backend for now
        return None

    async def capabilities(self) -> Dict[str, Any]:
        try:
            real = await self._is_real_redis()
        except Exception:
            real = False
        return {
            "backend": "redis",
            "real_redis": bool(real),
            "tokens_lua_loaded": bool(self._tokens_lua_sha),
            "multi_lua_loaded": bool(self._multi_lua_sha),
            "last_used_tokens_lua": bool(self._last_used_tokens_lua) if self._last_used_tokens_lua is not None else None,
            "last_used_multi_lua": bool(self._last_used_multi_lua) if self._last_used_multi_lua is not None else None,
        }
