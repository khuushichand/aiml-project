"""Claims monitoring helpers."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Optional, Dict, Any, Tuple


_CLAIMS_METRICS_REGISTERED = False
_CLAIMS_PROVIDER_STATS: Dict[Tuple[str, str], "ClaimsProviderStats"] = {}
_CLAIMS_PROVIDER_STATS_LOCK = threading.Lock()


@dataclass
class ClaimsProviderStats:
    requests: int = 0
    errors: int = 0
    latency_ewma_ms: Optional[float] = None
    cost_ewma_usd: Optional[float] = None
    last_error_ts: Optional[float] = None

    def error_rate(self) -> float:
        if self.requests <= 0:
            return 0.0
        return float(self.errors) / float(self.requests)


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
            name="claims_provider_budget_exhausted_total",
            type=MetricType.COUNTER,
            description="Claims provider budget guardrail hits",
            labels=["provider", "model", "mode", "reason"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_provider_throttled_total",
            type=MetricType.COUNTER,
            description="Claims provider throttling applied",
            labels=["provider", "model", "mode", "reason"],
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
            name="claims_alert_webhook_delivered_total",
            type=MetricType.COUNTER,
            description="Claims alert webhook deliveries",
            labels=["status"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_alert_webhook_failed_total",
            type=MetricType.COUNTER,
            description="Claims alert webhook failures",
            labels=["reason"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_alert_webhook_latency_seconds",
            type=MetricType.HISTOGRAM,
            description="Claims alert webhook latency in seconds",
            unit="s",
            labels=["status"],
            buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_alert_email_delivered_total",
            type=MetricType.COUNTER,
            description="Claims alert email deliveries",
            labels=["status"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_alert_email_failed_total",
            type=MetricType.COUNTER,
            description="Claims alert email failures",
            labels=["reason"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_alert_email_latency_seconds",
            type=MetricType.HISTOGRAM,
            description="Claims alert email delivery latency in seconds",
            unit="s",
            labels=["status"],
            buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_review_webhook_delivered_total",
            type=MetricType.COUNTER,
            description="Claims review webhook deliveries",
            labels=["status"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_review_webhook_failed_total",
            type=MetricType.COUNTER,
            description="Claims review webhook failures",
            labels=["reason"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_review_webhook_latency_seconds",
            type=MetricType.HISTOGRAM,
            description="Claims review webhook latency in seconds",
            unit="s",
            labels=["status"],
            buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_review_email_delivered_total",
            type=MetricType.COUNTER,
            description="Claims review email deliveries",
            labels=["status"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_review_email_failed_total",
            type=MetricType.COUNTER,
            description="Claims review email failures",
            labels=["reason"],
        )
    )
    reg.register_metric(
        MetricDefinition(
            name="claims_review_email_latency_seconds",
            type=MetricType.HISTOGRAM,
            description="Claims review email latency in seconds",
            unit="s",
            labels=["status"],
            buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10],
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
    _update_claims_provider_stats(
        provider=str(provider or ""),
        model=str(model or ""),
        latency_s=latency_s,
        error=error,
        estimated_cost=estimated_cost,
    )


def record_claims_budget_exhausted(
    *,
    provider: str,
    model: str,
    mode: str,
    reason: str,
) -> None:
    if not _claims_monitoring_enabled():
        return
    _register_claims_metrics()
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
    except Exception:
        return
    increment_counter(
        "claims_provider_budget_exhausted_total",
        1,
        labels={
            "provider": str(provider or ""),
            "model": str(model or ""),
            "mode": str(mode or ""),
            "reason": str(reason or "unknown"),
        },
    )


def record_claims_throttle(
    *,
    provider: str,
    model: str,
    mode: str,
    reason: str,
) -> None:
    if not _claims_monitoring_enabled():
        return
    _register_claims_metrics()
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
    except Exception:
        return
    increment_counter(
        "claims_provider_throttled_total",
        1,
        labels={
            "provider": str(provider or ""),
            "model": str(model or ""),
            "mode": str(mode or ""),
            "reason": str(reason or "unknown"),
        },
    )


def _update_claims_provider_stats(
    *,
    provider: str,
    model: str,
    latency_s: Optional[float],
    error: Optional[str],
    estimated_cost: Optional[float],
) -> None:
    key = (str(provider or ""), str(model or ""))
    with _CLAIMS_PROVIDER_STATS_LOCK:
        stats = _CLAIMS_PROVIDER_STATS.get(key)
        if stats is None:
            stats = ClaimsProviderStats()
            _CLAIMS_PROVIDER_STATS[key] = stats
        stats.requests += 1
        if error:
            stats.errors += 1
            stats.last_error_ts = time.time()
        if latency_s is not None:
            latency_ms = float(latency_s) * 1000.0
            if stats.latency_ewma_ms is None:
                stats.latency_ewma_ms = latency_ms
            else:
                stats.latency_ewma_ms = (stats.latency_ewma_ms * 0.8) + (latency_ms * 0.2)
        if estimated_cost is not None:
            cost_val = float(estimated_cost)
            if stats.cost_ewma_usd is None:
                stats.cost_ewma_usd = cost_val
            else:
                stats.cost_ewma_usd = (stats.cost_ewma_usd * 0.8) + (cost_val * 0.2)


def get_claims_provider_stats(provider: str, model: str) -> ClaimsProviderStats:
    key = (str(provider or ""), str(model or ""))
    with _CLAIMS_PROVIDER_STATS_LOCK:
        stats = _CLAIMS_PROVIDER_STATS.get(key)
        if stats is None:
            return ClaimsProviderStats()
        return ClaimsProviderStats(
            requests=stats.requests,
            errors=stats.errors,
            latency_ewma_ms=stats.latency_ewma_ms,
            cost_ewma_usd=stats.cost_ewma_usd,
            last_error_ts=stats.last_error_ts,
        )


def should_throttle_claims_provider(
    *,
    provider: str,
    model: str,
    budget_ratio: Optional[float] = None,
) -> Tuple[bool, Optional[str]]:
    try:
        from tldw_Server_API.app.core.config import settings
    except Exception:
        settings = {}
    if not bool(settings.get("CLAIMS_ADAPTIVE_THROTTLE_ENABLED", False)):
        return False, None

    stats = get_claims_provider_stats(provider, model)
    try:
        latency_threshold = float(settings.get("CLAIMS_ADAPTIVE_THROTTLE_LATENCY_MS", 0) or 0)
    except Exception:
        latency_threshold = 0.0
    try:
        error_threshold = float(settings.get("CLAIMS_ADAPTIVE_THROTTLE_ERROR_RATE", 0) or 0)
    except Exception:
        error_threshold = 0.0
    try:
        budget_threshold = float(settings.get("CLAIMS_ADAPTIVE_THROTTLE_BUDGET_RATIO", 0) or 0)
    except Exception:
        budget_threshold = 0.0

    if latency_threshold > 0 and stats.latency_ewma_ms is not None and stats.latency_ewma_ms > latency_threshold:
        return True, "latency"
    if error_threshold > 0 and stats.error_rate() > error_threshold:
        return True, "error_rate"
    if budget_threshold > 0 and budget_ratio is not None and budget_ratio <= budget_threshold:
        return True, "budget_ratio"
    return False, None


def suggest_claims_concurrency(
    *,
    provider: str,
    model: str,
    requested: int,
    budget_ratio: Optional[float] = None,
) -> int:
    try:
        from tldw_Server_API.app.core.config import settings
    except Exception:
        settings = {}
    if not bool(settings.get("CLAIMS_ADAPTIVE_THROTTLE_ENABLED", False)):
        return requested

    stats = get_claims_provider_stats(provider, model)
    target = int(requested)
    try:
        latency_threshold = float(settings.get("CLAIMS_ADAPTIVE_THROTTLE_LATENCY_MS", 0) or 0)
    except Exception:
        latency_threshold = 0.0
    try:
        error_threshold = float(settings.get("CLAIMS_ADAPTIVE_THROTTLE_ERROR_RATE", 0) or 0)
    except Exception:
        error_threshold = 0.0
    try:
        budget_threshold = float(settings.get("CLAIMS_ADAPTIVE_THROTTLE_BUDGET_RATIO", 0) or 0)
    except Exception:
        budget_threshold = 0.0

    if latency_threshold > 0 and stats.latency_ewma_ms is not None and stats.latency_ewma_ms > latency_threshold:
        target = max(1, int(round(target / 2.0)))
    if error_threshold > 0 and stats.error_rate() > error_threshold:
        target = 1
    if budget_threshold > 0 and budget_ratio is not None and budget_ratio <= budget_threshold:
        target = min(target, 1)
    return max(1, target)


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


def record_claims_webhook_delivery(
    *,
    status: str,
    reason: Optional[str] = None,
    latency_s: Optional[float] = None,
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
    increment_counter(
        "claims_alert_webhook_delivered_total",
        1,
        labels={"status": str(status)},
    )
    if reason:
        increment_counter(
            "claims_alert_webhook_failed_total",
            1,
            labels={"reason": str(reason)},
        )
    if latency_s is not None:
        observe_histogram(
            "claims_alert_webhook_latency_seconds",
            float(latency_s),
            labels={"status": str(status)},
        )


def record_claims_alert_email_delivery(
    *,
    status: str,
    reason: Optional[str] = None,
    latency_s: Optional[float] = None,
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
    increment_counter(
        "claims_alert_email_delivered_total",
        1,
        labels={"status": str(status)},
    )
    if reason:
        increment_counter(
            "claims_alert_email_failed_total",
            1,
            labels={"reason": str(reason)},
        )
    if latency_s is not None:
        observe_histogram(
            "claims_alert_email_latency_seconds",
            float(latency_s),
            labels={"status": str(status)},
        )


def record_claims_review_webhook_delivery(
    *,
    status: str,
    reason: Optional[str] = None,
    latency_s: Optional[float] = None,
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
    increment_counter(
        "claims_review_webhook_delivered_total",
        1,
        labels={"status": str(status)},
    )
    if reason:
        increment_counter(
            "claims_review_webhook_failed_total",
            1,
            labels={"reason": str(reason)},
        )
    if latency_s is not None:
        observe_histogram(
            "claims_review_webhook_latency_seconds",
            float(latency_s),
            labels={"status": str(status)},
        )


def record_claims_review_email_delivery(
    *,
    status: str,
    reason: Optional[str] = None,
    latency_s: Optional[float] = None,
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
    increment_counter(
        "claims_review_email_delivered_total",
        1,
        labels={"status": str(status)},
    )
    if reason:
        increment_counter(
            "claims_review_email_failed_total",
            1,
            labels={"reason": str(reason)},
        )
    if latency_s is not None:
        observe_histogram(
            "claims_review_email_latency_seconds",
            float(latency_s),
            labels={"status": str(status)},
        )
