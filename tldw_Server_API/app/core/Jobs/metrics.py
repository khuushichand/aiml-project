from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
import random

from loguru import logger
import os

def _parse_buckets(env_key: str, default: list[float]) -> list[float]:
    try:
        raw = os.getenv(env_key, "")
        if not raw:
            return default
        vals = []
        for part in raw.split(","):
            s = part.strip()
            if not s:
                continue
            vals.append(float(s))
        return vals or default
    except Exception:
        return default

try:
    from tldw_Server_API.app.core.Metrics.metrics_manager import (
        get_metrics_registry,
        MetricDefinition,
        MetricType,
    )
except Exception:  # pragma: no cover - metrics optional
    get_metrics_registry = None  # type: ignore
    MetricDefinition = None  # type: ignore
    MetricType = None  # type: ignore


JOBS_METRICS_REGISTERED = False


def ensure_jobs_metrics_registered() -> None:
    """Register Jobs metrics with the central registry, if available."""
    global JOBS_METRICS_REGISTERED
    if JOBS_METRICS_REGISTERED:
        return
    if not get_metrics_registry or not MetricDefinition or not MetricType:
        logger.debug("Metrics registry not available; skipping Jobs metrics registration")
        JOBS_METRICS_REGISTERED = True
        return
    reg = get_metrics_registry()
    # Configurable buckets
    duration_buckets = _parse_buckets(
        "JOBS_DURATION_BUCKETS", [0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 900]
    )
    queue_buckets = _parse_buckets(
        "JOBS_QUEUE_LATENCY_BUCKETS", [0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300]
    )

    defn = [
        MetricDefinition(
            name="jobs.queued",
            type=MetricType.GAUGE,
            description="Jobs queued gauge",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="jobs.sla_breaches_total",
            type=MetricType.COUNTER,
            description="Total SLA breaches (queue_latency/duration)",
            labels=["domain", "queue", "job_type", "kind"],
        ),
        MetricDefinition(
            name="jobs.queue_flag",
            type=MetricType.GAUGE,
            description="Queue control flags (paused/drain)",
            labels=["domain", "queue", "flag"],
        ),
        MetricDefinition(
            name="jobs.scheduled",
            type=MetricType.GAUGE,
            description="Jobs scheduled gauge (available_at in the future)",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="jobs.processing",
            type=MetricType.GAUGE,
            description="Jobs processing gauge",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="jobs.backlog",
            type=MetricType.GAUGE,
            description="Jobs backlog gauge (queued + scheduled)",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="jobs.duration_seconds",
            type=MetricType.HISTOGRAM,
            description="Job processing duration in seconds",
            unit="s",
            labels=["domain", "queue", "job_type"],
            buckets=duration_buckets,
        ),
        MetricDefinition(
            name="jobs.queue_latency_seconds",
            type=MetricType.HISTOGRAM,
            description="Latency from enqueue to acquisition",
            unit="s",
            labels=["domain", "queue", "job_type"],
            buckets=queue_buckets,
        ),
        MetricDefinition(
            name="jobs.retries_total",
            type=MetricType.COUNTER,
            description="Total job retries",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="jobs.failures_total",
            type=MetricType.COUNTER,
            description="Total job failures",
            labels=["domain", "queue", "job_type", "reason"],
        ),
        MetricDefinition(
            name="jobs.failures_by_code_total",
            type=MetricType.COUNTER,
            description="Total job failures by error_code",
            labels=["domain", "queue", "job_type", "error_code"],
        ),
        MetricDefinition(
            name="jobs.created_total",
            type=MetricType.COUNTER,
            description="Total jobs created",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="jobs.completed_total",
            type=MetricType.COUNTER,
            description="Total jobs completed",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="jobs.cancelled_total",
            type=MetricType.COUNTER,
            description="Total jobs cancelled",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="jobs.json_truncated_total",
            type=MetricType.COUNTER,
            description="Total JSON truncation events (payload/result)",
            labels=["domain", "queue", "job_type", "kind"],
        ),
        MetricDefinition(
            name="jobs.stale_processing",
            type=MetricType.GAUGE,
            description="Count of processing jobs with expired leases",
            labels=["domain", "queue"],
        ),
        MetricDefinition(
            name="jobs.time_to_expiry_seconds",
            type=MetricType.HISTOGRAM,
            description="Time remaining until lease expiry for processing jobs",
            unit="s",
            labels=["domain", "queue", "job_type"],
            buckets=[0.0, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800],
        ),
        MetricDefinition(
            name="jobs.retry_after_seconds",
            type=MetricType.HISTOGRAM,
            description="Retry backoff seconds applied when rescheduling failures",
            unit="s",
            labels=["domain", "queue", "job_type"],
            buckets=[0.0, 1, 2, 5, 10, 30, 60, 120, 300, 600],
        ),
        # Per-owner SLO gauges (P50/P90/P99)
        MetricDefinition(
            name="jobs.queue_latency_p50_seconds",
            type=MetricType.GAUGE,
            description="P50 queue latency per owner and job_type",
            unit="s",
            labels=["domain", "queue", "job_type", "owner_user_id"],
        ),
        MetricDefinition(
            name="jobs.queue_latency_p90_seconds",
            type=MetricType.GAUGE,
            description="P90 queue latency per owner and job_type",
            unit="s",
            labels=["domain", "queue", "job_type", "owner_user_id"],
        ),
        MetricDefinition(
            name="jobs.queue_latency_p99_seconds",
            type=MetricType.GAUGE,
            description="P99 queue latency per owner and job_type",
            unit="s",
            labels=["domain", "queue", "job_type", "owner_user_id"],
        ),
        MetricDefinition(
            name="jobs.duration_p50_seconds",
            type=MetricType.GAUGE,
            description="P50 processing duration per owner and job_type",
            unit="s",
            labels=["domain", "queue", "job_type", "owner_user_id"],
        ),
        MetricDefinition(
            name="jobs.duration_p90_seconds",
            type=MetricType.GAUGE,
            description="P90 processing duration per owner and job_type",
            unit="s",
            labels=["domain", "queue", "job_type", "owner_user_id"],
        ),
        MetricDefinition(
            name="jobs.duration_p99_seconds",
            type=MetricType.GAUGE,
            description="P99 processing duration per owner and job_type",
            unit="s",
            labels=["domain", "queue", "job_type", "owner_user_id"],
        ),
    ]
    for d in defn:
        try:
            reg.register_metric(d)
        except Exception as e:  # pragma: no cover
            logger.debug(f"Jobs metrics registration skipped for {d.name}: {e}")
    JOBS_METRICS_REGISTERED = True


