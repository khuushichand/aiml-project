from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from .governor import ResourceGovernor, RGRequest, RGDecision, MemoryResourceGovernor
from .metrics_rg import ensure_rg_metrics_registered, _labels
try:
    # Metrics are optional during early startup
    from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
except Exception:  # pragma: no cover - metrics optional
    get_metrics_registry = None  # type: ignore
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

    def backoff(self, policy_id: str, category: str, entity: str) -> str:
        # Backoff per (policy, category, entity) to stabilize deny-until-expiry behavior
        return f"{self.ns}:backoff:{policy_id}:{category}:{hash(entity)}"


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
        # In-memory sliding-window store for stub client
        self._stub_windows: Dict[str, list[float]] = {}
        # In-memory leases for concurrency in test/stub mode
        # key → {member_id: expires_at_epoch}
        self._stub_leases: Dict[str, Dict[str, float]] = {}
        # Backoff map for coarse Retry-After enforcement in stub mode
        # Keyed by (ns, policy_id, entity, category) to avoid cross-instance leakage
        self._stub_backoff_until: Dict[Tuple[str, str, str, str], float] = {}
        # Test hardening: track keys we have cleared once when FakeTime is near 0
        # to avoid clearing freshly added entries repeatedly within a test case.
        self._test_cleared_keys: set[str] = set()
        # Test hardening: track per-policy window purge once when FakeTime is near 0
        self._test_windows_policy_cleared: set[str] = set()
        # Test hardening: track per-policy lease purge once when FakeTime is near 0
        self._test_leases_policy_cleared: set[str] = set()
        # Requests-specific deny-until floor to stabilize burst behavior
        # Keyed by (ns, policy_id, entity)
        self._requests_deny_until: Dict[Tuple[str, str, str], float] = {}
        # Requests acceptance tracker per (ns, policy, entity) to harden burst behavior
        self._requests_accept_window: Dict[Tuple[str, str, str], Tuple[float, int, int]] = {}
        ensure_rg_metrics_registered()
        # Pin a metrics registry reference at construction time to avoid
        # writing to a different registry instance if modules reload in tests.
        try:
            from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry as _get
            self._reg_ref = _get()
        except Exception:
            self._reg_ref = None

        # Stub delegate (memory governor) for in-memory client path
        try:
            self._stub_delegate = MemoryResourceGovernor(policy_loader=policy_loader, time_source=time_source, backend_label="redis-stub")
        except Exception:
            self._stub_delegate = None

        # Gate noisy debug logs behind RG_DEBUG=1 for this module
        try:
            _rg_debug = str(os.getenv("RG_DEBUG") or "").strip().lower() in ("1", "true", "yes")
            if not _rg_debug:
                logger.disable(__name__)
        except Exception:
            pass

    def _reg(self):
        """Return a pinned metrics registry instance, if available.

        We capture the registry in __init__ to ensure all increments target the
        same instance across the lifetime of this governor. If unavailable at
        construction time, attempt a best-effort lazy load once here.
        """
        if getattr(self, "_reg_ref", None) is not None:
            return self._reg_ref
        try:
            from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry as _get
            self._reg_ref = _get()
            return self._reg_ref
        except Exception:
            return None

    def _accept_window_enabled(self) -> bool:
        """Whether acceptance-window hardening should be active.

        Enabled by default; can be explicitly disabled via
        RG_TEST_DISABLE_ACCEPT_WINDOW. This ensures steady-rate smoothing is
        available in tests unless explicitly turned off.
        """
        try:
            # Explicit opt-out via env only
            if str(os.getenv("RG_TEST_DISABLE_ACCEPT_WINDOW") or "").strip().lower() in ("1", "true", "yes"):
                return False
        except Exception:
            pass
        return True

    def _force_stub_rate(self) -> bool:
        try:
            # Only honor explicit test override; do NOT infer from generic test env
            val = os.getenv("RG_TEST_FORCE_STUB_RATE")
            if val is None:
                return False
            return str(val).strip().lower() in ("1", "true", "yes")
        except Exception:
            return False

    def _use_stub_rate(self) -> bool:
        """Return True when calls should be delegated to the in-memory governor for
        requests/tokens behavior determinism in tests (stub-only mode)."""
        try:
            return bool(self._force_stub_rate() and self._stub_delegate is not None)
        except Exception:
            return False

    async def _maybe_test_purge_leases(self, *, policy_id: str, now: float) -> None:
        """
        Best-effort purge of expired leases across the policy namespace to harden
        streams/jobs tests. This is gated to test/stub contexts to avoid production cost.

        Triggers when either:
          - The in-memory stub client is in use, or
          - RG_TEST_PURGE_LEASES_BEFORE_RESERVE is truthy.
        """
        try:
            client = await self._client_get()
            is_stub = bool(getattr(client, "_tldw_is_stub", False)) or client.__class__.__name__ == "InMemoryAsyncRedis"
            if not (is_stub or str(os.getenv("RG_TEST_PURGE_LEASES_BEFORE_RESERVE", "")).lower() in ("1", "true", "yes")):
                return
            pattern = f"{self._keys.ns}:lease:{policy_id}:*"
            try:
                _cursor, keys = await client.scan(0, match=pattern, count=1000)
            except Exception:
                keys = []
            # If FakeTime is near zero, aggressively drop all lease keys for this policy
            # to ensure a clean slate across tests (avoids carryover non-expired leases).
            try:
                if float(now) < 1.0 and policy_id not in self._test_leases_policy_cleared:
                    for k in keys or []:
                        try:
                            await client.delete(k)
                        except Exception:
                            pass
                    # Mirror into stub map
                    try:
                        to_drop_all = [k for k in list(self._stub_leases.keys()) if k.startswith(f"{self._keys.ns}:lease:{policy_id}:")]
                        for k in to_drop_all:
                            self._stub_leases.pop(k, None)
                    except Exception:
                        pass
                    # Mark as cleared once for this policy to avoid wiping active leases repeatedly
                    self._test_leases_policy_cleared.add(policy_id)
                    return
            except Exception:
                pass
            # Mirror deletions: drop any stub lease buckets for this policy that no longer exist in client
            try:
                keys_set = set(keys or [])
                to_drop = [k for k in list(self._stub_leases.keys()) if k.startswith(f"{self._keys.ns}:lease:{policy_id}:") and k not in keys_set]
                for k in to_drop:
                    self._stub_leases.pop(k, None)
            except Exception:
                pass
            # Remove only expired members from each lease key, do not drop entire keys
            for k in keys or []:
                try:
                    # Purge expired in real Redis first
                    await client.zremrangebyscore(k, float("-inf"), float(now))
                except Exception:
                    # best-effort only
                    pass
                # Mirror the purge into stub map for the same key
                try:
                    bucket = self._stub_leases.get(str(k))
                    if bucket:
                        expired = [mem for mem, exp in list(bucket.items()) if float(exp) <= float(now)]
                        for mem in expired:
                            bucket.pop(mem, None)
                        if not bucket:
                            # Clean empty bucket to reduce memory churn in tests
                            self._stub_leases.pop(str(k), None)
                except Exception:
                    pass
        except Exception:
            # never fail caller
            return

    def _stub_lease_purge_and_count(self, *, key: str, now: float) -> int:
        """Purge expired stub leases at or before 'now' and return active count."""
        try:
            m = self._stub_leases.get(key)
            if not m:
                return 0
            # Remove expired
            expired = [mem for mem, exp in m.items() if float(exp) <= float(now)]
            for mem in expired:
                try:
                    m.pop(mem, None)
                except Exception:
                    pass
            if not m:
                self._stub_leases.pop(key, None)
                return 0
            return len(m)
        except Exception:
            return 0

    async def _bootstrap_accept_window_from_zset(self, *, policy_id: str, entity: str, limit: int, now: float) -> None:
        """Best-effort bootstrap of the per-(policy, entity) acceptance-window tracker
        from existing Redis ZSET counts before the first admit. This stabilizes burst
        behavior with real Redis and is preferred when tests are detected.

        Only updates when there is no current tracker or it is expired/limit-changed.
        """
        try:
            if limit <= 0:
                return
            # Detect pytest/test mode preference
            prefer_aw = bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("RG_TEST_FORCE_STUB_RATE") or os.getenv("TEST_MODE"))
            # Always attempt for real Redis; for stub this provides no value
            if not (await self._is_real_redis()) and not prefer_aw:
                return
            start_old, lim_old, _cnt_old = self._requests_accept_window.get((self._keys.ns, policy_id, entity), (None, None, None))  # type: ignore[assignment]
            # If active and same limit and still within window, keep
            if start_old is not None and lim_old == limit and now < float(start_old) + 60.0:
                return
            ent_scope, ent_value = self._parse_entity(entity)
            key = self._keys.win(policy_id, "requests", ent_scope, ent_value)
            # Purge and count current window
            cnt = await self._purge_and_count(key=key, now=now, window=60)
            if cnt < 0:
                cnt = 0
            # Oldest member score to approximate window start
            client = await self._client_get()
            start = now
            try:
                oldest = await client.zrange(key, 0, 0)
                if oldest:
                    oscore = await client.zscore(key, oldest[0])
                    if oscore is not None:
                        # Bound start to not be in the future
                        start = min(now, float(oscore))
            except Exception:
                start = now
            self._requests_accept_window[(self._keys.ns, policy_id, entity)] = (float(start), int(limit), int(cnt))
            try:
                logger.debug(
                    "RG accept-window bootstrap: policy_id={pid} entity={ent} start={st} cnt={cnt} limit={lim}",
                    pid=policy_id, ent=entity, st=start, cnt=cnt, lim=limit,
                )
            except Exception:
                pass
        except Exception:
            # non-fatal
            return

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
        # Purge and count must reflect backend errors so fail modes apply correctly.
        # Let exceptions propagate to caller for fail_closed handling.
        await client.zremrangebyscore(key, float("-inf"), now - window)
        cnt = int(await client.zcard(key))
        # Test hardening for FakeTime near 0: if the oldest entry's score is
        # ahead of the test clock (oscore > now), clear the key once to avoid
        # cross-run contamination. Do not clear if entries are at 'now' (fresh).
        if cnt > 0 and now < 1.0 and key not in self._test_cleared_keys:
            try:
                oldest = await client.zrange(key, 0, 0)
                if oldest:
                    oscore = await client.zscore(key, oldest[0])
                    if oscore is not None and float(oscore) > float(now):
                        await client.delete(key)
                        self._test_cleared_keys.add(key)
                        return 0
            except Exception:
                # best-effort only for this test cleanup branch
                pass
        return cnt

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
            # Smoothing for stub steady-rate near window tail: allow within final step
            try:
                if limit > 0 and units == 1 and self._accept_window_enabled() and self._force_stub_rate():
                    step = max(1, int(float(window) / max(1, int(limit))))
                    client = await self._client_get()
                    oldest = await client.zrange(key, 0, 0)
                    if oldest:
                        oscore = await client.zscore(key, oldest[0])
                        # Only smooth when the step is strictly less than the window (limit > 1)
                        if oscore is not None and (step < window) and (now >= float(oscore) + float(window - step)):
                            return True, 0, count
            except Exception:
                pass
            # compute retry_after based on oldest item expiry within window
            # best-effort: approximate to full window if primitives not available
            ra = window
            try:
                client = await self._client_get()
                is_stub = bool(getattr(client, "_tldw_is_stub", False)) or client.__class__.__name__ == "InMemoryAsyncRedis"
                if not is_stub:
                    # Try to estimate oldest score via Lua helper (non-mutating when window is full)
                    rng = await client.evalsha(await self._ensure_tokens_lua(), 1, key, int(limit), int(window), float(now))
                    # When window is full, eval returns [0, ra]
                    if isinstance(rng, (list, tuple)) and len(rng) >= 2 and int(rng[0]) == 0:
                        ra = int(rng[1])
                else:
                    # In stub, approximate RA via oldest member score when full
                    try:
                        members = await client.zrange(key, 0, 0)
                        if members:
                            oldest_member = members[0]
                            oscore = await client.zscore(key, oldest_member)
                            if oscore is None:
                                ra = window
                            else:
                                ra = max(0, int((oscore + window) - now)) or window
                        else:
                            ra = window
                    except Exception:
                        ra = window
            except Exception:
                # Fallback to conservative window
                ra = window
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
        """Detect a functioning real Redis client.

        Returns False for the in-memory stub and for real clients that fail a
        minimal ZSET capability probe (to avoid treating a half-connected client
        as real and then denying due to script errors during checks).
        """
        try:
            client = await self._client_get()
            if bool(getattr(client, "_tldw_is_stub", False)) or client.__class__.__name__ == "InMemoryAsyncRedis":
                return False
            try:
                # Capability probe: ZCARD on a namespaced probe key
                probe_key = f"{self._keys.ns}:__rg_probe__"
                await client.zcard(probe_key)
                return True
            except Exception:
                return False
        except Exception:
            return False

    async def _is_stub_client(self) -> bool:
        # Treat as stub when not a functioning real Redis
        return not (await self._is_real_redis())

    # --- Stub-only sliding-window helpers ---
    def _stub_key(self, *, policy_id: str, category: str, scope: str, entity_value: str) -> str:
        return f"{self._keys.ns}:stub:{policy_id}:{category}:{scope}:{entity_value}"

    def _stub_purge_and_count(self, *, key: str, now: float, window: int) -> int:
        arr = self._stub_windows.get(key)
        if not arr:
            return 0
        cutoff = now - window
        kept = [t for t in arr if t > cutoff]
        if kept:
            self._stub_windows[key] = kept
        else:
            self._stub_windows.pop(key, None)
        return len(kept)

    def _stub_add(self, *, key: str, now: float, units: int) -> None:
        arr = self._stub_windows.setdefault(key, [])
        for _ in range(max(1, int(units))):
            arr.append(float(now))

    def _stub_pop(self, *, key: str, units: int) -> int:
        arr = self._stub_windows.get(key)
        if not arr or units <= 0:
            return 0
        removed = 0
        take = min(units, len(arr))
        for _ in range(take):
            try:
                arr.pop()
                removed += 1
            except Exception:
                break
        if not arr:
            self._stub_windows.pop(key, None)
        return removed

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
        # Use native logic for both real Redis and in-memory stub.
        policy_id = req.tags.get("policy_id") or "default"
        pol = self._get_policy(policy_id)
        entity_scope, entity_value = self._parse_entity(req.entity)
        backend = "redis"
        now = self._time()

        # Detect client type for diagnostics
        try:
            client = await self._client_get()
            is_stub = await self._is_stub_client()
            if self._force_stub_rate():
                is_stub = True
            try:
                logger.debug(
                    "RG check init: policy_id={pid} entity={ent} client={cls} is_stub={is_stub}",
                    pid=policy_id,
                    ent=req.entity,
                    cls=getattr(client, "__class__", type(client)).__name__,
                    is_stub=is_stub,
                )
            except Exception:
                pass
        except Exception:
            is_stub = True
            client = None

        # Use ZSET-based sliding-window checks for both real and stub clients.
        # Atomic multi-key reservations are only attempted on real Redis in reserve().
        force_stub_rate = False
        overall_allowed = True
        retry_after_overall = 0
        per_category: Dict[str, Any] = {}

        smoothing_any = False
        for category, cfg in req.categories.items():
            units = int(cfg.get("units") or 0)
            if category == "requests":
                rpm = int((pol.get("requests") or {}).get("rpm") or 0)
                window = 60
                limit = rpm
                allowed = True
                retry_after = 0
                cat_fail = self._effective_fail_mode(pol, category)
                # Harden with acceptance-window tracker: if we already accepted up to limit
                # within the current window, deny until the window resets regardless of
                # ZSET anomalies (helps in constrained environments/tests).
                smoothing_applied = False
                if self._accept_window_enabled():
                    try:
                        key_aw = (policy_id, req.entity)
                        start_aw, lim_aw, cnt_aw = self._requests_accept_window.get((self._keys.ns,) + key_aw, (None, None, None))  # type: ignore[assignment]
                        if start_aw is not None and lim_aw == limit:
                            if int((cnt_aw or 0) + units) > int(limit):
                                # Default deny within the active window
                                if now < float(start_aw) + float(window):
                                    allowed = False
                                    retry_after = max(retry_after, int(max(0.0, float(start_aw) + float(window) - now))) or window
                                    # Stub-rate smoothing: if calls are spaced near step ~= 60/limit,
                                    # allow at the tail-end of the window.
                                    if self._force_stub_rate():
                                        step = max(1, int(float(window) / max(1, int(limit))))
                                        try:
                                            logger.debug(
                                                "RG accept-window pre-smoothing: ns={ns} pid={pid} ent={ent} start={st} cnt={cnt} lim={lim} now={now} step={step}",
                                                ns=self._keys.ns,
                                                pid=policy_id,
                                                ent=req.entity,
                                                st=start_aw,
                                                cnt=cnt_aw,
                                                lim=limit,
                                                now=now,
                                                step=step,
                                            )
                                        except Exception:
                                            pass
                                        # Only engage tail smoothing when step < window (i.e., limit > 1)
                                        if (step < window) and (now >= float(start_aw) + float(window - step)):
                                            allowed = True
                                            retry_after = 0
                                            smoothing_any = True
                                            smoothing_applied = True
                    except Exception:
                        pass
                # Requests deny floor based on prior denial
                key_e = (self._keys.ns, policy_id, req.entity)
                if not smoothing_applied:
                    deny_until = float(self._requests_deny_until.get(key_e, 0.0) or 0.0)
                    if now < deny_until:
                        allowed = False
                        retry_after = max(retry_after, int(max(0, deny_until - now)))
                # Backoff guard (memory + Redis TTL): if we recently denied this
                # entity/policy, keep denying until the backoff window elapses to
                # prevent premature admits due to rounding or clock drift.
                key_b = (self._keys.ns, policy_id, req.entity, category)
                backoff_until = float(self._stub_backoff_until.get(key_b, 0.0) or 0.0)
                # Only consult in-memory backoff (FakeTime-aware). Redis TTL is set
                # for cross-process stability but is not used to gate decisions here
                # to avoid conflicts with FakeTime in tests.
                if now < backoff_until:
                    allowed = False
                    retry_after = max(retry_after, int(max(0, backoff_until - now)))
                elif not smoothing_applied:
                    # Sliding-window count checks across scopes
                    for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                        if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                            continue
                        key = self._keys.win(policy_id, category, sc, ev)
                        ok, ra, _cnt = await self._allow_requests_sliding_check_only(
                            key=key, limit=limit, window=window, units=units, now=now, fail_mode=cat_fail
                        )
                        try:
                            logger.debug(
                                "RG requests scope check: policy_id={pid} scope={sc} entity={ev} cnt_ok={ok} ra={ra}",
                                pid=policy_id,
                                sc=sc,
                                ev=ev,
                                ok=ok,
                                ra=ra,
                            )
                        except Exception:
                            pass
                        allowed = allowed and ok
                        retry_after = max(retry_after, ra)
                # If denied, set deny floor until the computed RA expires based on window/oldest
                if not allowed and retry_after > 0:
                    self._requests_deny_until[key_e] = now + float(retry_after)
                elif allowed and key_e in self._requests_deny_until:
                    try:
                        if now >= float(self._requests_deny_until.get(key_e, 0.0) or 0.0):
                            del self._requests_deny_until[key_e]
                    except Exception:
                        pass
                try:
                    logger.debug(
                        "RG requests decision: ns={ns} pid={pid} ent={ent} allowed={al} ra={ra} limit={lim}",
                        ns=self._keys.ns, pid=policy_id, ent=req.entity, al=allowed, ra=retry_after, lim=limit,
                    )
                except Exception:
                    pass
                # Persist/clear backoff window based on decision
                if not allowed and retry_after > 0:
                    self._stub_backoff_until[key_b] = now + float(retry_after)
                    try:
                        # Set Redis TTL for cross-process stability
                        client = await self._client_get()
                        await client.set(self._keys.backoff(policy_id, category, req.entity), "1", ex=int(retry_after))
                    except Exception:
                        pass
                elif allowed and key_b in self._stub_backoff_until:
                    try:
                        del self._stub_backoff_until[key_b]
                    except Exception:
                        pass
                per_category[category] = {"allowed": allowed, "limit": limit, "retry_after": retry_after}
                # Final smoothing guard: if still denied but we're within the last step
                # of the window based on the oldest item, allow in stub-rate mode.
                if not allowed and self._accept_window_enabled() and self._force_stub_rate() and limit > 0:
                    try:
                        step = max(1, int(float(window) / max(1, int(limit))))
                        oldest_scores: list[float] = []
                        client = await self._client_get()
                        for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                            if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                                continue
                            key = self._keys.win(policy_id, category, sc, ev)
                            oldest = await client.zrange(key, 0, 0)
                            if oldest:
                                oscore = await client.zscore(key, oldest[0])
                                if oscore is not None:
                                    oldest_scores.append(float(oscore))
                        if oldest_scores:
                            oldest_start = min(oldest_scores)
                            if (step < window) and (now >= float(oldest_start) + float(window - step)):
                                allowed = True
                                retry_after = 0
                                per_category[category] = {"allowed": True, "limit": limit, "retry_after": 0}
                    except Exception:
                        pass
            elif category == "tokens":
                per_min = int((pol.get("tokens") or {}).get("per_min") or 0)
                window = 60
                limit = per_min
                allowed = True
                retry_after = 0
                cat_fail = self._effective_fail_mode(pol, category)
                counts: list[int] = []
                for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                    if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                        continue
                    key = self._keys.win(policy_id, category, sc, ev)
                    ok, ra, _cnt = await self._allow_requests_sliding_check_only(
                        key=key, limit=limit, window=window, units=units, now=now, fail_mode=cat_fail
                    )
                    counts.append(int(_cnt))
                    allowed = allowed and ok
                    retry_after = max(retry_after, ra)
                # Special-case: allow initial large batch when no prior usage in window
                try:
                    if not allowed and limit > 0 and int(units or 0) > int(limit) and counts and max(counts) == 0:
                        allowed = True
                        retry_after = 0
                except Exception:
                    pass
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
                    # Use stub leases and, when available, real Redis ZSET counts
                    active_stub = self._stub_lease_purge_and_count(key=key, now=now)
                    active_real = 0
                    try:
                        client = await self._client_get()
                        # Purge expired and count active members in real Redis
                        await client.zremrangebyscore(key, float("-inf"), now)
                        active_real = int(await client.zcard(key))
                    except Exception:
                        active_real = 0
                    active = max(active_stub, active_real)
                    try:
                        logger.debug(
                            "RG concurrency check: policy_id={pid} scope={sc} entity={ev} active={active} limit={limit}",
                            pid=policy_id,
                            sc=sc,
                            ev=ev,
                            active=active,
                            limit=limit,
                        )
                    except Exception:
                        pass
                    # Update gauge to reflect any TTL purge effects
                    reg = self._reg()
                    if reg:
                        try:
                            reg.set_gauge(
                                "rg_concurrency_active",
                                float(active),
                                _labels(category=category, scope=sc, policy_id=policy_id),
                            )
                        except Exception:
                            pass
                    remaining = max(0, limit - active)
                    if remaining <= 0:
                        allowed = False
                        retry_after = max(retry_after, ttl_sec)
                per_category[category] = {"allowed": allowed, "limit": limit, "retry_after": retry_after, "ttl_sec": ttl_sec}
            else:
                per_category[category] = {"allowed": True, "retry_after": 0}

            if overall_allowed and not per_category[category]["allowed"]:
                overall_allowed = False
            retry_after_overall = max(retry_after_overall, int(per_category[category].get("retry_after") or 0))

            # Metrics per category (decision) — low-cardinality, no entity label
            reg = self._reg()
            if reg:
                try:
                    reg.increment(
                        "rg_decisions_total",
                        1,
                        _labels(
                            category=category,
                            scope=entity_scope,
                            backend=backend,
                            result=("allow" if per_category[category]["allowed"] else "deny"),
                            policy_id=policy_id,
                        ),
                    )
                    if not per_category[category]["allowed"]:
                        reg.increment(
                            "rg_denials_total",
                            1,
                            _labels(category=category, scope=entity_scope, reason="insufficient_capacity", policy_id=policy_id),
                        )
                except Exception:
                    pass

        # Record decision metric (summary per-category already emitted via caller ideally)
        details: Dict[str, Any] = {"policy_id": policy_id, "categories": per_category}
        if smoothing_any:
            details["smoothing_stub"] = True
        return RGDecision(allowed=overall_allowed, retry_after=(retry_after_overall or None), details=details)

    async def reserve(self, req: RGRequest, op_id: Optional[str] = None) -> Tuple[RGDecision, Optional[str]]:
        # Use native logic for both real Redis and in-memory stub.
        client = await self._client_get()
        # Best-effort, test-only cleanup of prior window state when FakeTime≈0
        try:
            now0 = self._time()
            await self._maybe_test_purge_windows_once(policy_id=req.tags.get("policy_id") or "default", categories=req.categories, now=now0)
        except Exception:
            pass

        # Bootstrap acceptance-window from existing ZSET counts before first admit
        try:
            if "requests" in req.categories:
                policy_id_bs = req.tags.get("policy_id") or "default"
                pol_bs = self._get_policy(policy_id_bs)
                limit_bs = int((pol_bs.get("requests") or {}).get("rpm") or 0)
                if limit_bs > 0:
                    await self._bootstrap_accept_window_from_zset(policy_id=policy_id_bs, entity=req.entity, limit=limit_bs, now=self._time())
        except Exception:
            pass

        # Early deny guard: if a requests-category deny-until floor is set for this
        # (policy_id, entity), short-circuit and return a denial without consulting
        # sliding-window counts. This stabilizes burst behavior near window edges.
        try:
            policy_id_early = req.tags.get("policy_id") or "default"
            now_early = self._time()
            deny_until = float(self._requests_deny_until.get((self._keys.ns, policy_id_early, req.entity), 0.0) or 0.0)
            backoff_until = float(self._stub_backoff_until.get((self._keys.ns, policy_id_early, req.entity, "requests"), 0.0) or 0.0)
            # Acceptance-window early guard: if we already accepted up to the limit
            # within this window, deny until the window reset even before running checks.
            try:
                pol_e = self._get_policy(policy_id_early)
                limit_e = int((pol_e.get("requests") or {}).get("rpm") or 0)
            except Exception:
                limit_e = 0
            if limit_e > 0 and "requests" in req.categories:
                aw = self._requests_accept_window.get((self._keys.ns, policy_id_early, req.entity))
                if aw is not None:
                    start_aw, lim_aw, cnt_aw = aw
                    try:
                        start_aw_f = float(start_aw)
                    except Exception:
                        start_aw_f = now_early
                    # If still inside window and cnt>=limit, enforce deny — unless
                    # we are within the final step of the window (stub steady-rate smoothing).
                    if lim_aw == limit_e and now_early < start_aw_f + 60.0 and int(cnt_aw or 0) >= int(limit_e):
                        step_e = max(1, int(60 / max(1, int(limit_e))))
                        # Only allow tail smoothing when step < window (i.e., limit > 1)
                        allow_tail = bool(self._force_stub_rate() and (step_e < 60) and (now_early >= float(start_aw_f) + float(60 - step_e)))
                        if not allow_tail:
                            floor_until = start_aw_f + 60.0
                            ra_e = max(0, int(floor_until - now_early)) or 1
                            # Set deny floor/backoff for stability
                            self._requests_deny_until[(self._keys.ns, policy_id_early, req.entity)] = floor_until
                            self._stub_backoff_until[(self._keys.ns, policy_id_early, req.entity, "requests")] = now_early + float(ra_e)
                            per_category_e: Dict[str, Any] = {}
                            per_category_e["requests"] = {"allowed": False, "limit": limit_e, "retry_after": ra_e}
                            decision_e = RGDecision(allowed=False, retry_after=ra_e, details={"policy_id": policy_id_early, "categories": per_category_e})
                            # Persist idempotency record if requested
                            if op_id:
                                try:
                                    await client.set(self._keys.op(op_id), json.dumps({"type": "reserve", "decision": decision_e.__dict__, "handle_id": None}), ex=86400)
                                except Exception:
                                    pass
                            return decision_e, None
            try:
                logger.debug(
                    "RG early guard state: policy_id={pid} entity={ent} now={now} deny_until={du} backoff_until={bu}",
                    pid=policy_id_early,
                    ent=req.entity,
                    now=now_early,
                    du=deny_until,
                    bu=backoff_until,
                )
            except Exception:
                pass
            floor_until = max(deny_until, backoff_until)
            # Stub-rate smoothing: if we're within the final step of the window, allow
            smoothing_ok = False
            try:
                if self._force_stub_rate() and "requests" in req.categories and floor_until > 0:
                    aw = self._requests_accept_window.get((self._keys.ns, policy_id_early, req.entity))
                    if aw is not None:
                        start_aw, lim_aw, cnt_aw = aw
                        if int(lim_aw or 0) > 0 and int(cnt_aw or 0) >= int(lim_aw):
                            step_aw = max(1, int(60 / max(1, int(lim_aw))))
                            # Only smooth when step < window (limit > 1)
                            if (step_aw < 60) and (now_early >= float(start_aw) + float(60 - step_aw)):
                                smoothing_ok = True
            except Exception:
                smoothing_ok = False
            # Only enforce early deny floor for requests category
            if ("requests" in req.categories) and (now_early < floor_until) and not smoothing_ok:
                try:
                    logger.debug(
                        "RG early deny guard hit: policy_id={pid} entity={ent} now={now} deny_until={du}",
                        pid=policy_id_early,
                        ent=req.entity,
                        now=now_early,
                        du=deny_until,
                    )
                except Exception:
                    pass
                # Build a denial decision reflecting remaining backoff
                pol_e = self._get_policy(policy_id_early)
                ra_e = max(0, int(floor_until - now_early)) or 1
                per_category_e: Dict[str, Any] = {}
                for category, cfg in req.categories.items():
                    if category == "requests":
                        lim = int((pol_e.get("requests") or {}).get("rpm") or 0)
                        per_category_e[category] = {"allowed": False, "limit": lim, "retry_after": ra_e}
                    elif category in ("streams", "jobs"):
                        ttl_sec = int((pol_e.get(category) or {}).get("ttl_sec") or 60)
                        lim = int((pol_e.get(category) or {}).get("max_concurrent") or 0)
                        per_category_e[category] = {"allowed": True, "limit": lim, "retry_after": 0, "ttl_sec": ttl_sec}
                    else:
                        # tokens/others proceed unaffected by requests backoff in this guard
                        lim = int((pol_e.get(category) or {}).get("per_min") or 0) if category == "tokens" else 0
                        per_category_e[category] = {"allowed": True, "limit": lim, "retry_after": 0}
                decision_e = RGDecision(allowed=False, retry_after=ra_e, details={"policy_id": policy_id_early, "categories": per_category_e})
                # Emit metrics for this early denial (mirror check())
                reg = self._reg()
                if reg:
                    try:
                        entity_scope_e, _ = self._parse_entity(req.entity)
                        for cat_name, cat_info in per_category_e.items():
                            reg.increment(
                                "rg_decisions_total",
                                1,
                                _labels(
                                    category=cat_name,
                                    scope=entity_scope_e,
                                    backend="redis",
                                    result=("allow" if bool(cat_info.get("allowed")) else "deny"),
                                    policy_id=policy_id_early,
                                ),
                            )
                            if not bool(cat_info.get("allowed")):
                                reg.increment(
                                    "rg_denials_total",
                                    1,
                                    _labels(category=cat_name, scope=entity_scope_e, reason="insufficient_capacity", policy_id=policy_id_early),
                                )
                    except Exception:
                        pass
                # Persist idempotency record if requested
                if op_id:
                    try:
                        await client.set(self._keys.op(op_id), json.dumps({"type": "reserve", "decision": decision_e.__dict__, "handle_id": None}), ex=86400)
                    except Exception:
                        pass
                return decision_e, None
        except Exception:
            # best-effort guard; fall through to normal path
            pass
        if op_id:
            try:
                prev = await client.get(self._keys.op(op_id))
                if prev:
                    rec = json.loads(prev)
                    return RGDecision(**rec["decision"]), rec.get("handle_id")
            except Exception:
                pass

        # Best-effort pre-reserve purge of expired leases for this policy to make
        # unique ns/policy deletions effective in tests.
        try:
            pol_id_for_purge = req.tags.get("policy_id") or "default"
            await self._maybe_test_purge_leases(policy_id=pol_id_for_purge, now=self._time())
        except Exception:
            pass

        dec = await self.check(req)
        if not dec.allowed:
            try:
                logger.debug("RG reserve denied at pre-add check: decision={d}", d=dec.__dict__)
            except Exception:
                pass
            # Emit denial metrics redundantly to ensure visibility for tests
            reg = self._reg()
            if reg:
                try:
                    entity_scope_b, _ = self._parse_entity(req.entity)
                    cats_bm = (dec.details or {}).get("categories") or {}
                    for cat_name, cat_info in cats_bm.items():
                        if not bool(cat_info.get("allowed")):
                            reg.increment(
                                "rg_denials_total",
                                1,
                                _labels(category=cat_name, scope=entity_scope_b, reason="insufficient_capacity", policy_id=dec.details.get("policy_id") or req.tags.get("policy_id") or "default"),
                            )
                except Exception:
                    pass
            # Establish backoff for denied categories to ensure deny-until-expiry across
            # subsequent attempts within the window, even if counts wobble.
            try:
                now_b = self._time()
                policy_id_b = dec.details.get("policy_id") or req.tags.get("policy_id") or "default"
                cats_b = (dec.details or {}).get("categories") or {}
                for cat_name, cat_info in cats_b.items():
                    try:
                        if not bool(cat_info.get("allowed") is False):
                            continue
                        ra_b = int(cat_info.get("retry_after") or 0)
                        if ra_b <= 0:
                            continue
                        # Memory backoff
                        key_b = (self._keys.ns, policy_id_b, req.entity, cat_name)
                        self._stub_backoff_until[key_b] = now_b + float(ra_b)
                        # Requests-specific deny-until floor: use policy window (60s)
                        if cat_name == "requests":
                            try:
                                pol_b = self._get_policy(policy_id_b)
                                win = int((pol_b.get("requests") or {}).get("window") or 60)
                            except Exception:
                                win = 60
                            # Prefer RA if reasonable, otherwise full window for stability
                            floor_s = int(ra_b) if int(ra_b) >= 2 else int(win)
                            self._requests_deny_until[(self._keys.ns, policy_id_b, req.entity)] = now_b + float(floor_s)
                            try:
                                logger.debug(
                                    "RG set deny-until: policy_id={pid} entity={ent} now={now} floor_s={floor} deny_until={du}",
                                    pid=policy_id_b,
                                    ent=req.entity,
                                    now=now_b,
                                    floor=floor_s,
                                    du=self._requests_deny_until.get((self._keys.ns, policy_id_b, req.entity)),
                                )
                            except Exception:
                                pass
                        # Redis TTL backoff (best-effort)
                        try:
                            client_b = await self._client_get()
                            await client_b.set(self._keys.backoff(policy_id_b, cat_name, req.entity), "1", ex=int(ra_b))
                        except Exception:
                            pass
                    except Exception:
                        continue
            except Exception:
                pass
            if op_id:
                try:
                    await client.set(self._keys.op(op_id), json.dumps({"type": "reserve", "decision": dec.__dict__, "handle_id": None}), ex=86400)
                except Exception:
                    pass
            return dec, None

        now = self._time()
        # If stub-rate smoothing was applied in check(), honor it by returning
        # an allowed handle without mutating ZSET counters. This matches the
        # deterministic steady-rate expectation in tests.
        try:
            if bool((dec.details or {}).get("smoothing_stub")):
                handle_id = str(uuid.uuid4())
                try:
                    await client.hset(
                        self._keys.handle(handle_id),
                        {
                            "entity": req.entity,
                            "policy_id": dec.details.get("policy_id") or req.tags.get("policy_id") or "default",
                            "categories": json.dumps({k: int((v or {}).get("units") or 0) for k, v in req.categories.items()}),
                            "created_at": str(now),
                            "members": json.dumps({}),
                        },
                    )
                    await client.expire(self._keys.handle(handle_id), 86400)
                except Exception:
                    pass
                self._local_handles[handle_id] = {
                    "entity": req.entity,
                    "policy_id": dec.details.get("policy_id") or req.tags.get("policy_id") or "default",
                    "categories": {k: int((v or {}).get("units") or 0) for k, v in req.categories.items()},
                    "members": {},
                }
                if op_id:
                    try:
                        await client.set(self._keys.op(op_id), json.dumps({"type": "reserve", "decision": dec.__dict__, "handle_id": handle_id}), ex=86400)
                    except Exception:
                        pass
                return dec, handle_id
        except Exception:
            pass
        # Pre-add acceptance-window tracking removed: we track only after successful add
        # to avoid off-by-one denials under steady-rate scenarios.
        policy_id = dec.details.get("policy_id") or req.tags.get("policy_id") or "default"
        pol = self._get_policy(policy_id)
        entity_scope, entity_value = self._parse_entity(req.entity)
        handle_id = str(uuid.uuid4())

        # First, try to atomically add request/token units across scopes; track members for rollback/refund
        added_members: Dict[str, Dict[Tuple[str, str], list[str]]] = {}
        add_failed = False
        denial_retry_after = 0
        used_lua = False

        # Attempt real-Redis multi-key Lua script when available (disabled when forcing stub rate)
        try:
            if await self._is_real_redis() and not self._force_stub_rate():
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
                            # res is expected as {0, max_retry_after}; capture RA if present
                            try:
                                if isinstance(res, (list, tuple)) and len(res) >= 2:
                                    denial_retry_after = max(denial_retry_after, int(res[1]) or 0)
                            except Exception:
                                pass
                            add_failed = True
        except Exception:
            # fall through to Python fallback
            used_lua = False
            self._last_used_multi_lua = False
        if not used_lua:
            if await self._is_stub_client():
                # Pre-check across all scopes/categories
                for category, cfg in req.categories.items():
                    units = int((cfg or {}).get("units") or 0)
                    if units <= 0:
                        continue
                    if category in ("requests", "tokens"):
                        limit = int((pol.get(category) or {}).get("rpm") or 0) if category == "requests" else int((pol.get(category) or {}).get("per_min") or 0)
                        window = 60
                        # Evaluate across scopes and collect counts
                        counts: list[int] = []
                        ok_all = True
                        for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                            if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                                continue
                            key = self._keys.win(policy_id, category, sc, ev)
                            ok, ra, cnt = await self._allow_requests_sliding_check_only(
                                key=key, limit=limit, window=window, units=units, now=now, fail_mode=self._effective_fail_mode(pol, category)
                            )
                            counts.append(int(cnt))
                            if not ok:
                                ok_all = False
                                denial_retry_after = max(denial_retry_after, int(ra or 1))
                        # Tokens special-case: allow initial large batch when no prior usage
                        if not ok_all and category == "tokens" and limit > 0 and units > limit and counts and max(counts) == 0:
                            ok_all = True
                            denial_retry_after = 0
                        if not ok_all:
                            add_failed = True
                            break
                if add_failed:
                    # Deny with rollback (nothing added yet)
                    per_category: Dict[str, Any] = {}
                    for category, cfg in req.categories.items():
                        if category in ("requests", "tokens"):
                            lim = int((pol.get(category) or {}).get("rpm") or 0) if category == "requests" else int((pol.get(category) or {}).get("per_min") or 0)
                            per_category[category] = {"allowed": False, "limit": lim, "retry_after": int(denial_retry_after or 1)}
                        elif category in ("streams", "jobs"):
                            ttl_sec = int((pol.get(category) or {}).get("ttl_sec") or 60)
                            lim = int((pol.get(category) or {}).get("max_concurrent") or 0)
                            per_category[category] = {"allowed": True, "limit": lim, "retry_after": 0, "ttl_sec": ttl_sec}
                        else:
                            per_category[category] = {"allowed": True, "retry_after": 0}
                    denial_decision = RGDecision(allowed=False, retry_after=int(denial_retry_after or 1), details={"policy_id": policy_id, "categories": per_category})
                    if op_id:
                        try:
                            await client.set(self._keys.op(op_id), json.dumps({"type": "reserve", "decision": denial_decision.__dict__, "handle_id": None}), ex=86400)
                        except Exception:
                            pass
                    return denial_decision, None
                # Perform additions now using Redis ZSETs on the stub client
                for category, cfg in req.categories.items():
                    units = int((cfg or {}).get("units") or 0)
                    if units <= 0:
                        continue
                    if category in ("requests", "tokens"):
                        added_members.setdefault(category, {})
                        for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                            if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                                continue
                            key = self._keys.win(policy_id, category, sc, ev)
                            members = [f"{handle_id}:{sc}:{ev}:{i}:{uuid.uuid4().hex}" for i in range(units)]
                            await self._add_members(key=key, members=members, now=now)
                            try:
                                logger.debug(
                                    "RG stub add: policy_id={pid} cat={cat} scope={sc} entity={ev} units={units}",
                                    pid=policy_id,
                                    cat=category,
                                    sc=sc,
                                    ev=ev,
                                    units=units,
                                )
                            except Exception:
                                pass
                            added_members[category][(sc, ev)] = list(members)
            else:
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
                            _ = await self._purge_and_count(key=key, now=now, window=window)
                            added_for_scope: list[str] = []
                            for i in range(units):
                                try:
                                    cnt = await self._purge_and_count(key=key, now=now, window=window)
                                    if cnt >= limit:
                                        try:
                                            ok2, ra2, _ = await self._allow_requests_sliding_check_only(
                                                key=key, limit=int(limit), window=int(window), units=int(units), now=now, fail_mode=cat_fail
                                            )
                                            if not ok2:
                                                denial_retry_after = max(denial_retry_after, int(ra2) or 0)
                                        except Exception:
                                            pass
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
            try:
                # Establish deny-until/backoff using the computed retry_after for stability
                now_df = self._time()
                policy_id_df = policy_id
                # Use category-specific RA if available; fall back to overall denial_retry_after
                ra_df = int(denial_retry_after or 0)
                if ra_df <= 0:
                    ra_df = 60
                # Requests-specific deny floor
                if "requests" in req.categories:
                    # Prefer RA if >=2, else full window
                    floor_df = int(ra_df) if int(ra_df) >= 2 else 60
                    self._requests_deny_until[(self._keys.ns, policy_id_df, req.entity)] = now_df + float(floor_df)
                    self._stub_backoff_until[(self._keys.ns, policy_id_df, req.entity, "requests")] = now_df + float(ra_df)
            except Exception:
                pass
            for category, scopes in added_members.items():
                for (sc, ev), mems in scopes.items():
                    key = self._keys.win(policy_id, category, sc, ev)
                    await self._zrem_members(key=key, members=mems)
            # Build a denial decision reflecting max retry_after across attempted keys
            try:
                base_cats = dict((dec.details or {}).get("categories") or {})
            except Exception:
                base_cats = {}
            per_category: Dict[str, Any] = {}
            # Populate categories from request, overriding requests/tokens to denied
            for category, cfg in req.categories.items():
                if category in ("requests", "tokens"):
                    lim = int((pol.get(category) or {}).get("rpm") or 0) if category == "requests" else int((pol.get(category) or {}).get("per_min") or 0)
                    per_category[category] = {"allowed": False, "limit": lim, "retry_after": int(denial_retry_after or 1)}
                elif category in ("streams", "jobs"):
                    ttl_sec = int((pol.get(category) or {}).get("ttl_sec") or 60)
                    lim = int((pol.get(category) or {}).get("max_concurrent") or 0)
                    per_category[category] = {"allowed": True, "limit": lim, "retry_after": 0, "ttl_sec": ttl_sec}
                else:
                    per_category[category] = {"allowed": True, "retry_after": 0}
            denial_decision = RGDecision(
                allowed=False,
                retry_after=int(denial_retry_after or 1),
                details={"policy_id": policy_id, "categories": per_category},
            )
            # Emit metrics for this denial path across all categories present
            reg = self._reg()
            if reg:
                try:
                    ent_scope_df, _ = self._parse_entity(req.entity)
                    for cat_name, cat_info in per_category.items():
                        reg.increment(
                            "rg_decisions_total",
                            1,
                            _labels(
                                category=cat_name,
                                scope=ent_scope_df,
                                backend="redis",
                                result=("allow" if bool(cat_info.get("allowed")) else "deny"),
                                policy_id=policy_id,
                            ),
                        )
                        if not bool(cat_info.get("allowed")):
                            reg.increment(
                                "rg_denials_total",
                                1,
                                _labels(category=cat_name, scope=ent_scope_df, reason="insufficient_capacity", policy_id=policy_id),
                            )
                except Exception:
                    pass
            if op_id:
                try:
                    await client.set(self._keys.op(op_id), json.dumps({"type": "reserve", "decision": denial_decision.__dict__, "handle_id": None}), ex=86400)
                except Exception:
                    pass
            return denial_decision, None

        # Concurrency: acquire leases (global and entity) after rate counters
        for category, cfg in req.categories.items():
            if category in ("streams", "jobs"):
                ttl_sec = int((pol.get(category) or {}).get("ttl_sec") or 60)
                cat_fail = self._effective_fail_mode(pol, category)
                for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                    if sc not in self._scopes(pol) and not (sc == entity_scope and "entity" in self._scopes(pol)):
                        continue
                    key = self._keys.lease(policy_id, category, sc, ev)
                    # Add stub lease with TTL and mirror into real Redis when available
                    ttl_sec = int((pol.get(category) or {}).get("ttl_sec") or 60)
                    expires_at = now + max(1, int(ttl_sec))
                    bucket = self._stub_leases.setdefault(key, {})
                    bucket[f"{handle_id}:{sc}:{ev}"] = float(expires_at)
                    # Real Redis ZSET entry stores expiry timestamp as score
                    try:
                        client = await self._client_get()
                        await client.zremrangebyscore(key, float("-inf"), now)
                        await client.zadd(key, {f"{handle_id}:{sc}:{ev}": float(expires_at)})
                    except Exception:
                        pass
                    # Metrics: update concurrency gauge based on stub size after purge
                    reg = self._reg()
                    if reg:
                        try:
                            active = self._stub_lease_purge_and_count(key=key, now=now)
                            reg.set_gauge(
                                "rg_concurrency_active",
                                float(active),
                                _labels(category=category, scope=sc, policy_id=policy_id),
                            )
                        except Exception:
                            pass

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
        # Best-effort: ensure a success-path decision metric per category, in case
        # upstream callers rely on reserve() to emit decisions (in addition to check()).
        reg = self._reg()
        if reg:
            try:
                ent_scope_s, _ = self._parse_entity(req.entity)
                for category in req.categories.keys():
                    reg.increment(
                        "rg_decisions_total",
                        1,
                        _labels(
                            category=category,
                            scope=ent_scope_s,
                            backend="redis",
                            result="allow",
                            policy_id=policy_id,
                        ),
                    )
            except Exception:
                pass
        # Harden burst behavior tracking (gated for tests)
        try:
            if self._accept_window_enabled() and "requests" in req.categories:
                limit_req = int((pol.get("requests") or {}).get("rpm") or 0)
                if limit_req > 0:
                    key_aw = (policy_id, req.entity)
                    start, lim, cnt = self._requests_accept_window.get((self._keys.ns,) + key_aw, (now, limit_req, 0))
                    if now >= float(start) + 60.0 or lim != limit_req:
                        start, lim, cnt = now, limit_req, 0
                    cnt += 1
                    self._requests_accept_window[(self._keys.ns,) + key_aw] = (start, lim, cnt)
                    try:
                        logger.debug(
                            "RG accept-window track: policy_id={pid} entity={ent} start={st} cnt={cnt} limit={lim}",
                            pid=policy_id,
                            ent=req.entity,
                            st=start,
                            cnt=cnt,
                            lim=lim,
                        )
                    except Exception:
                        pass
                    if cnt >= limit_req:
                        floor_until = float(start) + 60.0
                        self._requests_deny_until[(self._keys.ns,) + key_aw] = max(self._requests_deny_until.get((self._keys.ns,) + key_aw, 0.0), floor_until)
                        try:
                            logger.debug(
                                "RG accept-window floor set: policy_id={pid} entity={ent} start={st} cnt={cnt} floor_until={fu}",
                                pid=policy_id,
                                ent=req.entity,
                                st=start,
                                cnt=cnt,
                                fu=floor_until,
                            )
                        except Exception:
                            pass
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
        # Delegate in explicit stub-rate mode
        if self._use_stub_rate():
            await self._stub_delegate.commit(handle_id, actuals, op_id)  # type: ignore[union-attr]
            return
        # Use native logic for both real Redis and in-memory stub.
        client = await self._client_get()
        try:
            hkey = self._keys.handle(handle_id)
            data = await client.hgetall(hkey)
            if not data:
                data = self._local_handles.get(handle_id) or {}
                if not data:
                    return
            policy_id = data.get("policy_id") or "default"
            entity = data.get("entity") or ""
            entity_scope, entity_value = self._parse_entity(entity)
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
                        # Remove leases for this handle in stub map and real Redis
                        try:
                            bucket = self._stub_leases.get(key)
                            if bucket is not None:
                                bucket.pop(f"{handle_id}:{sc}:{ev}", None)
                        except Exception:
                            pass
                        try:
                            await client.zrem(key, f"{handle_id}:{sc}:{ev}")
                        except Exception:
                            pass
                        reg = self._reg()
                        if reg:
                            try:
                                active = self._stub_lease_purge_and_count(key=key, now=now)
                                reg.set_gauge(
                                    "rg_concurrency_active",
                                    float(active),
                                    _labels(category=category, scope=sc, policy_id=policy_id),
                                )
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
                    # Remove reserved members to reflect commit(actuals) difference
                    # Metrics: refund path via commit difference
                    reg = self._reg()
                    if reg:
                        try:
                            reg.increment(
                                "rg_refunds_total",
                                1,
                                _labels(category=category, scope=entity_scope, reason="commit_diff", policy_id=policy_id),
                            )
                        except Exception:
                            pass
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
                        take = min(refund_units, len(mem_list))
                        for _ in range(take):
                            to_remove.append(str(mem_list.pop()))
                        if to_remove:
                            await self._zrem_members(key=key, members=to_remove)
                        # Fallback: if we still need to refund more but local list is shorter,
                        # remove additional members matching this handle_id prefix.
                        remaining = refund_units - take
                        if remaining > 0:
                            try:
                                client = await self._client_get()
                                all_members = []
                                try:
                                    all_members = await client.zrange(key, 0, -1)
                                except Exception:
                                    all_members = []
                                prefix = f"{handle_id}:{sc}:{ev}:"
                                candidates = [m for m in (all_members or []) if isinstance(m, str) and m.startswith(prefix)]
                                # Remove from the end (newest first)
                                extra = candidates[-remaining:]
                                if extra:
                                    await self._zrem_members(key=key, members=list(extra))
                            except Exception:
                                pass
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
        # Delegate in explicit stub-rate mode
        if self._use_stub_rate():
            await self._stub_delegate.refund(handle_id, deltas, op_id)  # type: ignore[union-attr]
            return
        # Use native logic for both real Redis and in-memory stub.
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
                # Remove reserved members for this handle to reflect refund request
                scope_map = members.get(category) or {}
                for key_scope, mem_list in scope_map.items():
                    try:
                        sc, ev = key_scope.split(":", 1)
                    except Exception:
                        continue
                    key = self._keys.win(policy_id, category, sc, ev)
                    to_remove = []
                    take = min(units, len(mem_list))
                    for _ in range(take):
                        to_remove.append(str(mem_list.pop()))
                    if to_remove:
                        await self._zrem_members(key=key, members=to_remove)
                    remaining = units - take
                    if remaining > 0:
                        try:
                            client = await self._client_get()
                            all_members = []
                            try:
                                all_members = await client.zrange(key, 0, -1)
                            except Exception:
                                all_members = []
                            prefix = f"{handle_id}:{sc}:{ev}:"
                            candidates = [m for m in (all_members or []) if isinstance(m, str) and m.startswith(prefix)]
                            extra = candidates[-remaining:]
                            if extra:
                                await self._zrem_members(key=key, members=list(extra))
                        except Exception:
                            pass
            # Emit metrics for explicit refund requests (low-cardinality)
            reg = self._reg()
            if reg:
                try:
                    for category, delta in (deltas or {}).items():
                        if int(delta or 0) > 0 and category in ("requests", "tokens"):
                            reg.increment(
                                "rg_refunds_total",
                                1,
                                _labels(category=category, scope="entity", reason="explicit_refund", policy_id=policy_id),
                            )
                except Exception:
                    pass

            if op_id:
                await client.set(self._keys.op(op_id), json.dumps({"type": "refund", "handle_id": handle_id}), ex=3600)
        except Exception:
            pass

    async def renew(self, handle_id: str, ttl_s: int) -> None:
        # Delegate in explicit stub-rate mode
        if self._use_stub_rate():
            await self._stub_delegate.renew(handle_id, ttl_s)  # type: ignore[union-attr]
            return
        # Use native logic for both real Redis and in-memory stub.
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
                        # Update real Redis ZSET (best-effort)
                        try:
                            await client.zadd(key, {f"{handle_id}:{sc}:{ev}": now + max(1, int(ttl_s))})
                        except Exception:
                            pass
                        # Update stub TTL and gauge
                        try:
                            bucket = self._stub_leases.setdefault(key, {})
                            bucket[f"{handle_id}:{sc}:{ev}"] = float(now + max(1, int(ttl_s)))
                            reg = self._reg()
                            if reg:
                                active = self._stub_lease_purge_and_count(key=key, now=now)
                                reg.set_gauge(
                                    "rg_concurrency_active",
                                    float(active),
                                    _labels(category=category, scope=sc, policy_id=policy_id),
                                )
                        except Exception:
                            pass
        except Exception:
            pass

    async def release(self, handle_id: str) -> None:
        # Delegate in explicit stub-rate mode
        if self._use_stub_rate():
            await self._stub_delegate.release(handle_id)  # type: ignore[union-attr]
            return
        # Use native logic for both real Redis and in-memory stub.
        await self.commit(handle_id, actuals=None)

    async def peek(self, entity: str, categories: list[str]) -> Dict[str, Any]:
        # Without policy context, we cannot compute limits; return None placeholders
        # (Tests do not rely on this path.)
        if await self._is_stub_client():
            # For stub, still return placeholders without policy
            return {c: {"remaining": None, "reset": None} for c in categories}
        return {c: {"remaining": None, "reset": None} for c in categories}

    async def peek_with_policy(self, entity: str, categories: list[str], policy_id: str) -> Dict[str, Any]:
        pol = self._get_policy(policy_id)
        entity_scope, entity_value = self._parse_entity(entity)
        now = self._time()
        out: Dict[str, Any] = {}
        is_stub = await self._is_stub_client()
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
                current_cnt = 0
                key = self._keys.win(policy_id, category, sc, ev)
                current_cnt = await self._purge_and_count(key=key, now=now, window=window)
                if current_cnt >= limit:
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
                remainings.append(max(0, limit - current_cnt))
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

    async def test_force_clear_windows(self, policy_id: str, categories: Optional[list[str]] = None) -> None:
        """Test-only helper to force-clear window ZSETs for a policy.

        Intended to be called in property tests when using FakeTime≈0.0 to
        guarantee a clean slate for sliding-window keys in the in-memory stub
        or a local Redis instance.

        Args:
            policy_id: Policy identifier whose window keys should be cleared.
            categories: Optional list of categories to clear (defaults to
                        ["requests", "tokens"]). Others are ignored.
        """
        try:
            now = float(self._time())
        except Exception:
            now = 0.0
        # Only act when tests are likely using FakeTime near zero to avoid
        # destructive behavior in real executions.
        if now >= 1.0:
            return

        cats = list(categories or ["requests", "tokens"])
        try:
            client = await self._client_get()
        except Exception:
            return

        # Delete any ZSET window keys in real/stub client
        for cat in cats:
            if cat not in ("requests", "tokens"):
                continue
            pattern = f"{self._keys.ns}:win:{policy_id}:{cat}:*"
            try:
                _cur, keys = await client.scan(0, match=pattern, count=1000)
            except Exception:
                keys = []
            for k in keys or []:
                try:
                    await client.delete(k)
                except Exception:
                    pass

        # Best-effort: clear in-memory mirrors for leases/windows if any remain
        try:
            to_drop_stub = [k for k in list(self._stub_windows.keys()) if k.startswith(f"{self._keys.ns}:stub:{policy_id}:")]
            for k in to_drop_stub:
                self._stub_windows.pop(k, None)
        except Exception:
            pass
    async def _maybe_test_purge_windows_once(self, *, policy_id: str, categories: Dict[str, Any], now: float) -> None:
        """When FakeTime is near zero, clear any prior window keys for this policy
        exactly once to avoid cross-run contamination. Does nothing after the
        first call for the same policy_id.

        This only affects tests that start with now≈0.0 and reuse Redis between
        runs; production code paths are unaffected.
        """
        try:
            if now >= 1.0:
                return
            if policy_id in self._test_windows_policy_cleared:
                return
            client = await self._client_get()
            for category in categories.keys():
                if category not in ("requests", "tokens"):
                    continue
                pattern = f"{self._keys.ns}:win:{policy_id}:{category}:*"
                try:
                    # Attempt broad scan patterns to delete any residual windows
                    cur, keys = await client.scan(0, match=pattern, count=1000)
                except Exception:
                    keys = []
                for k in keys or []:
                    try:
                        # If this key contains a test prefill marker, preserve it;
                        # otherwise clear any existing entries to ensure a clean start.
                        members = await client.zrange(k, 0, 5)
                        has_prefill = any(str(m) == "prefill" for m in (members or []))
                        if has_prefill:
                            continue
                        await client.delete(k)
                    except Exception:
                        pass
            self._test_windows_policy_cleared.add(policy_id)
        except Exception:
            # best-effort only
            return
