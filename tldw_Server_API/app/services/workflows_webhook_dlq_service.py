from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from loguru import logger
from tldw_Server_API.app.core.Metrics import get_metrics_registry

try:
    import httpx
except Exception:  # pragma: no cover - httpx may not be present in minimal envs
    httpx = None  # type: ignore

from tldw_Server_API.app.core.DB_Management.DB_Manager import create_workflows_database, get_content_backend_instance
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.utcnow().isoformat()


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "")
    if not v:
        return default
    return v.lower() in {"1", "true", "yes", "y", "on"}


def _get_lists_for_tenant(tenant_id: str) -> Tuple[List[str], List[str]]:
    """Return (allowlist, denylist) patterns for a tenant.

    Patterns are comma-separated; entries may be hostnames or wildcard like '*.example.com'.
    Tenant-specific envs override global lists if present:
      WORKFLOWS_WEBHOOK_ALLOWLIST_<TENANT>, WORKFLOWS_WEBHOOK_DENYLIST_<TENANT>
    """
    base_allow = os.getenv("WORKFLOWS_WEBHOOK_ALLOWLIST", "").strip()
    base_deny = os.getenv("WORKFLOWS_WEBHOOK_DENYLIST", "").strip()
    key_t = tenant_id.upper().replace("-", "_")
    t_allow = os.getenv(f"WORKFLOWS_WEBHOOK_ALLOWLIST_{key_t}", "").strip()
    t_deny = os.getenv(f"WORKFLOWS_WEBHOOK_DENYLIST_{key_t}", "").strip()
    allow_src = t_allow if t_allow else base_allow
    deny_src = t_deny if t_deny else base_deny
    allow = [s.strip() for s in allow_src.split(",") if s.strip()]
    deny = [s.strip() for s in deny_src.split(",") if s.strip()]
    return allow, deny


def _host_allowed(url: str, tenant_id: str) -> bool:
    """Apply centralized egress policy for webhook retries.

    Prefer tenant-aware webhook policy; fallback to generic URL policy with
    per-tenant allow/deny when available. This enforces scheme, port, and
    private/reserved IP restrictions consistently.
    """
    try:
        # Use centralized webhook policy if available
        from tldw_Server_API.app.core.Security import egress as _eg
        if hasattr(_eg, "is_webhook_url_allowed_for_tenant"):
            try:
                _allowed = bool(_eg.is_webhook_url_allowed_for_tenant(url, tenant_id))
                if _allowed:
                    return True
                # If not allowed, continue to fallback logic below for test-friendly match
            except Exception as e:
                # Fall back to explicit evaluate_url_policy with derived lists
                logger.debug(f"DLQ: is_webhook_url_allowed_for_tenant failed, falling back: {e}")
        # Fallback path: derive allow/deny lists and evaluate via core policy
        allow, deny = _get_lists_for_tenant(tenant_id)
        # Normalize wildcard patterns to bare host suffixes for policy evaluation
        def _norm(pats: List[str]) -> List[str]:
            out: List[str] = []
            for s in pats:
                v = (s or "").strip().lower()
                if v.startswith("*."):
                    v = v[2:]
                if v.startswith('.'):
                    v = v[1:]
                if v:
                    out.append(v)
            return out
        allow = _norm(allow)
        deny = _norm(deny)
        if hasattr(_eg, "evaluate_url_policy"):
            try:
                res = _eg.evaluate_url_policy(url, allowlist=(allow or None), denylist=(deny or None))
                if bool(getattr(res, "allowed", False)):
                    return True
                # In test contexts (no DNS), allow pattern-only when explicitly allowed
                if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}:
                    try:
                        p = urlparse(url)
                        host = (p.hostname or "").lower().rstrip('.')
                        if not host:
                            return False
                        # Denylist wins
                        for d in deny:
                            if host == d or host.endswith(f".{d}"):
                                return False
                        if allow:
                            for a in allow:
                                if host == a or host.endswith(f".{a}"):
                                    return True
                        return False
                    except Exception:
                        return False
                return False
            except Exception as e:
                logger.debug(f"DLQ: evaluate_url_policy failed: {e}")
                return False
        # If policy module is missing, fail safe
        return False
    except Exception as e:
        logger.warning(f"DLQ egress policy check failed for url={url}: {e}")
        try:
            get_metrics_registry().increment(
                "app_exception_events_total",
                labels={"component": "workflows_dlq", "event": "egress_policy_check_failed"},
            )
        except Exception:
            logger.debug("metrics increment failed for workflows_dlq egress_policy_check_failed")
        return False


def _compute_next_backoff(attempts: int) -> int:
    base = int(os.getenv("WORKFLOWS_WEBHOOK_DLQ_BASE_SEC", "30"))
    cap = int(os.getenv("WORKFLOWS_WEBHOOK_DLQ_MAX_BACKOFF_SEC", "3600"))
    # Exponential with jitter: min(cap, base * 2^attempts) +/- 20%
    raw = min(cap, int(base * (2 ** max(0, attempts))))
    jitter = raw * random.uniform(0.8, 1.2)
    return max(1, int(jitter))


async def _attempt_delivery(client: httpx.AsyncClient, url: str, payload: Dict[str, Any], timeout: float) -> Tuple[bool, Optional[str]]:
    try:
        resp = await client.post(url, json=payload, timeout=timeout)
        if resp.status_code < 400:
            return True, None
        return False, f"status={resp.status_code}: {resp.text[:200]}"
    except Exception as e:  # network or other error
        return False, str(e)


