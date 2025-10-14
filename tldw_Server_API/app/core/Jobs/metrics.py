from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from loguru import logger

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
    defn = [
        MetricDefinition(
            name="prompt_studio.jobs.queued",
            type=MetricType.GAUGE,
            description="Jobs queued gauge",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.scheduled",
            type=MetricType.GAUGE,
            description="Jobs scheduled gauge (available_at in the future)",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.processing",
            type=MetricType.GAUGE,
            description="Jobs processing gauge",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.backlog",
            type=MetricType.GAUGE,
            description="Jobs backlog gauge (queued + scheduled)",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.duration_seconds",
            type=MetricType.HISTOGRAM,
            description="Job processing duration in seconds",
            unit="s",
            labels=["domain", "queue", "job_type"],
            buckets=[0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 900],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.queue_latency_seconds",
            type=MetricType.HISTOGRAM,
            description="Latency from enqueue to acquisition",
            unit="s",
            labels=["domain", "queue", "job_type"],
            buckets=[0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.retries_total",
            type=MetricType.COUNTER,
            description="Total job retries",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.failures_total",
            type=MetricType.COUNTER,
            description="Total job failures",
            labels=["domain", "queue", "job_type", "reason"],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.created_total",
            type=MetricType.COUNTER,
            description="Total jobs created",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.completed_total",
            type=MetricType.COUNTER,
            description="Total jobs completed",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.cancelled_total",
            type=MetricType.COUNTER,
            description="Total jobs cancelled",
            labels=["domain", "queue", "job_type"],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.stale_processing",
            type=MetricType.GAUGE,
            description="Count of processing jobs with expired leases",
            labels=["domain", "queue"],
        ),
        MetricDefinition(
            name="prompt_studio.jobs.time_to_expiry_seconds",
            type=MetricType.HISTOGRAM,
            description="Time remaining until lease expiry for processing jobs",
            unit="s",
            labels=["domain", "queue", "job_type"],
            buckets=[0.0, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800],
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
    get_metrics_registry().observe("prompt_studio.jobs.queue_latency_seconds", latency, _labels(job))


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
    get_metrics_registry().observe("prompt_studio.jobs.duration_seconds", duration, _labels(job))


def increment_retries(job: Dict) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    get_metrics_registry().increment("prompt_studio.jobs.retries_total", 1, _labels(job))


def increment_failures(job: Dict, reason: str = "unknown") -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    labels = _labels(job)
    labels = dict(labels)
    labels["reason"] = reason
    get_metrics_registry().increment("prompt_studio.jobs.failures_total", 1, labels)


def set_queue_gauges(domain: str, queue: str, job_type: Optional[str], queued: int, processing: int, backlog: Optional[int] = None, scheduled: Optional[int] = None) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    labels = {"domain": domain, "queue": queue, "job_type": job_type or ""}
    get_metrics_registry().set_gauge("prompt_studio.jobs.queued", float(queued), labels)
    get_metrics_registry().set_gauge("prompt_studio.jobs.processing", float(processing), labels)
    if backlog is not None:
        get_metrics_registry().set_gauge("prompt_studio.jobs.backlog", float(backlog), labels)
    if scheduled is not None:
        get_metrics_registry().set_gauge("prompt_studio.jobs.scheduled", float(scheduled), labels)


def set_stale_processing(domain: str, queue: str, count: int) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    labels = {"domain": domain, "queue": queue}
    get_metrics_registry().set_gauge("prompt_studio.jobs.stale_processing", float(count), labels)


def increment_created(job: Dict) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    get_metrics_registry().increment("prompt_studio.jobs.created_total", 1, _labels(job))


def increment_completed(job: Dict) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    get_metrics_registry().increment("prompt_studio.jobs.completed_total", 1, _labels(job))


def increment_cancelled(job: Dict) -> None:
    ensure_jobs_metrics_registered()
    if not get_metrics_registry:
        return
    get_metrics_registry().increment("prompt_studio.jobs.cancelled_total", 1, _labels(job))
