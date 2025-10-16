"""
usage_tracker.py

Async helpers to log per-request LLM usage and compute costs.
Integrates with AuthNZ DatabasePool for both SQLite and Postgres.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool
from .pricing_catalog import get_pricing_catalog
from tldw_Server_API.app.core.Metrics import increment_counter


def _enabled() -> bool:
    try:
        settings = get_settings()
        val = getattr(settings, "LLM_USAGE_ENABLED", True)
        # Allow env to override
        env_val = os.getenv("LLM_USAGE_ENABLED")
        if env_val is not None:
            return str(env_val).strip().lower() in {"true", "1", "yes", "y", "on"}
        return bool(val)
    except Exception:
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
    user_id: Optional[int],
    key_id: Optional[int],
    endpoint: str,
    operation: str,
    provider: str,
    model: str,
    status: int,
    latency_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: Optional[int] = None,
    currency: str = "USD",
    request_id: Optional[str] = None,
    estimated: Optional[bool] = None,
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
        except Exception:
            # Metrics must never impact request flow
            pass

        db_pool: DatabasePool = await get_db_pool()
        if db_pool.pool:
            # PostgreSQL ($1, $2... params)
            query = (
                """
                INSERT INTO llm_usage_log (
                    ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
                    prompt_tokens, completion_tokens, total_tokens,
                    prompt_cost_usd, completion_cost_usd, total_cost_usd, currency, estimated, request_id
                ) VALUES (
                    CURRENT_TIMESTAMP, $1, $2, $3, $4, $5, $6, $7, $8,
                    $9, $10, $11,
                    $12, $13, $14, $15, $16, $17
                )
                """
            )
            await db_pool.execute(
                query,
                user_id,
                key_id,
                endpoint,
                operation,
                provider,
                model,
                int(status),
                int(latency_ms),
                pt,
                ct,
                tt,
                float(p_cost),
                float(c_cost),
                float(t_cost),
                currency,
                bool(estimated),
                request_id,
            )
        else:
            # SQLite ('?' params)
            query = (
                """
                INSERT INTO llm_usage_log (
                    ts, user_id, key_id, endpoint, operation, provider, model, status, latency_ms,
                    prompt_tokens, completion_tokens, total_tokens,
                    prompt_cost_usd, completion_cost_usd, total_cost_usd, currency, estimated, request_id
                ) VALUES (
                    CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """
            )
            await db_pool.execute(
                query,
                user_id,
                key_id,
                endpoint,
                operation,
                provider,
                model,
                int(status),
                int(latency_ms),
                pt,
                ct,
                tt,
                float(p_cost),
                float(c_cost),
                float(t_cost),
                currency,
                1 if estimated else 0,
                request_id,
            )
    except Exception as e:
        # Never break request processing due to logging errors
        logger.debug(f"LLM usage logging skipped/failed: {e}")