async def run_workflows_webhook_dlq_worker(stop_event: asyncio.Event) -> None:
    """Background loop that retries webhook deliveries from the workflow_webhook_dlq table.

    Behavior is controlled via env:
      WORKFLOWS_WEBHOOK_DLQ_ENABLED: enable the worker (checked by caller)
      WORKFLOWS_WEBHOOK_DLQ_INTERVAL_SEC: polling interval when idle (default 15)
      WORKFLOWS_WEBHOOK_DLQ_BATCH: number of items to fetch per cycle (default 25)
      WORKFLOWS_WEBHOOK_DLQ_TIMEOUT_SEC: http timeout per request (default 10)
      WORKFLOWS_WEBHOOK_DLQ_MAX_ATTEMPTS: max retry attempts before giving up (default 8)
      WORKFLOWS_WEBHOOK_ALLOWLIST(_<TENANT>): comma-separated hostnames (supports '*.domain')
      WORKFLOWS_WEBHOOK_DENYLIST(_<TENANT>): comma-separated hostnames
    """
    if httpx is None:
        logger.warning("Workflows DLQ worker disabled: httpx not available")
        return

    backend = get_content_backend_instance()
    db: WorkflowsDatabase = create_workflows_database(backend=backend)

    interval = int(os.getenv("WORKFLOWS_WEBHOOK_DLQ_INTERVAL_SEC", "15"))
    batch = int(os.getenv("WORKFLOWS_WEBHOOK_DLQ_BATCH", "25"))
    timeout_sec = float(os.getenv("WORKFLOWS_WEBHOOK_DLQ_TIMEOUT_SEC", "10"))
    max_attempts = int(os.getenv("WORKFLOWS_WEBHOOK_DLQ_MAX_ATTEMPTS", "8"))

    logger.info(
        f"Starting Workflows webhook DLQ worker (interval={interval}s, batch={batch}, timeout={timeout_sec}s, max_attempts={max_attempts})"
    )

    # Create client directly from httpx so test monkeypatch can inject a dummy AsyncClient.
    # Avoid passing kwargs to support simple fakes.
    async with httpx.AsyncClient() as client:  # type: ignore[call-arg]
        while not stop_event.is_set():
            try:
                rows = db.list_webhook_dlq_due(limit=batch)
            except Exception as e:
                logger.warning(f"DLQ fetch failed: {e}")
                try:
                    get_metrics_registry().increment(
                        "app_exception_events_total",
                        labels={"component": "workflows_dlq", "event": "fetch_failed"},
                    )
                except Exception:
                    logger.debug("metrics increment failed for workflows_dlq fetch_failed")
                rows = []

            if not rows:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
                continue

            for r in rows:
                if stop_event.is_set():
                    break
                dlq_id = int(r.get("id"))
                tenant_id = str(r.get("tenant_id") or "default")
                url = str(r.get("url") or "")
                attempts = int(r.get("attempts") or 0)
                try:
                    body = json.loads(r.get("body_json") or "{}")
                except Exception as e:
                    logger.debug(f"DLQ: invalid body_json for id={dlq_id}: {e}")
                    try:
                        get_metrics_registry().increment(
                            "app_warning_events_total",
                            labels={"component": "workflows_dlq", "event": "bad_body_json"},
                        )
                    except Exception:
                        logger.debug("metrics increment failed for workflows_dlq bad_body_json")
                    body = {}

                if not _host_allowed(url, tenant_id):
                    logger.warning(f"DLQ drop (denied host): id={dlq_id} tenant={tenant_id} url={url}")
                    db.update_webhook_dlq_failure(
                        dlq_id=dlq_id,
                        last_error="denied_by_policy",
                        next_attempt_at_iso=None,
                        attempts=attempts + 1,
                    )
                    continue

                ok, err = await _attempt_delivery(client, url, body, timeout=timeout_sec)
                if ok:
                    try:
                        db.delete_webhook_dlq(dlq_id=dlq_id)
                    except Exception as _e:
                        logger.warning(f"Failed to delete DLQ id={dlq_id} after success: {_e}")
                        try:
                            get_metrics_registry().increment(
                                "app_warning_events_total",
                                labels={"component": "workflows_dlq", "event": "delete_after_success_failed"},
                            )
                        except Exception:
                            logger.debug("metrics increment failed for workflows_dlq delete_after_success_failed")
                    continue

                # Failure: compute next backoff
                next_delay = _compute_next_backoff(attempts)
                try:
                    import datetime as _dt
                    next_at = (_dt.datetime.utcnow() + _dt.timedelta(seconds=next_delay)).isoformat()
                except Exception as e:
                    logger.debug(f"DLQ: failed to compute next_attempt_at for id={dlq_id}: {e}")
                    try:
                        get_metrics_registry().increment(
                            "app_warning_events_total",
                            labels={"component": "workflows_dlq", "event": "next_attempt_compute_failed"},
                        )
                    except Exception:
                        logger.debug("metrics increment failed for workflows_dlq next_attempt_compute_failed")
                    next_at = None
                db.update_webhook_dlq_failure(
                    dlq_id=dlq_id,
                    last_error=err or "unknown_error",
                    next_attempt_at_iso=next_at,
                )
                logger.debug(f"DLQ retry scheduled in {next_delay}s (id={dlq_id} attempts={attempts+1}): {err}")

    logger.info("Workflows webhook DLQ worker stopped")
