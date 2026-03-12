"""ACP observability metrics.

Registers ACP-specific counters and gauges with the unified MetricsRegistry
so they appear on the ``/metrics`` Prometheus endpoint.
"""
from __future__ import annotations

from loguru import logger

from tldw_Server_API.app.core.Metrics import (
    MetricDefinition,
    MetricType,
    get_metrics_registry,
    increment_counter,
    set_gauge,
    observe_histogram,
)


_ACP_METRICS_REGISTERED = False


def _ensure_registered() -> None:
    """Lazily register ACP metrics on first use."""
    global _ACP_METRICS_REGISTERED
    if _ACP_METRICS_REGISTERED:
        return

    registry = get_metrics_registry()

    defs = [
        MetricDefinition(
            name="acp_active_sessions",
            type=MetricType.GAUGE,
            description="Number of currently active ACP sessions",
            labels=["agent_type"],
        ),
        MetricDefinition(
            name="acp_sessions_created_total",
            type=MetricType.COUNTER,
            description="Total number of ACP sessions created",
            labels=["agent_type"],
        ),
        MetricDefinition(
            name="acp_sessions_closed_total",
            type=MetricType.COUNTER,
            description="Total number of ACP sessions closed",
            labels=["reason"],
        ),
        MetricDefinition(
            name="acp_prompts_total",
            type=MetricType.COUNTER,
            description="Total prompts sent to ACP agents",
            labels=["agent_type"],
        ),
        MetricDefinition(
            name="acp_prompt_latency_seconds",
            type=MetricType.HISTOGRAM,
            description="ACP prompt response latency in seconds",
            labels=["agent_type"],
        ),
        MetricDefinition(
            name="acp_token_usage_total",
            type=MetricType.COUNTER,
            description="Total tokens consumed by ACP sessions",
            labels=["agent_type", "direction"],
        ),
        MetricDefinition(
            name="acp_governance_blocks_total",
            type=MetricType.COUNTER,
            description="Total governance policy blocks",
            labels=["policy", "agent_type"],
        ),
        MetricDefinition(
            name="acp_errors_total",
            type=MetricType.COUNTER,
            description="Total ACP errors",
            labels=["error_type"],
        ),
        MetricDefinition(
            name="acp_quota_rejections_total",
            type=MetricType.COUNTER,
            description="Total quota-based rejections (429s)",
            labels=["quota_type"],
        ),
        MetricDefinition(
            name="acp_orchestration_tasks_total",
            type=MetricType.COUNTER,
            description="Total orchestration tasks created",
            labels=["status"],
        ),
        MetricDefinition(
            name="acp_orchestration_runs_total",
            type=MetricType.COUNTER,
            description="Total orchestration runs dispatched",
            labels=["status"],
        ),
    ]

    for d in defs:
        try:
            registry.register_metric(d)
        except Exception:
            pass  # Already registered

    _ACP_METRICS_REGISTERED = True
    logger.debug("ACP metrics registered with MetricsRegistry")


# ---- Convenience wrappers ----


def record_session_created(agent_type: str = "unknown") -> None:
    _ensure_registered()
    increment_counter("acp_sessions_created_total", labels={"agent_type": agent_type})


def record_session_closed(reason: str = "normal") -> None:
    _ensure_registered()
    increment_counter("acp_sessions_closed_total", labels={"reason": reason})


def set_active_sessions(count: int, agent_type: str = "all") -> None:
    _ensure_registered()
    set_gauge("acp_active_sessions", count, labels={"agent_type": agent_type})


def record_prompt(agent_type: str = "unknown") -> None:
    _ensure_registered()
    increment_counter("acp_prompts_total", labels={"agent_type": agent_type})


def record_prompt_latency(seconds: float, agent_type: str = "unknown") -> None:
    _ensure_registered()
    observe_histogram(
        "acp_prompt_latency_seconds", seconds, labels={"agent_type": agent_type}
    )


def record_token_usage(
    tokens: int, agent_type: str = "unknown", direction: str = "total"
) -> None:
    _ensure_registered()
    increment_counter(
        "acp_token_usage_total",
        value=tokens,
        labels={"agent_type": agent_type, "direction": direction},
    )


def record_governance_block(policy: str, agent_type: str = "unknown") -> None:
    _ensure_registered()
    increment_counter(
        "acp_governance_blocks_total",
        labels={"policy": policy, "agent_type": agent_type},
    )


def record_error(error_type: str = "unknown") -> None:
    _ensure_registered()
    increment_counter("acp_errors_total", labels={"error_type": error_type})


def record_quota_rejection(quota_type: str = "concurrent_sessions") -> None:
    _ensure_registered()
    increment_counter(
        "acp_quota_rejections_total", labels={"quota_type": quota_type}
    )


def record_orchestration_task(status: str = "created") -> None:
    _ensure_registered()
    increment_counter("acp_orchestration_tasks_total", labels={"status": status})


def record_orchestration_run(status: str = "dispatched") -> None:
    _ensure_registered()
    increment_counter("acp_orchestration_runs_total", labels={"status": status})
