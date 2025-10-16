from __future__ import annotations

"""
Workflows metrics registration and helpers.

Defines Prometheus/OpenTelemetry metric instruments used by the Workflows
engine and endpoints. Importing this module ensures metrics exist to avoid
"not registered" warnings when recording.
"""

from tldw_Server_API.app.core.Metrics import (
    MetricDefinition,
    MetricType,
    get_metrics_registry,
)


def register_workflows_metrics() -> None:
    r = get_metrics_registry()

    # Run lifecycle
    r.register_metric(MetricDefinition(
        name="workflows_runs_started",
        type=MetricType.COUNTER,
        description="Workflow runs started",
        labels=["tenant", "mode"],
    ))
    r.register_metric(MetricDefinition(
        name="workflows_runs_completed",
        type=MetricType.COUNTER,
        description="Workflow runs completed successfully",
        labels=["tenant"],
    ))
    r.register_metric(MetricDefinition(
        name="workflows_runs_failed",
        type=MetricType.COUNTER,
        description="Workflow runs failed",
        labels=["tenant"],
    ))
    r.register_metric(MetricDefinition(
        name="workflows_run_duration_ms",
        type=MetricType.HISTOGRAM,
        description="Workflow run duration in milliseconds",
        unit="ms",
        labels=["tenant"],
        buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000, 120000],
    ))

    # Steps
    r.register_metric(MetricDefinition(
        name="workflows_steps_started",
        type=MetricType.COUNTER,
        description="Workflow steps started",
        labels=["type"],
    ))
    r.register_metric(MetricDefinition(
        name="workflows_steps_succeeded",
        type=MetricType.COUNTER,
        description="Workflow steps succeeded",
        labels=["type"],
    ))
    r.register_metric(MetricDefinition(
        name="workflows_steps_failed",
        type=MetricType.COUNTER,
        description="Workflow steps failed",
        labels=["type"],
    ))
    r.register_metric(MetricDefinition(
        name="workflows_step_duration_ms",
        type=MetricType.HISTOGRAM,
        description="Workflow step duration in milliseconds",
        unit="ms",
        labels=["type", "tenant"],
        buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
    ))

    # Webhooks
    r.register_metric(MetricDefinition(
        name="workflows_webhook_deliveries_total",
        type=MetricType.COUNTER,
        description="Completion/webhook delivery attempts",
        labels=["status", "host"],  # status: delivered|failed|blocked
    ))

    # Engine
    r.register_metric(MetricDefinition(
        name="workflows_engine_queue_depth",
        type=MetricType.GAUGE,
        description="Number of queued workflow runs in scheduler",
        labels=[],
    ))


# Register eagerly on import
try:
    register_workflows_metrics()
except Exception:
    pass
