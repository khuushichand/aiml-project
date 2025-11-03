from __future__ import annotations

"""
Core Resource Governor (memory backend) with idempotency and metrics.

Implements a minimal in-process governor suitable for unit/integration tests
and single-node development. It provides:
  - Token bucket / sliding window for requests/tokens categories
  - Concurrency leases with TTL for streams/jobs categories
  - Idempotent reserve/commit/refund via op_id
  - Monotonic time source injection for deterministic tests
  - Basic policy resolution (policy_id → rules) and strictest-wins across
    global + entity scope

This module does not wire HTTP middleware; that integration happens in the
API layer. Minutes/day ledger durability is left to a separate DAL; this
memory governor implements only in-memory counting for the 'minutes' category.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from loguru import logger

from .metrics_rg import ensure_rg_metrics_registered, _labels

try:
    # Metrics are optional during early startup
    from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
except Exception:  # pragma: no cover - metrics optional
    get_metrics_registry = None  # type: ignore


TimeSource = Callable[[], float]


@dataclass(frozen=True)
class RGRequest:
    entity: str  # format: "scope:value" (e.g., "user:123")
    categories: Dict[str, Dict[str, int]]  # e.g., {"requests": {"units": 1}}
    tags: Dict[str, str] = field(default_factory=dict)  # endpoint, service, policy_id, etc.


@dataclass
class RGDecision:
    allowed: bool
    retry_after: Optional[int]
    details: Dict[str, Any]


class ResourceGovernor:
    async def check(self, req: RGRequest) -> RGDecision:  # pragma: no cover - interface
        raise NotImplementedError

    async def reserve(self, req: RGRequest, op_id: Optional[str] = None) -> Tuple[RGDecision, Optional[str]]:  # pragma: no cover - interface
        raise NotImplementedError

    async def commit(self, handle_id: str, actuals: Optional[Dict[str, int]] = None, op_id: Optional[str] = None) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def refund(self, handle_id: str, deltas: Optional[Dict[str, int]] = None, op_id: Optional[str] = None) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def renew(self, handle_id: str, ttl_s: int) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def release(self, handle_id: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def peek(self, entity: str, categories: list[str]) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    async def query(self, entity: str, category: str) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    async def reset(self, entity: str, category: Optional[str] = None) -> None:  # pragma: no cover - interface
        raise NotImplementedError


# --- Token bucket primitives ---


@dataclass
class _Bucket:
    capacity: float
    refill_per_sec: float
    tokens: float
    last_refill: float

    def refill(self, now: float) -> None:
        if now <= self.last_refill:
            return
        dt = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + dt * self.refill_per_sec)
        self.last_refill = now

    def available(self, now: float) -> float:
        self.refill(now)
        return self.tokens

    def consume(self, units: float, now: float) -> bool:
        self.refill(now)
        if self.tokens >= units:
            self.tokens -= units
            return True
        return False

    def retry_after(self, units: float, now: float) -> int:
        self.refill(now)
        if self.tokens >= units:
            return 0
        deficit = units - self.tokens
        if self.refill_per_sec <= 0:
            return 3600  # effectively unbounded wait
        sec = int((deficit / self.refill_per_sec) + 0.999)
        return max(1, sec)


# --- Concurrency leases ---


@dataclass
class _Lease:
    lease_id: str
    expires_at: float


# --- Reservation handle ---


@dataclass
class _ReservationHandle:
    handle_id: str
    entity: str
    policy_id: str
    categories: Dict[str, int]  # reserved units by category
    created_at: float
    expires_at: float
    state: str = "reserved"  # reserved|finalized


class MemoryResourceGovernor(ResourceGovernor):
    """
    In-memory Resource Governor implementation.

    Policy format example:
    {
      "chat.default": {
        "requests": {"rpm": 120, "burst": 2.0},
        "tokens": {"per_min": 60000, "burst": 1.5},
        "streams": {"max_concurrent": 2, "ttl_sec": 90},
        "scopes": ["global", "user"]
      }
    }
    """

    def __init__(
        self,
        *,
        policies: Optional[Dict[str, Dict[str, Any]]] = None,
        policy_loader: Optional[Any] = None,
        time_source: TimeSource = time.monotonic,
        backend_label: str = "memory",
        default_handle_ttl: int = 120,
    ) -> None:
        self._policies = policies or {}
        self._policy_loader = policy_loader
        self._time = time_source
        self._backend_label = backend_label
        self._default_handle_ttl = max(5, int(default_handle_ttl))

        # Keyed by (policy_id, category, scope, entity_value)
        self._buckets: Dict[Tuple[str, str, str, str], _Bucket] = {}
        # Concurrency: (policy_id, category, scope, entity_value) → {lease_id: _Lease}
        self._leases: Dict[Tuple[str, str, str, str], Dict[str, _Lease]] = {}
        # Handles and idempotency
        self._handles: Dict[str, _ReservationHandle] = {}
        self._ops: Dict[str, Dict[str, Any]] = {}  # op_id → {type, handle_id}

        # Metrics
        ensure_rg_metrics_registered()

    # --- Policy helpers ---
    def _get_policy(self, policy_id: str) -> Dict[str, Any]:
        if self._policy_loader is not None:
            try:
                pol = self._policy_loader.get_policy(policy_id)  # type: ignore[attr-defined]
                if pol:
                    return pol
            except Exception as e:
                logger.debug(f"Policy loader failed; falling back to static policies: {e}")
        return self._policies.get(policy_id, {})

    @staticmethod
    def _parse_entity(entity: str) -> Tuple[str, str]:
        # entity of the form "scope:value" → (scope, value)
        if ":" in entity:
            s, v = entity.split(":", 1)
            return s.strip() or "entity", v.strip()
        return "entity", entity

    # --- Buckets ---
    def _bucket_key(self, policy_id: str, category: str, scope: str, entity_value: str) -> Tuple[str, str, str, str]:
        return (policy_id, category, scope, entity_value)

    def _get_bucket(self, policy_id: str, category: str, scope: str, entity_value: str, *, capacity: float, refill_per_sec: float) -> _Bucket:
        k = self._bucket_key(policy_id, category, scope, entity_value)
        b = self._buckets.get(k)
        if b is None:
            b = _Bucket(capacity=float(capacity), refill_per_sec=float(refill_per_sec), tokens=float(capacity), last_refill=self._time())
            self._buckets[k] = b
        return b

    # --- Leases ---
    def _get_lease_map(self, policy_id: str, category: str, scope: str, entity_value: str) -> Dict[str, _Lease]:
        k = self._bucket_key(policy_id, category, scope, entity_value)
        m = self._leases.get(k)
        if m is None:
            m = {}
            self._leases[k] = m
        return m

    def _purge_expired_leases(self, m: Dict[str, _Lease], now: float) -> None:
        expired = [lid for lid, l in m.items() if l.expires_at <= now]
        for lid in expired:
            del m[lid]

    # --- Core evaluation ---
    def _category_limits(self, policy: Dict[str, Any], category: str) -> Dict[str, Any]:
        return dict(policy.get(category, {}))

    def _scopes(self, policy: Dict[str, Any]) -> list[str]:
        s = policy.get("scopes")
        if isinstance(s, list) and s:
            return [str(x) for x in s]
        return ["global", "entity"]

    def _compute_headroom_requests_tokens(
        self,
        *,
        policy_id: str,
        policy: Dict[str, Any],
        category: str,
        entity_scope: str,
        entity_value: str,
        units: int,
        now: float,
    ) -> Tuple[bool, int, Dict[str, Any]]:
        cfg = self._category_limits(policy, category)
        # Interpret RPM / per_min and burst
        if category == "requests":
            rpm = float(cfg.get("rpm") or 0)
            burst = float(cfg.get("burst") or 1.0)
            refill_per_sec = rpm / 60.0
            capacity = rpm * max(1.0, burst)
        else:  # tokens
            per_min = float(cfg.get("per_min") or 0)
            burst = float(cfg.get("burst") or 1.0)
            refill_per_sec = per_min / 60.0
            capacity = per_min * max(1.0, burst)

        if refill_per_sec <= 0 or capacity <= 0:
            # Policy disabled or zero → deny with large retry
            return False, 60, {"limit": 0, "used": 0, "remaining": 0}

        # Evaluate strictest across scopes: global + entity scope
        scopes = self._scopes(policy)
        scope_keys: list[Tuple[str, str]] = []
        if "global" in scopes:
            scope_keys.append(("global", "*"))
        if entity_scope in scopes or "entity" in scopes:
            scope_keys.append((entity_scope, entity_value))

        remainings = []
        retry_after_candidates = []
        for sc, ev in scope_keys:
            b = self._get_bucket(policy_id, category, sc, ev, capacity=capacity, refill_per_sec=refill_per_sec)
            avail = b.available(now)
            remaining = max(0, int(avail))
            remainings.append(remaining)
            if avail >= units:
                retry_after_candidates.append(0)
            else:
                retry_after_candidates.append(b.retry_after(units, now))

        effective_remaining = min(remainings) if remainings else 0
        allowed = effective_remaining >= units
        retry_after = max(retry_after_candidates) if retry_after_candidates else None
        details = {
            "limit": int(capacity),
            "remaining": int(effective_remaining),
            "retry_after": int(retry_after or 0) if retry_after is not None else None,
        }
        return allowed, int(retry_after or 0) if retry_after is not None else 0, details

    def _acquire_concurrency(
        self,
        *,
        policy_id: str,
        policy: Dict[str, Any],
        category: str,
        entity_scope: str,
        entity_value: str,
        units: int,
        now: float,
    ) -> Tuple[bool, int, Dict[str, Any]]:
        cfg = self._category_limits(policy, category)
        limit = int(cfg.get("max_concurrent") or 0)
        ttl_sec = int(cfg.get("ttl_sec") or 60)
        if limit <= 0:
            return False, 1, {"limit": 0, "remaining": 0}

        scopes = self._scopes(policy)
        scope_keys: list[Tuple[str, str]] = []
        if "global" in scopes:
            scope_keys.append(("global", "*"))
        if entity_scope in scopes or "entity" in scopes:
            scope_keys.append((entity_scope, entity_value))

        remainings = []
        retry_after_candidates = []
        for sc, ev in scope_keys:
            m = self._get_lease_map(policy_id, category, sc, ev)
            self._purge_expired_leases(m, now)
            active = len(m)
            remaining = max(0, limit - active)
            remainings.append(remaining)
            retry_after_candidates.append(ttl_sec if remaining <= 0 else 0)

        effective_remaining = min(remainings) if remainings else 0
        allowed = effective_remaining >= units
        retry_after = max(retry_after_candidates) if retry_after_candidates else None
        details = {"limit": int(limit), "remaining": int(effective_remaining), "ttl_sec": ttl_sec, "retry_after": retry_after}
        return allowed, int(retry_after or 0) if retry_after is not None else 0, details

    # --- Public API ---
    async def check(self, req: RGRequest) -> RGDecision:
        now = self._time()
        policy_id = req.tags.get("policy_id") or "default"
        pol = self._get_policy(policy_id)
        entity_scope, entity_value = self._parse_entity(req.entity)
        backend = self._backend_label

        overall_allowed = True
        per_category: Dict[str, Any] = {}
        retry_after_overall = 0

        for category, cfg in req.categories.items():
            units = int(cfg.get("units") or 0)
            if category in ("requests", "tokens"):
                allowed, retry_after, details = self._compute_headroom_requests_tokens(
                    policy_id=policy_id,
                    policy=pol,
                    category=category,
                    entity_scope=entity_scope,
                    entity_value=entity_value,
                    units=units,
                    now=now,
                )
            elif category in ("streams", "jobs"):
                allowed, retry_after, details = self._acquire_concurrency(
                    policy_id=policy_id,
                    policy=pol,
                    category=category,
                    entity_scope=entity_scope,
                    entity_value=entity_value,
                    units=units,
                    now=now,
                )
            else:
                # Minutes and other ledgers are not enforced in memory; allow by default here
                allowed, retry_after, details = True, 0, {"remaining": 10**9}

            per_category[category] = {"allowed": bool(allowed), **details}
            overall_allowed = overall_allowed and allowed
            retry_after_overall = max(retry_after_overall, int(details.get("retry_after") or 0))

            # Metrics per category (decision)
            if get_metrics_registry:
                get_metrics_registry().increment(
                    "rg_decisions_total",
                    1,
                    _labels(category=category, scope=entity_scope, backend=backend, result=("allow" if allowed else "deny"), policy_id=policy_id),
                )
                if not allowed:
                    get_metrics_registry().increment(
                        "rg_denials_total",
                        1,
                        _labels(category=category, scope=entity_scope, reason="insufficient_capacity", policy_id=policy_id),
                    )

        return RGDecision(allowed=overall_allowed, retry_after=(retry_after_overall or None), details={"policy_id": policy_id, "categories": per_category})

    async def reserve(self, req: RGRequest, op_id: Optional[str] = None) -> Tuple[RGDecision, Optional[str]]:
        # Idempotency: return previous outcome for same op_id
        if op_id and op_id in self._ops:
            rec = self._ops[op_id]
            hid = rec.get("handle_id")
            return rec.get("decision"), hid  # type: ignore[return-value]

        dec = await self.check(req)
        if not dec.allowed:
            if op_id:
                self._ops[op_id] = {"type": "reserve", "decision": dec, "handle_id": None}
            return dec, None

        # Consume from buckets / acquire leases
        now = self._time()
        policy_id = dec.details.get("policy_id") or req.tags.get("policy_id") or "default"
        pol = self._get_policy(policy_id)
        entity_scope, entity_value = self._parse_entity(req.entity)
        handle_id = str(uuid.uuid4())
        ttl = self._default_handle_ttl
        h = _ReservationHandle(handle_id=handle_id, entity=req.entity, policy_id=policy_id, categories={}, created_at=now, expires_at=now + ttl)

        for category, cfg in req.categories.items():
            units = int(cfg.get("units") or 0)
            h.categories[category] = units
            if category in ("requests", "tokens"):
                # consume from both global and entity buckets when applicable
                cl_allowed, _ra, _det = self._compute_headroom_requests_tokens(
                    policy_id=policy_id,
                    policy=pol,
                    category=category,
                    entity_scope=entity_scope,
                    entity_value=entity_value,
                    units=units,
                    now=now,
                )
                if not cl_allowed:
                    logger.warning("reserve inconsistency: allowed in check but deny on consume; ignoring for memory backend")
                cfg = self._category_limits(pol, category)
                if category == "requests":
                    rpm = float(cfg.get("rpm") or 0)
                    burst = float(cfg.get("burst") or 1.0)
                    refill_per_sec = rpm / 60.0
                    capacity = rpm * max(1.0, burst)
                else:
                    per_min = float(cfg.get("per_min") or 0)
                    burst = float(cfg.get("burst") or 1.0)
                    refill_per_sec = per_min / 60.0
                    capacity = per_min * max(1.0, burst)
                # global
                if "global" in self._scopes(pol):
                    b = self._get_bucket(policy_id, category, "global", "*", capacity=capacity, refill_per_sec=refill_per_sec)
                    _ = b.consume(units, now)
                # entity
                b = self._get_bucket(policy_id, category, entity_scope, entity_value, capacity=capacity, refill_per_sec=refill_per_sec)
                _ = b.consume(units, now)

            elif category in ("streams", "jobs"):
                cfgc = self._category_limits(pol, category)
                limit = int(cfgc.get("max_concurrent") or 0)
                ttl_sec = int(cfgc.get("ttl_sec") or 60)
                # Acquire for global and entity scopes (when configured)
                scopes = self._scopes(pol)
                for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                    if sc not in scopes and not (sc == entity_scope and "entity" in scopes):
                        continue
                    m = self._get_lease_map(policy_id, category, sc, ev)
                    self._purge_expired_leases(m, now)
                    if len(m) >= limit:
                        logger.debug("lease contention on reserve: scope={} ev={}", sc, ev)
                        continue
                    lid = f"{handle_id}:{sc}:{ev}"
                    m[lid] = _Lease(lease_id=lid, expires_at=now + ttl_sec)
                    # Gauge update (best-effort)
                    if get_metrics_registry:
                        get_metrics_registry().set_gauge(
                            "rg_concurrency_active",
                            float(len(m)),
                            {"category": category, "scope": sc, "policy_id": policy_id},
                        )
            else:
                # minutes / others: no-op in memory (allow)
                pass

        self._handles[handle_id] = h
        if op_id:
            self._ops[op_id] = {"type": "reserve", "decision": dec, "handle_id": handle_id}
        return dec, handle_id

    async def commit(self, handle_id: str, actuals: Optional[Dict[str, int]] = None, op_id: Optional[str] = None) -> None:
        # Idempotent per op_id
        if op_id and op_id in self._ops:
            rec = self._ops[op_id]
            if rec.get("type") == "commit" and rec.get("handle_id") == handle_id:
                return
        h = self._handles.get(handle_id)
        if not h:
            return
        now = self._time()
        entity_scope, entity_value = self._parse_entity(h.entity)
        pol = self._get_policy(h.policy_id)

        actuals = actuals or {}
        for category, reserved in list(h.categories.items()):
            actual = int(actuals.get(category, reserved))
            actual = max(0, min(actual, reserved))
            refund_units = reserved - actual
            if refund_units > 0:
                # return difference to buckets
                if category in ("requests", "tokens"):
                    cfg = self._category_limits(pol, category)
                    if category == "requests":
                        rpm = float(cfg.get("rpm") or 0)
                        burst = float(cfg.get("burst") or 1.0)
                        refill_per_sec = rpm / 60.0
                        capacity = rpm * max(1.0, burst)
                    else:
                        per_min = float(cfg.get("per_min") or 0)
                        burst = float(cfg.get("burst") or 1.0)
                        refill_per_sec = per_min / 60.0
                        capacity = per_min * max(1.0, burst)
                    # global
                    if "global" in self._scopes(pol):
                        b = self._get_bucket(h.policy_id, category, "global", "*", capacity=capacity, refill_per_sec=refill_per_sec)
                        b.refill(now)
                        b.tokens = min(b.capacity, b.tokens + refund_units)
                    # entity
                    b = self._get_bucket(h.policy_id, category, entity_scope, entity_value, capacity=capacity, refill_per_sec=refill_per_sec)
                    b.refill(now)
                    b.tokens = min(b.capacity, b.tokens + refund_units)
                    if get_metrics_registry:
                        get_metrics_registry().increment(
                            "rg_refunds_total",
                            1,
                            _labels(category=category, scope=entity_scope, reason="commit_diff", policy_id=h.policy_id),
                        )
                # concurrency: nothing to refund here

        # Release any concurrency leases
        for category in list(h.categories.keys()):
            if category in ("streams", "jobs"):
                scopes = self._scopes(pol)
                for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                    if sc not in scopes and not (sc == entity_scope and "entity" in scopes):
                        continue
                    m = self._get_lease_map(h.policy_id, category, sc, ev)
                    self._purge_expired_leases(m, now)
                    # Remove leases for this handle
                    to_del = [lid for lid in list(m.keys()) if lid.startswith(f"{handle_id}:")]
                    for lid in to_del:
                        del m[lid]
                    if get_metrics_registry:
                        get_metrics_registry().set_gauge(
                            "rg_concurrency_active",
                            float(len(m)),
                            {"category": category, "scope": sc, "policy_id": h.policy_id},
                        )

        h.state = "finalized"
        if op_id:
            self._ops[op_id] = {"type": "commit", "handle_id": handle_id}

    async def refund(self, handle_id: str, deltas: Optional[Dict[str, int]] = None, op_id: Optional[str] = None) -> None:
        # Idempotent per op_id
        if op_id and op_id in self._ops:
            rec = self._ops[op_id]
            if rec.get("type") == "refund" and rec.get("handle_id") == handle_id:
                return
        h = self._handles.get(handle_id)
        if not h:
            return
        now = self._time()
        entity_scope, entity_value = self._parse_entity(h.entity)
        pol = self._get_policy(h.policy_id)
        deltas = deltas or {}

        for category, reserved in list(h.categories.items()):
            refund_units = int(deltas.get(category, reserved))
            refund_units = max(0, min(refund_units, reserved))
            if refund_units <= 0:
                continue
            if category in ("requests", "tokens"):
                cfg = self._category_limits(pol, category)
                if category == "requests":
                    rpm = float(cfg.get("rpm") or 0)
                    burst = float(cfg.get("burst") or 1.0)
                    refill_per_sec = rpm / 60.0
                    capacity = rpm * max(1.0, burst)
                else:
                    per_min = float(cfg.get("per_min") or 0)
                    burst = float(cfg.get("burst") or 1.0)
                    refill_per_sec = per_min / 60.0
                    capacity = per_min * max(1.0, burst)
                # global
                if "global" in self._scopes(pol):
                    b = self._get_bucket(h.policy_id, category, "global", "*", capacity=capacity, refill_per_sec=refill_per_sec)
                    b.refill(now)
                    b.tokens = min(b.capacity, b.tokens + refund_units)
                # entity
                b = self._get_bucket(h.policy_id, category, entity_scope, entity_value, capacity=capacity, refill_per_sec=refill_per_sec)
                b.refill(now)
                b.tokens = min(b.capacity, b.tokens + refund_units)
                if get_metrics_registry:
                    get_metrics_registry().increment(
                        "rg_refunds_total",
                        1,
                        _labels(category=category, scope=entity_scope, reason="explicit_refund", policy_id=h.policy_id),
                    )

        if op_id:
            self._ops[op_id] = {"type": "refund", "handle_id": handle_id}

    async def renew(self, handle_id: str, ttl_s: int) -> None:
        h = self._handles.get(handle_id)
        if not h:
            return
        now = self._time()
        h.expires_at = now + max(1, int(ttl_s))
        entity_scope, entity_value = self._parse_entity(h.entity)
        pol = self._get_policy(h.policy_id)
        for category in list(h.categories.keys()):
            if category in ("streams", "jobs"):
                scopes = self._scopes(pol)
                for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                    if sc not in scopes and not (sc == entity_scope and "entity" in scopes):
                        continue
                    m = self._get_lease_map(h.policy_id, category, sc, ev)
                    # Renew leases for this handle
                    for lid, lease in list(m.items()):
                        if lid.startswith(f"{handle_id}:"):
                            lease.expires_at = now + max(1, int(ttl_s))

    async def release(self, handle_id: str) -> None:
        # Alias to commit with zero actuals for all categories
        await self.commit(handle_id, actuals={})

    async def peek(self, entity: str, categories: list[str]) -> Dict[str, Any]:
        now = self._time()
        result: Dict[str, Any] = {}
        # Peeks without policy context assume a synthetic policy_id 'default'
        policy_id = "default"
        entity_scope, entity_value = self._parse_entity(entity)
        for category in categories:
            # We report remaining based on current bucket tokens if present
            remainings = []
            for sc, ev in (("global", "*"), (entity_scope, entity_value)):
                b = self._buckets.get(self._bucket_key(policy_id, category, sc, ev))
                if b:
                    remainings.append(int(b.available(now)))
            result[category] = {"remaining": (min(remainings) if remainings else None)}
        return result

    async def query(self, entity: str, category: str) -> Dict[str, Any]:
        now = self._time()
        policy_id = "default"
        entity_scope, entity_value = self._parse_entity(entity)
        b_global = self._buckets.get(self._bucket_key(policy_id, category, "global", "*"))
        b_entity = self._buckets.get(self._bucket_key(policy_id, category, entity_scope, entity_value))
        return {
            "global": {"available": int(b_global.available(now))} if b_global else None,
            "entity": {"available": int(b_entity.available(now))} if b_entity else None,
        }

    async def reset(self, entity: str, category: Optional[str] = None) -> None:
        entity_scope, entity_value = self._parse_entity(entity)
        keys = list(self._buckets.keys())
        for (pol, cat, sc, ev) in keys:
            if category and cat != category:
                continue
            if sc == entity_scope and ev == entity_value:
                try:
                    del self._buckets[(pol, cat, sc, ev)]
                except KeyError:
                    pass

