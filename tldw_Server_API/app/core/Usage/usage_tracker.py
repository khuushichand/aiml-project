"""
usage_tracker.py

Async helpers to log per-request LLM usage and compute costs.
Integrates with AuthNZ DatabasePool for both SQLite and Postgres.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import date, datetime, timezone
from sqlite3 import Error as SQLiteError

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.usage_repo import AuthnzUsageRepo
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.Metrics import increment_counter

from .pricing_catalog import get_pricing_catalog

try:  # pragma: no cover - ledger optional during upgrades/tests
    from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import (  # type: ignore
        LedgerEntry,
        ResourceDailyLedger,
    )
except ImportError:  # pragma: no cover - safe fallback
    LedgerEntry = None  # type: ignore
    ResourceDailyLedger = None  # type: ignore

_USAGE_NONCRITICAL_EXCEPTIONS = (
    OSError,
    RuntimeError,
    SQLiteError,
    TimeoutError,
    TypeError,
    ValueError,
)

_tokens_daily_ledger: ResourceDailyLedger | None = None  # type: ignore[name-defined]
_tokens_daily_ledger_lock = asyncio.Lock()
_tokens_legacy_backfill_done: set[str] = set()


async def _get_tokens_daily_ledger() -> ResourceDailyLedger | None:
    global _tokens_daily_ledger
    if ResourceDailyLedger is None or LedgerEntry is None:
        return None
    if _tokens_daily_ledger is not None:
        return _tokens_daily_ledger
    async with _tokens_daily_ledger_lock:
        if _tokens_daily_ledger is not None:
            return _tokens_daily_ledger
        try:
            ledger = ResourceDailyLedger()  # type: ignore[call-arg]
            await ledger.initialize()
            _tokens_daily_ledger = ledger
            return ledger
        except _USAGE_NONCRITICAL_EXCEPTIONS as exc:  # pragma: no cover - defensive
            logger.debug(f"LLM usage: ResourceDailyLedger init failed; tokens/day caps disabled: {exc}")
            _tokens_daily_ledger = None
            return None


async def backfill_legacy_tokens_to_ledger(
    *,
    entity_scope: str,
    entity_value: str,
    day_utc: str | None = None,
) -> None:
    """
    Best-effort migration helper: mirror today's tokens usage from ``llm_usage_log``
    into the shared ResourceDailyLedger once per process/entity/day.

    This preserves in-progress daily token caps when upgrading from versions
    that only wrote to ``llm_usage_log`` (and not the ledger).

    This function is fail-open and never raises.
    """
    if ResourceDailyLedger is None or LedgerEntry is None:
        return

    scope = str(entity_scope or "").strip()
    value = str(entity_value or "").strip()
    if scope not in {"user", "api_key"} or not value:
        return

    # Only numeric api_key ids map to llm_usage_log.key_id.
    if scope == "api_key":
        try:
            int(value)
        except (TypeError, ValueError):
            return

    day = day_utc or datetime.now(timezone.utc).date().isoformat()
    key = f"{scope}:{value}:{day}"
    if key in _tokens_legacy_backfill_done:
        return

    try:
        ledger = await _get_tokens_daily_ledger()
        if ledger is None:
            _tokens_legacy_backfill_done.add(key)
            return

        used = await ledger.total_for_day(
            entity_scope=scope,
            entity_value=value,
            category="tokens",
            day_utc=day,
        )
        used_int = int(used or 0)

        try:
            day_val = date.fromisoformat(day)
        except (TypeError, ValueError):
            day_val = datetime.now(timezone.utc).date()

        pool: DatabasePool = await get_db_pool()
        repo = AuthnzUsageRepo(pool)
        legacy_total = 0
        if scope == "user":
            legacy_total = int((await repo.summarize_user_day(user_id=int(value), day=day_val)).get("tokens") or 0)
        else:
            legacy_total = int((await repo.summarize_key_day(key_id=int(value), day=day_val)).get("tokens") or 0)

        delta = int(legacy_total) - int(used_int)
        if delta > 0:
            entry = LedgerEntry(  # type: ignore[call-arg]
                entity_scope=scope,
                entity_value=value,
                category="tokens",
                units=int(delta),
                op_id=f"tokens-legacy:{scope}:{value}:{day}",
                occurred_at=datetime.now(timezone.utc),
            )
            await ledger.add(entry)
    except _USAGE_NONCRITICAL_EXCEPTIONS:
        return
    finally:
        _tokens_legacy_backfill_done.add(key)


def _enabled() -> bool:
    try:
        settings = get_settings()
        val = getattr(settings, "LLM_USAGE_ENABLED", True)
        # Allow env to override
        env_val = os.getenv("LLM_USAGE_ENABLED")
        if env_val is not None:
            return str(env_val).strip().lower() in {"true", "1", "yes", "y", "on"}
        return bool(val)
    except _USAGE_NONCRITICAL_EXCEPTIONS:
        return True


def compute_costs(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> tuple[float, float, float, bool]:
    """
    Compute (prompt_cost, completion_cost, total_cost, estimated)
    given provider, model and token counts.
    """
    catalog = get_pricing_catalog()
    in_per_1k, out_per_1k, est = catalog.get_rates(provider, model)
    prompt_cost = (max(0, prompt_tokens) / 1000.0) * in_per_1k
    completion_cost = (max(0, completion_tokens) / 1000.0) * out_per_1k
    total_cost = prompt_cost + completion_cost
    return prompt_cost, completion_cost, total_cost, est


async def log_llm_usage(
    *,
    user_id: int | None,
    key_id: int | None,
    endpoint: str,
    operation: str,
    provider: str,
    model: str,
    status: int,
    latency_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int | None = None,
    currency: str = "USD",
    request_id: str | None = None,
    estimated: bool | None = None,
) -> None:
    """
    Insert a single llm_usage_log row. Computes costs if needed.

    This function is best-effort and should never raise; errors are logged.
    """
    if not _enabled():
        return

    try:
        pt = int(prompt_tokens or 0)
        ct = int(completion_tokens or 0)
        tt = int(total_tokens) if total_tokens is not None else pt + ct

        p_cost, c_cost, t_cost, est_flag = compute_costs(provider, model, pt, ct)
        if estimated is None:
            estimated = est_flag

        # Record cost and tokens in Prometheus metrics (best-effort)
        try:
            increment_counter(
                "llm_cost_dollars",
                float(t_cost),
                labels={"provider": str(provider or "unknown"), "model": str(model or "unknown")},
            )
            # Per-user and per-operation breakdowns
            if user_id is not None:
                increment_counter(
                    "llm_cost_dollars_by_user",
                    float(t_cost),
                    labels={
                        "provider": str(provider or "unknown"),
                        "model": str(model or "unknown"),
                        "user_id": str(user_id),
                    },
                )
            if operation:
                increment_counter(
                    "llm_cost_dollars_by_operation",
                    float(t_cost),
                    labels={
                        "provider": str(provider or "unknown"),
                        "model": str(model or "unknown"),
                        "operation": str(operation or ""),
                    },
                )
            if pt:
                increment_counter(
                    "llm_tokens_used_total",
                    float(pt),
                    labels={"provider": str(provider or "unknown"), "model": str(model or "unknown"), "type": "prompt"},
                )
                if user_id is not None:
                    increment_counter(
                        "llm_tokens_used_total_by_user",
                        float(pt),
                        labels={
                            "provider": str(provider or "unknown"),
                            "model": str(model or "unknown"),
                            "type": "prompt",
                            "user_id": str(user_id),
                        },
                    )
                if operation:
                    increment_counter(
                        "llm_tokens_used_total_by_operation",
                        float(pt),
                        labels={
                            "provider": str(provider or "unknown"),
                            "model": str(model or "unknown"),
                            "type": "prompt",
                            "operation": str(operation or ""),
                        },
                    )
            if ct:
                increment_counter(
                    "llm_tokens_used_total",
                    float(ct),
                    labels={"provider": str(provider or "unknown"), "model": str(model or "unknown"), "type": "completion"},
                )
                if user_id is not None:
                    increment_counter(
                        "llm_tokens_used_total_by_user",
                        float(ct),
                        labels={
                            "provider": str(provider or "unknown"),
                            "model": str(model or "unknown"),
                            "type": "completion",
                            "user_id": str(user_id),
                        },
                    )
                if operation:
                    increment_counter(
                        "llm_tokens_used_total_by_operation",
                        float(ct),
                        labels={
                            "provider": str(provider or "unknown"),
                            "model": str(model or "unknown"),
                            "type": "completion",
                            "operation": str(operation or ""),
                        },
                    )
        except _USAGE_NONCRITICAL_EXCEPTIONS:
            # Metrics must never impact request flow
            pass

        db_pool: DatabasePool = await get_db_pool()
        repo = AuthnzUsageRepo(db_pool)
        await repo.insert_llm_usage_log(
            user_id=user_id,
            key_id=key_id,
            endpoint=endpoint,
            operation=operation,
            provider=provider,
            model=model,
            status=int(status),
            latency_ms=int(latency_ms),
            prompt_tokens=pt,
            completion_tokens=ct,
            total_tokens=tt,
            prompt_cost_usd=float(p_cost),
            completion_cost_usd=float(c_cost),
            total_cost_usd=float(t_cost),
            currency=currency,
            estimated=bool(estimated),
            request_id=request_id,
        )

        # Shadow-write daily token usage into the shared ResourceDailyLedger so
        # ResourceGovernor can enforce tokens-per-day caps cross-module.
        try:
            if tt > 0:
                ledger = await _get_tokens_daily_ledger()
                if ledger is not None and LedgerEntry is not None:
                    entity_scope = None
                    entity_value = None
                    try:
                        if user_id is not None:
                            entity_scope = "user"
                            entity_value = str(int(user_id))
                        elif key_id is not None:
                            entity_scope = "api_key"
                            entity_value = str(int(key_id))
                    except (TypeError, ValueError):
                        entity_scope = None
                        entity_value = None

                    if entity_scope and entity_value:
                        rid = str(request_id or "").strip()
                        if rid:
                            op_id = f"llm:{rid}:{operation}:{provider}:{model}:{pt}:{ct}:{tt}"
                        else:
                            op_id = f"llm:{operation}:{provider}:{model}:{int(time.time())}:{pt}:{ct}:{tt}"
                        entry = LedgerEntry(  # type: ignore[call-arg]
                            entity_scope=entity_scope,
                            entity_value=entity_value,
                            category="tokens",
                            units=int(tt),
                            op_id=str(op_id),
                            occurred_at=datetime.now(timezone.utc),
                        )
                        await ledger.add(entry)
        except _USAGE_NONCRITICAL_EXCEPTIONS:
            # Ledger writes must never affect request flow
            pass
    except _USAGE_NONCRITICAL_EXCEPTIONS as e:
        # Never break request processing due to logging errors
        logger.debug(f"LLM usage logging skipped/failed: {e}")