def _labels(job: Dict) -> Dict[str, str]:
    return {
        "domain": str(job.get("domain", "")),
        "queue": str(job.get("queue", "")),
        "job_type": str(job.get("job_type", "")),
    }


def observe_queue_latency(job: Dict, acquired_at: Optional[datetime], created_at: Optional[datetime]) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    if not acquired_at or not created_at:
        return
    latency = max(0.0, (acquired_at - created_at).total_seconds())
    labels = _labels(job)
    # Optional exemplars: attach sample of trace/request IDs as labels at a low rate
    try:
        if os.getenv("JOBS_METRICS_EXEMPLARS", "").lower() in {"1","true","yes","y","on"}:
            rate = float(os.getenv("JOBS_METRICS_EXEMPLAR_SAMPLING", "0.01") or "0.01")
            if random.random() < max(0.0, min(1.0, rate)):
                if job.get("trace_id"):
                    labels = dict(labels)
                    labels["trace_id"] = str(job.get("trace_id"))
                if job.get("request_id"):
                    labels = dict(labels)
                    labels["request_id"] = str(job.get("request_id"))
    except Exception:
        pass
    get_metrics_registry().observe("jobs.queue_latency_seconds", latency, labels)


def observe_duration(job: Dict, started_at: Optional[datetime], completed_at: Optional[datetime]) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    start = started_at or job.get("acquired_at")
    if not completed_at or not start:
        return
    try:
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
    except Exception:
        return
    duration = max(0.0, (completed_at - start).total_seconds())
    labels = _labels(job)
    try:
        if os.getenv("JOBS_METRICS_EXEMPLARS", "").lower() in {"1","true","yes","y","on"}:
            rate = float(os.getenv("JOBS_METRICS_EXEMPLAR_SAMPLING", "0.01") or "0.01")
            if random.random() < max(0.0, min(1.0, rate)):
                if job.get("trace_id"):
                    labels = dict(labels)
                    labels["trace_id"] = str(job.get("trace_id"))
                if job.get("request_id"):
                    labels = dict(labels)
                    labels["request_id"] = str(job.get("request_id"))
    except Exception:
        pass
    get_metrics_registry().observe("jobs.duration_seconds", duration, labels)


def increment_retries(job: Dict) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    get_metrics_registry().increment("jobs.retries_total", 1, _labels(job))


def increment_failures(job: Dict, reason: str = "unknown") -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    labels = _labels(job)
    labels = dict(labels)
    labels["reason"] = reason
    get_metrics_registry().increment("jobs.failures_total", 1, labels)


def increment_failures_by_code(job: Dict, error_code: str) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    labels = _labels(job)
    labels = dict(labels)
    labels["error_code"] = str(error_code)
    get_metrics_registry().increment("jobs.failures_by_code_total", 1, labels)


def observe_retry_after(job: Dict, seconds: float) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    get_metrics_registry().observe("jobs.retry_after_seconds", float(seconds), _labels(job))


def set_queue_gauges(domain: str, queue: str, job_type: Optional[str], queued: int, processing: int, backlog: Optional[int] = None, scheduled: Optional[int] = None) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    labels = {"domain": domain, "queue": queue, "job_type": job_type or ""}
    get_metrics_registry().set_gauge("jobs.queued", float(queued), labels)
    get_metrics_registry().set_gauge("jobs.processing", float(processing), labels)
    if backlog is not None:
        get_metrics_registry().set_gauge("jobs.backlog", float(backlog), labels)
    if scheduled is not None:
        get_metrics_registry().set_gauge("jobs.scheduled", float(scheduled), labels)


def set_stale_processing(domain: str, queue: str, count: int) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    labels = {"domain": domain, "queue": queue}
    get_metrics_registry().set_gauge("jobs.stale_processing", float(count), labels)


def increment_created(job: Dict) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    get_metrics_registry().increment("jobs.created_total", 1, _labels(job))


def increment_completed(job: Dict) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    get_metrics_registry().increment("jobs.completed_total", 1, _labels(job))


def increment_cancelled(job: Dict) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    get_metrics_registry().increment("jobs.cancelled_total", 1, _labels(job))


def increment_json_truncated(job: Dict, kind: str) -> None:
    """Increment counter when payload/result JSON is truncated due to caps."""
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    labels = _labels(job)
    labels = dict(labels)
    labels["kind"] = str(kind)
    get_metrics_registry().increment("jobs.json_truncated_total", 1, labels)


def increment_sla_breach(job: Dict, kind: str) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    labels = _labels(job)
    labels = dict(labels)
    labels["kind"] = str(kind)
    get_metrics_registry().increment("jobs.sla_breaches_total", 1, labels)


def set_queue_flag(domain: str, queue: str, flag: str, value: bool) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    get_metrics_registry().set_gauge("jobs.queue_flag", 1.0 if value else 0.0, {"domain": domain, "queue": queue, "flag": flag})
