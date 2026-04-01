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

# --- Cardinality bounding for run-first metric labels ---
_KNOWN_OUTCOMES: frozenset[str] = frozenset({
    "success", "error", "timeout", "blocked",
    "end_turn", "max_iterations", "cancelled",
})
_KNOWN_INELIGIBLE_REASONS: frozenset[str] = frozenset({
    "none", "no_tools", "rollout_off", "run_missing",
    "provider_not_in_rollout_allowlist",
})
_LABEL_MAX_LEN = 64


def _clamp_label(
    value: str,
    known: frozenset[str] | None = None,
    max_len: int = _LABEL_MAX_LEN,
) -> str:
    """Normalize a metric label to a bounded set or truncate to *max_len*."""
    normalized = str(value or "").strip().lower() or "unknown"
    if known is not None:
        return normalized if normalized in known else "other"
    return normalized[:max_len]


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
        MetricDefinition(
            name="acp_run_first_rollout_total",
            type=MetricType.COUNTER,
            description="Total ACP run-first rollout exposures",
            labels=[
                "agent_type",
                "presentation_variant",
                "cohort",
                "provider",
                "model",
                "eligible",
                "ineligible_reason",
            ],
        ),
        MetricDefinition(
            name="acp_run_first_first_tool_total",
            type=MetricType.COUNTER,
            description="Total first-tool selections under ACP run-first rollout",
            labels=[
                "agent_type",
                "presentation_variant",
                "cohort",
                "provider",
                "model",
                "eligible",
                "ineligible_reason",
                "first_tool",
            ],
        ),
        MetricDefinition(
            name="acp_run_first_fallback_after_run_total",
            type=MetricType.COUNTER,
            description="Total typed-tool fallbacks after run under ACP rollout",
            labels=[
                "agent_type",
                "presentation_variant",
                "cohort",
                "provider",
                "model",
                "eligible",
                "ineligible_reason",
                "fallback_tool",
            ],
        ),
        MetricDefinition(
            name="acp_run_first_completion_proxy_total",
            type=MetricType.COUNTER,
            description="Total ACP run-first completion proxy outcomes",
            labels=[
                "agent_type",
                "presentation_variant",
                "cohort",
                "provider",
                "model",
                "eligible",
                "ineligible_reason",
                "outcome",
            ],
        ),
    ]

    for d in defs:
        try:
            registry.register_metric(d)
        except Exception as exc:
            logger.debug("ACP metric registration skipped for {}: {}", d.name, exc)

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


def _run_first_base_labels(
    *,
    agent_type: str = "mcp",
    presentation_variant: str = "unknown",
    cohort: str = "unknown",
    provider: str = "unknown",
    model: str = "unknown",
    eligible: bool = False,
    ineligible_reason: str | None = None,
) -> dict[str, str]:
    return {
        "agent_type": _clamp_label(agent_type),
        "presentation_variant": _clamp_label(presentation_variant),
        "cohort": _clamp_label(cohort),
        "provider": _clamp_label(provider),
        "model": _clamp_label(model),
        "eligible": str(bool(eligible)).lower(),
        "ineligible_reason": _clamp_label(
            str(ineligible_reason or "").strip() or "none",
            known=_KNOWN_INELIGIBLE_REASONS,
        ),
    }


def record_run_first_rollout(
    *,
    agent_type: str = "mcp",
    presentation_variant: str = "unknown",
    cohort: str = "unknown",
    provider: str = "unknown",
    model: str = "unknown",
    eligible: bool = False,
    ineligible_reason: str | None = None,
) -> None:
    _ensure_registered()
    increment_counter(
        "acp_run_first_rollout_total",
        labels=_run_first_base_labels(
            agent_type=agent_type,
            presentation_variant=presentation_variant,
            cohort=cohort,
            provider=provider,
            model=model,
            eligible=eligible,
            ineligible_reason=ineligible_reason,
        ),
    )


def record_run_first_first_tool(
    *,
    agent_type: str = "mcp",
    presentation_variant: str = "unknown",
    cohort: str = "unknown",
    provider: str = "unknown",
    model: str = "unknown",
    eligible: bool = False,
    ineligible_reason: str | None = None,
    first_tool: str,
) -> None:
    _ensure_registered()
    labels = _run_first_base_labels(
        agent_type=agent_type,
        presentation_variant=presentation_variant,
        cohort=cohort,
        provider=provider,
        model=model,
        eligible=eligible,
        ineligible_reason=ineligible_reason,
    )
    labels["first_tool"] = _clamp_label(first_tool)
    increment_counter("acp_run_first_first_tool_total", labels=labels)


def record_run_first_fallback_after_run(
    *,
    agent_type: str = "mcp",
    presentation_variant: str = "unknown",
    cohort: str = "unknown",
    provider: str = "unknown",
    model: str = "unknown",
    eligible: bool = False,
    ineligible_reason: str | None = None,
    fallback_tool: str,
) -> None:
    _ensure_registered()
    labels = _run_first_base_labels(
        agent_type=agent_type,
        presentation_variant=presentation_variant,
        cohort=cohort,
        provider=provider,
        model=model,
        eligible=eligible,
        ineligible_reason=ineligible_reason,
    )
    labels["fallback_tool"] = _clamp_label(fallback_tool)
    increment_counter("acp_run_first_fallback_after_run_total", labels=labels)


def record_run_first_completion_proxy(
    *,
    agent_type: str = "mcp",
    presentation_variant: str = "unknown",
    cohort: str = "unknown",
    provider: str = "unknown",
    model: str = "unknown",
    eligible: bool = False,
    ineligible_reason: str | None = None,
    outcome: str,
) -> None:
    _ensure_registered()
    labels = _run_first_base_labels(
        agent_type=agent_type,
        presentation_variant=presentation_variant,
        cohort=cohort,
        provider=provider,
        model=model,
        eligible=eligible,
        ineligible_reason=ineligible_reason,
    )
    labels["outcome"] = _clamp_label(outcome, known=_KNOWN_OUTCOMES)
    increment_counter("acp_run_first_completion_proxy_total", labels=labels)
