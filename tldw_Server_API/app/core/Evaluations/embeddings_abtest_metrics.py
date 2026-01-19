from __future__ import annotations

"""
Embeddings A/B testing metrics registration and helpers.

Importing this module ensures the A/B metrics exist so callers can record
without "not registered" warnings.
"""

from tldw_Server_API.app.core.Metrics import (
    MetricDefinition,
    MetricType,
    get_metrics_registry,
)


_METRICS_REGISTERED = False


def register_embeddings_abtest_metrics() -> None:
    global _METRICS_REGISTERED
    if _METRICS_REGISTERED:
        return
    reg = get_metrics_registry()

    reg.register_metric(MetricDefinition(
        name="embeddings_abtest_arm_builds_total",
        type=MetricType.COUNTER,
        description="Embeddings A/B arm collection builds (built/reused/failed)",
        labels=["status", "provider", "model"],
    ))
    reg.register_metric(MetricDefinition(
        name="embeddings_abtest_arm_build_duration_seconds",
        type=MetricType.HISTOGRAM,
        description="Embeddings A/B arm collection build duration in seconds",
        unit="s",
        labels=["status", "provider", "model"],
        buckets=[0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300],
    ))
    reg.register_metric(MetricDefinition(
        name="embeddings_abtest_runs_total",
        type=MetricType.COUNTER,
        description="Embeddings A/B test runs completed or failed",
        labels=["status"],
    ))
    reg.register_metric(MetricDefinition(
        name="embeddings_abtest_run_duration_seconds",
        type=MetricType.HISTOGRAM,
        description="Embeddings A/B test run duration in seconds",
        unit="s",
        labels=["status"],
        buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1200, 1800],
    ))

    _METRICS_REGISTERED = True


def record_abtest_arm_build(
    *,
    duration_seconds: float,
    status: str,
    provider: str,
    model: str,
) -> None:
    register_embeddings_abtest_metrics()
    reg = get_metrics_registry()
    labels = {"status": status, "provider": provider, "model": model}
    reg.increment("embeddings_abtest_arm_builds_total", labels=labels)
    reg.observe("embeddings_abtest_arm_build_duration_seconds", duration_seconds, labels=labels)


def record_abtest_run(*, duration_seconds: float, status: str) -> None:
    register_embeddings_abtest_metrics()
    reg = get_metrics_registry()
    labels = {"status": status}
    reg.increment("embeddings_abtest_runs_total", labels=labels)
    reg.observe("embeddings_abtest_run_duration_seconds", duration_seconds, labels=labels)


try:
    register_embeddings_abtest_metrics()
except Exception:
    pass
