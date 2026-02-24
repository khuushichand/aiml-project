"""Governance rollout, metrics, and audit trace helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from tldw_Server_API.app.core.MCP_unified.monitoring.metrics import (
    MetricsCollector,
    get_metrics_collector,
)


class GovernanceRolloutMode(str, Enum):
    """Rollout strategy for governance enforcement."""

    OFF = "off"
    SHADOW = "shadow"
    ENFORCE = "enforce"


def resolve_rollout_mode(
    raw_mode: str | None,
    default: GovernanceRolloutMode = GovernanceRolloutMode.OFF,
) -> GovernanceRolloutMode:
    """Resolve a rollout mode value with deterministic fallback."""
    safe_default = default if isinstance(default, GovernanceRolloutMode) else GovernanceRolloutMode.OFF
    candidate = str(raw_mode or "").strip().lower()
    if not candidate:
        return safe_default
    try:
        return GovernanceRolloutMode(candidate)
    except ValueError:
        return safe_default


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _coerce_matched_rules(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item).strip())
    rendered = str(value).strip()
    return (rendered,) if rendered else ()


@dataclass(frozen=True)
class GovernanceAuditTrace:
    """Immutable governance decision trace payload."""

    surface: str
    category: str
    status: str
    rollout_mode: GovernanceRolloutMode
    policy_revision_ref: str | None = None
    rule_revision_ref: str | None = None
    fallback_reason: str | None = None
    matched_rules: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rollout_mode"] = self.rollout_mode.value
        return payload


def build_audit_trace(
    *,
    surface: str,
    category: str,
    status: str,
    rollout_mode: GovernanceRolloutMode | str,
    policy_revision_ref: str | None = None,
    rule_revision_ref: str | None = None,
    decision: Mapping[str, Any] | None = None,
) -> GovernanceAuditTrace:
    """Build a governance audit trace with revision refs."""
    decision_map = dict(decision or {})
    mode = resolve_rollout_mode(
        rollout_mode.value if isinstance(rollout_mode, GovernanceRolloutMode) else str(rollout_mode),
    )

    resolved_policy_ref = (
        _optional_text(policy_revision_ref)
        or _optional_text(decision_map.get("policy_revision_ref"))
    )
    resolved_rule_ref = (
        _optional_text(rule_revision_ref)
        or _optional_text(decision_map.get("rule_revision_ref"))
    )
    fallback_reason = _optional_text(decision_map.get("fallback_reason"))
    matched_rules = _coerce_matched_rules(decision_map.get("matched_rules"))

    return GovernanceAuditTrace(
        surface=str(surface or "").strip().lower() or "other",
        category=str(category or "").strip().lower() or "general",
        status=str(status or "").strip().lower() or "unknown",
        rollout_mode=mode,
        policy_revision_ref=resolved_policy_ref,
        rule_revision_ref=resolved_rule_ref,
        fallback_reason=fallback_reason,
        matched_rules=matched_rules,
    )


class GovernanceMetrics:
    """Emit governance metrics and produce audit traces."""

    def __init__(self, metrics_collector: MetricsCollector | None = None) -> None:
        self._metrics_collector = metrics_collector

    def _collector(self) -> MetricsCollector:
        return self._metrics_collector or get_metrics_collector()

    def record_check(
        self,
        *,
        surface: str,
        category: str,
        status: str,
        rollout_mode: GovernanceRolloutMode | str,
        policy_revision_ref: str | None = None,
        rule_revision_ref: str | None = None,
        decision: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record one governance decision and return its trace payload."""
        mode = resolve_rollout_mode(
            rollout_mode.value if isinstance(rollout_mode, GovernanceRolloutMode) else str(rollout_mode),
        )
        normalized_surface = str(surface or "").strip().lower() or "other"
        normalized_category = str(category or "").strip().lower() or "general"
        normalized_status = str(status or "").strip().lower() or "unknown"

        self._collector().record_governance_check(
            surface=normalized_surface,
            category=normalized_category,
            status=normalized_status,
            rollout_mode=mode.value,
        )

        trace = build_audit_trace(
            surface=normalized_surface,
            category=normalized_category,
            status=normalized_status,
            rollout_mode=mode,
            policy_revision_ref=policy_revision_ref,
            rule_revision_ref=rule_revision_ref,
            decision=decision,
        )
        return trace.to_dict()
