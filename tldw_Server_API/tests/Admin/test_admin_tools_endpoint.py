from __future__ import annotations

import sys
import types

import pytest

from tldw_Server_API.app.api.v1.endpoints.admin import admin_tools


pytestmark = pytest.mark.unit


class _FakeCollector:
    def get_internal_metrics(self, *, period_seconds: int) -> dict[str, object]:
        assert period_seconds == 3600
        return {
            "module_alpha_tools_call": {
                "labels": [
                    {"labels": {"module": "alpha", "tool": "search"}, "count": 2, "avg": 0.1},
                    {"labels": {"module": "alpha", "tool": "search"}, "count": 1, "avg": 0.2},
                    {"labels": {"module": "alpha", "tool": "summarize"}, "count": 1, "avg": 0.4},
                    {"labels": {"module": "beta", "tool": "lookup"}, "count": 3, "avg": 0.05},
                ]
            }
        }


@pytest.mark.asyncio
async def test_get_mcp_tool_usage_aggregates_metrics_from_label_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.SimpleNamespace(get_metrics_collector=lambda: _FakeCollector())
    monkeypatch.setitem(
        sys.modules,
        "tldw_Server_API.app.core.MCP_unified.monitoring.metrics",
        fake_module,
    )

    result = await admin_tools.get_mcp_tool_usage(period_seconds=3600)

    assert result.modules["alpha"].calls == 4
    assert result.modules["alpha"].avg_latency_ms == 200.0
    assert result.modules["beta"].calls == 3
    assert result.modules["beta"].avg_latency_ms == 50.0
    assert result.tools["alpha.search"].calls == 3
    assert result.tools["alpha.search"].avg_latency_ms == 133.3
    assert result.tools["alpha.summarize"].calls == 1
    assert result.tools["alpha.summarize"].avg_latency_ms == 400.0

