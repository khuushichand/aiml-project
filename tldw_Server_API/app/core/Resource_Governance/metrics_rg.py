from __future__ import annotations

"""
Resource Governor metrics registration and helpers.

Registers counters/gauges used by the Resource Governor. Metrics are only
registered once and are safe to call multiple times.
"""

import os
from typing import Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.Metrics.metrics_manager import (
    MetricDefinition,
    MetricType,
    get_metrics_registry,
)


_RG_METRICS_REGISTERED = False


def ensure_rg_metrics_registered() -> None:
    global _RG_METRICS_REGISTERED
    if _RG_METRICS_REGISTERED:
        return
    try:
        reg = get_metrics_registry()
        # Decisions (allow/deny) counters
        reg.register_metric(
            MetricDefinition(
                name="rg_decisions_total",
                type=MetricType.COUNTER,
                description="Resource Governor decisions (allow/deny)",
                labels=["category", "scope", "backend", "result", "policy_id"],
            )
        )
        # Denials counter (with reason)
        reg.register_metric(
            MetricDefinition(
                name="rg_denials_total",
                type=MetricType.COUNTER,
                description="Resource Governor denials by reason",
                labels=["category", "scope", "reason", "policy_id"],
            )
        )
        # Refunds counter (with reason)
        reg.register_metric(
            MetricDefinition(
                name="rg_refunds_total",
                type=MetricType.COUNTER,
                description="Resource Governor refunds by reason",
                labels=["category", "scope", "reason", "policy_id"],
            )
        )
        # Concurrency active gauge
        reg.register_metric(
            MetricDefinition(
                name="rg_concurrency_active",
                type=MetricType.GAUGE,
                description="Active concurrency leases",
                labels=["category", "scope", "policy_id"],
            )
        )
        # Wait histogram (optional, for backoff/queueing semantics)
        reg.register_metric(
            MetricDefinition(
                name="rg_wait_seconds",
                type=MetricType.HISTOGRAM,
                description="Estimated wait/retry seconds",
                unit="s",
                labels=["category", "scope", "policy_id"],
                buckets=[0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300],
            )
        )
        # Optional by-entity metrics (hashed) to keep cardinality manageable
        if rg_metrics_entity_label_enabled():
            reg.register_metric(
                MetricDefinition(
                    name="rg_decisions_by_entity_total",
                    type=MetricType.COUNTER,
                    description="RG decisions (allow/deny) by hashed entity",
                    labels=["category", "scope", "backend", "result", "policy_id", "entity"],
                )
            )
            reg.register_metric(
                MetricDefinition(
                    name="rg_denials_by_entity_total",
                    type=MetricType.COUNTER,
                    description="RG denials by reason and hashed entity",
                    labels=["category", "scope", "reason", "policy_id", "entity"],
                )
            )
            reg.register_metric(
                MetricDefinition(
                    name="rg_refunds_by_entity_total",
                    type=MetricType.COUNTER,
                    description="RG refunds by reason and hashed entity",
                    labels=["category", "scope", "reason", "policy_id", "entity"],
                )
            )
        _RG_METRICS_REGISTERED = True
    except Exception as e:  # pragma: no cover - metrics must never block
        logger.debug(f"RG metrics registration skipped: {e}")


def _labels(
    *,
    category: str,
    scope: str,
    backend: Optional[str] = None,
    result: Optional[str] = None,
    policy_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, str]:
    labels: Dict[str, str] = {
        "category": category,
        "scope": scope,
    }
    if backend is not None:
        labels["backend"] = backend
    if result is not None:
        labels["result"] = result
    if policy_id is not None:
        labels["policy_id"] = policy_id
    if reason is not None:
        labels["reason"] = reason
    return labels


def rg_metrics_entity_label_enabled() -> bool:
    try:
        v = os.getenv("RG_METRICS_ENTITY_LABEL")
        if v is None:
            return False
        return str(v).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False
