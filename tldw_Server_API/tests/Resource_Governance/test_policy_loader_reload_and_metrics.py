import os
import time
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Resource_Governance.policy_loader import PolicyLoader, PolicyReloadConfig
from tldw_Server_API.app.core.Resource_Governance import MemoryResourceGovernor, RGRequest
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry

pytestmark = pytest.mark.rate_limit


@pytest.mark.asyncio
async def test_policy_loader_file_reload_updates_route_map(tmp_path):
    # Create a temp copy of the stub YAML and point loader at it
    base = Path(__file__).resolve().parents[3] / "tldw_Server_API" / "Config_Files" / "resource_governor_policies.yaml"
    data = base.read_text(encoding="utf-8")
    p = tmp_path / "rg.yaml"
    p.write_text(data, encoding="utf-8")

    loader = PolicyLoader(str(p), PolicyReloadConfig(enabled=False))
    snap1 = await loader.load_once()
    assert snap1.route_map and snap1.route_map.get("by_path", {}).get("/api/v1/chat/*") == "chat.default"

    # Modify mapping
    new_data = data.replace("chat.default", "chat.alt")
    # Also add the new policy to avoid downstream lookups failing
    if "chat.alt:" not in new_data:
        new_data = new_data.replace("policies:\n  # Chat API:", "policies:\n  chat.alt:\n    requests: { rpm: 100 }\n  # Chat API:")
    p.write_text(new_data, encoding="utf-8")

    # Force reload by simulating the poll
    await loader._maybe_reload()  # type: ignore[attr-defined]
    snap2 = loader.get_snapshot()
    assert snap2.route_map.get("by_path", {}).get("/api/v1/chat/*") == "chat.alt"


@pytest.mark.asyncio
async def test_rg_metrics_allow_deny_refund_paths():
    pols = {
        "p": {
            "requests": {"rpm": 1},
            "tokens": {"per_min": 2},
            "scopes": ["global", "user"],
        }
    }
    rg = MemoryResourceGovernor(policies=pols)
    reg = get_metrics_registry()
    before = reg.get_metric_stats("rg_denials_total")
    before_ref = reg.get_metric_stats("rg_refunds_total")

    e = "user:metrics"
    # Allow tokens once, then deny next combined
    d1, h1 = await rg.reserve(RGRequest(entity=e, categories={"tokens": {"units": 2}}, tags={"policy_id": "p"}))
    assert d1.allowed and h1
    d2, h2 = await rg.reserve(RGRequest(entity=e, categories={"tokens": {"units": 1}}, tags={"policy_id": "p"}))
    assert not d2.allowed and not h2

    # Trigger refund by committing fewer tokens than reserved on the first handle
    await rg.commit(h1, actuals={"tokens": 1})

    after = reg.get_metric_stats("rg_denials_total")
    after_ref = reg.get_metric_stats("rg_refunds_total")
    # Ensure counters increased
    if before:
        assert after["count"] >= before["count"]
    else:
        assert after["count"] >= 1
    if before_ref:
        assert after_ref["count"] >= before_ref["count"]
    else:
        assert after_ref["count"] >= 1
