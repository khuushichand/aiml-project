import pytest

from tldw_Server_API.app.core.Resource_Governance.metrics_rg import (
    ensure_rg_metrics_registered,
    record_shadow_mismatch,
)
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


pytestmark = pytest.mark.rate_limit


def test_record_shadow_mismatch_increments_counter():
    ensure_rg_metrics_registered()
    reg = get_metrics_registry()

    labels = {
        "module": "chat",
        "route": "/api/v1/chat/completions",
        "policy_id": "chat.default",
        "legacy": "allow",
        "rg": "deny",
    }

    before = reg.get_metric_stats("rg_shadow_decision_mismatch_total", labels=labels) or {}
    before_count = int(before.get("count", 0) or 0)

    record_shadow_mismatch(**labels)

    after = reg.get_metric_stats("rg_shadow_decision_mismatch_total", labels=labels) or {}
    after_count = int(after.get("count", 0) or 0)

    assert after_count == before_count + 1

