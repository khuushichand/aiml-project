import sys
import types
import asyncio

import pytest

from tldw_Server_API.app.core.MCP_unified.monitoring import metrics as metrics_module


MetricsCollector = metrics_module.MetricsCollector


def _labels_by_key(entries):
    return {
        frozenset(item["labels"].items()): item
        for item in entries
    }


def test_metrics_collector_records_status_labels():
    collector = MetricsCollector(enable_prometheus=False)
    collector.record_request("resources/list", duration=0.1, status="success")
    collector.record_request("resources/list", duration=0.2, status="failure")

    internal = collector.get_internal_metrics(period_seconds=300)
    assert "request_resources/list" in internal

    entry = internal["request_resources/list"]
    assert entry["type"] == "histogram"
    assert entry["sum"] == pytest.approx(0.3, rel=1e-9)

    label_entries = _labels_by_key(entry["labels"])
    success_key = frozenset({("status", "success")})
    failure_key = frozenset({("status", "failure")})
    assert success_key in label_entries
    assert failure_key in label_entries
    assert label_entries[success_key]["count"] == 1
    assert label_entries[failure_key]["count"] == 1
    assert label_entries[success_key]["sum"] == pytest.approx(0.1, rel=1e-9)
    assert label_entries[failure_key]["sum"] == pytest.approx(0.2, rel=1e-9)


@pytest.mark.asyncio
async def test_metrics_collector_cpu_sampling_nonblocking(monkeypatch):
    collector = MetricsCollector(enable_prometheus=False)

    fake_psutil = types.SimpleNamespace()
    fake_psutil.virtual_memory = lambda: types.SimpleNamespace(used=123)

    def fake_cpu_percent(*, interval=None):
        assert interval is None
        return 45.6

    fake_psutil.cpu_percent = fake_cpu_percent
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)

    async def fake_to_thread(func, *args, **kwargs):
        assert func is fake_cpu_percent
        assert kwargs == {"interval": None}
        return func(*args, **kwargs)

    monkeypatch.setattr(metrics_module.asyncio, "to_thread", fake_to_thread)

    await collector._sample_system_metrics()
    internal = collector.get_internal_metrics(period_seconds=300)

    mem_entry = internal["memory_usage"]
    cpu_entry = internal["cpu_usage"]

    assert mem_entry["type"] == "gauge"
    assert mem_entry["value"] == pytest.approx(123.0)
    assert mem_entry["labels"][0]["value"] == pytest.approx(123.0)

    assert cpu_entry["type"] == "gauge"
    assert cpu_entry["value"] == pytest.approx(45.6)
    assert cpu_entry["labels"][0]["value"] == pytest.approx(45.6)
