from __future__ import annotations

import pytest

from tldw_Server_API.app.core import config as app_config
from tldw_Server_API.app.core.MCP_unified.monitoring.metrics import MetricsCollector

pytestmark = pytest.mark.unit


def test_rollout_modes_resolve_off_shadow_enforce(monkeypatch):
    monkeypatch.delenv("GOVERNANCE_ROLLOUT_MODE", raising=False)

    assert app_config.resolve_governance_rollout_mode("off") == "off"
    assert app_config.resolve_governance_rollout_mode("shadow") == "shadow"
    assert app_config.resolve_governance_rollout_mode("enforce") == "enforce"
    assert app_config.resolve_governance_rollout_mode("invalid-value") == "off"

    monkeypatch.setenv("GOVERNANCE_ROLLOUT_MODE", "shadow")
    assert app_config.resolve_governance_rollout_mode() == "shadow"


def test_metrics_use_low_cardinality_labels_only():
    collector = MetricsCollector(enable_prometheus=False)
    collector.record_governance_check(
        surface="mcp_tool:req-12345",
        category="workspace-very-specific-9912",
        status="dynamic-status",
        rollout_mode="experimental",
    )

    internal = collector.get_internal_metrics(period_seconds=300)
    assert "governance_check" in internal

    labels = internal["governance_check"]["labels"][0]["labels"]
    assert labels["surface"] == "other"
    assert labels["category"] == "other"
    assert labels["status"] == "unknown"
    assert labels["rollout_mode"] == "off"


def test_audit_trace_persists_policy_and_rule_revision_refs():
    from tldw_Server_API.app.core.Governance.metrics import GovernanceMetrics

    collector = MetricsCollector(enable_prometheus=False)
    governance_metrics = GovernanceMetrics(metrics_collector=collector)

    trace = governance_metrics.record_check(
        surface="mcp_tool",
        category="security",
        status="deny",
        rollout_mode="shadow",
        policy_revision_ref="policy:v2",
        rule_revision_ref="rule:17",
    )

    assert trace["policy_revision_ref"] == "policy:v2"
    assert trace["rule_revision_ref"] == "rule:17"
    assert trace["rollout_mode"] == "shadow"
