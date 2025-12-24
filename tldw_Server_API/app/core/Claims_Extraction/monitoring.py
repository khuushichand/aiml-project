"""Claims monitoring helpers."""

from __future__ import annotations

from typing import Optional, Dict, Any


_CLAIMS_METRICS_REGISTERED = False


def _claims_monitoring_enabled() -> bool:
    """Return True when claims monitoring is enabled in settings."""
    try:
        from tldw_Server_API.app.core.config import settings
    except Exception:
        return True
    return bool(settings.get("CLAIMS_MONITORING_ENABLED", False))


def _estimate_tokens(text: str) -> int:
    """Estimate tokens using a simple character heuristic."""
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def estimate_claims_cost(*, provider: str, model: str, text: str) -> Optional[float]:
    """Estimate provider cost using configured multipliers and a token heuristic."""
    try:
        from tldw_Server_API.app.core.config import settings
    except Exception:
        return None
    multipliers = settings.get("CLAIMS_PROVIDER_COST_MULTIPLIERS") or {}
    if not isinstance(multipliers, dict):
        return None
    provider_key = str(provider or "").strip()
    model_key = str(model or "").strip()
    key_candidates = [
        f"{provider_key}/{model_key}" if provider_key and model_key else "",
        f"{provider_key}:{model_key}" if provider_key and model_key else "",
        model_key,
        provider_key,
        "default",
    ]
    multiplier = None
    for key in key_candidates:
        if key and key in multipliers:
            multiplier = multipliers.get(key)
            break
    if multiplier is None:
        return None
    try:
        multiplier_val = float(multiplier)
    except Exception:
        return None
    tokens = _estimate_tokens(text)
    if tokens <= 0:
        return None
    return float(tokens) / 1000.0 * multiplier_val


def _register_claims_metrics() -> None:
    global _CLAIMS_METRICS_REGISTERED
    if _CLAIMS_METRICS_REGISTERED:
        return
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import (
            get_metrics_registry,
            MetricDefinition,
            MetricType,
        )
    except Exception:
        return

    reg = get_metrics_registry()
    reg.register_metric(
        MetricDefinition(
            name="claims_provider_requests_total",
            type=MetricType.COUNTER,
            description="Total claim provider requests",
            labels=["provider", "model", "mode"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_provider_latency_seconds",
            type=MetricType.HISTOGRAM,
            description="Claim provider latency in seconds",
            unit="s",
            labels=["provider", "model"],
            buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_provider_errors_total",
            type=MetricType.COUNTER,
            description="Claim provider errors",
            labels=["provider", "model", "reason"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_provider_estimated_cost_usd_total",
            type=MetricType.COUNTER,
            description="Estimated claim extraction cost",
            unit="usd",
            labels=["provider", "model"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_rebuild_queue_size",
            type=MetricType.GAUGE,
            description="Claims rebuild queue size",
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_rebuild_processed_total",
            type=MetricType.COUNTER,
            description="Claims rebuild jobs processed",
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_rebuild_failed_total",
            type=MetricType.COUNTER,
            description="Claims rebuild jobs failed",
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_rebuild_job_duration_seconds",
            type=MetricType.HISTOGRAM,
            description="Claims rebuild job duration",
            unit="s",
            buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 60],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_rebuild_worker_heartbeat_timestamp",
            type=MetricType.GAUGE,
            description="Claims rebuild worker heartbeat timestamp",
            unit="timestamp",
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_review_queue_size",
            type=MetricType.GAUGE,
            description="Claims review queue size",
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_review_processed_total",
            type=MetricType.COUNTER,
            description="Claims review actions processed",
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_review_latency_seconds",
            type=MetricType.HISTOGRAM,
            description="Claims review latency in seconds",
            unit="s",
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 86400],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="rag_total_claims_checked_total",
            type=MetricType.COUNTER,
            description="Total number of claims checked during RAG post-check",
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="rag_unsupported_claims_total",
            type=MetricType.COUNTER,
            description="Number of unsupported claims during RAG post-check",
        )
    )
    _CLAIMS_METRICS_REGISTERED = True


def record_postcheck_metrics(total_claims: int, unsupported_claims: int) -> None:
    """Record post-generation verification counters for claims."""
    _register_claims_metrics()
    if total_claims <= 0 and unsupported_claims <= 0:
        return
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
    except Exception:
        return
    try:
        if total_claims > 0:
            increment_counter("rag_total_claims_checked_total", total_claims)
        if unsupported_claims > 0:
            increment_counter("rag_unsupported_claims_total", unsupported_claims)
    except Exception:
        pass


def record_claims_provider_request(
    *,
    provider: str,
    model: str,
    mode: str,
    latency_s: Optional[float] = None,
    error: Optional[str] = None,
    estimated_cost: Optional[float] = None,
) -> None:
    if not _claims_monitoring_enabled():
        return
    _register_claims_metrics()
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import (
            increment_counter,
            observe_histogram,
        )
    except Exception:
        return
    labels = {
        "provider": str(provider),
        "model": str(model or ""),
        "mode": str(mode or ""),
    }
    increment_counter("claims_provider_requests_total", 1, labels=labels)
    if latency_s is not None:
        observe_histogram("claims_provider_latency_seconds", float(latency_s), labels={
            "provider": str(provider),
            "model": str(model or ""),
        })
    if error:
        increment_counter(
            "claims_provider_errors_total",
            1,
            labels={
                "provider": str(provider),
                "model": str(model or ""),
                "reason": str(error),
            },
        )
    if estimated_cost is not None:
        increment_counter(
            "claims_provider_estimated_cost_usd_total",
            float(estimated_cost),
            labels={"provider": str(provider), "model": str(model or "")},
        )


def record_claims_rebuild_metrics(
    *,
    queue_size: Optional[int] = None,
    processed: Optional[int] = None,
    failed: Optional[int] = None,
    duration_s: Optional[float] = None,
    heartbeat_ts: Optional[float] = None,
) -> None:
    if not _claims_monitoring_enabled():
        return
    _register_claims_metrics()
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import (
            increment_counter,
            observe_histogram,
            set_gauge,
        )
    except Exception:
        return
    if queue_size is not None:
        set_gauge("claims_rebuild_queue_size", float(queue_size))
    if processed:
        increment_counter("claims_rebuild_processed_total", int(processed))
    if failed:
        increment_counter("claims_rebuild_failed_total", int(failed))
    if duration_s is not None:
        observe_histogram("claims_rebuild_job_duration_seconds", float(duration_s))
    if heartbeat_ts is not None:
        set_gauge("claims_rebuild_worker_heartbeat_timestamp", float(heartbeat_ts))


def record_claims_review_metrics(
    *,
    queue_size: Optional[int] = None,
    processed: Optional[int] = None,
    latency_s: Optional[float] = None,
) -> None:
    if not _claims_monitoring_enabled():
        return
    _register_claims_metrics()
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import (
            increment_counter,
            observe_histogram,
            set_gauge,
        )
    except Exception:
        return
    if queue_size is not None:
        set_gauge("claims_review_queue_size", float(queue_size))
    if processed:
        increment_counter("claims_review_processed_total", int(processed))
    if latency_s is not None:
        observe_histogram("claims_review_latency_seconds", float(latency_s))
