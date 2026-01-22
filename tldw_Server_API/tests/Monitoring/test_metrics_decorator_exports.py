import pytest

from tldw_Server_API.app.core.Metrics import cache_metrics, measure_latency
import tldw_Server_API.app.core.Metrics.metrics_manager as metrics_manager

pytestmark = pytest.mark.monitoring


def test_measure_latency_exports_default_buckets(monkeypatch):


    monkeypatch.setenv("METRICS_RING_BUFFER_MAXLEN_OR_UNBOUNDED", "50")
    metrics_manager._metrics_registry = None
    registry = metrics_manager.get_metrics_registry()

    try:
        @measure_latency(metric_name="test_latency_seconds")
        def sample():
            return "ok"

        sample()
        text = registry.export_prometheus_format()

        assert "test_latency_seconds_bucket" in text
        assert 'test_latency_seconds_bucket{le="0.1"}' in text
    finally:
        metrics_manager._metrics_registry = None


def test_cache_hit_ratio_uses_cumulative_counters(monkeypatch):


    monkeypatch.setenv("METRICS_RING_BUFFER_MAXLEN_OR_UNBOUNDED", "2")
    metrics_manager._metrics_registry = None
    registry = metrics_manager.get_metrics_registry()

    try:
        @cache_metrics("demo_cache", track_ratio=True)
        def fetch(cache_hit: bool):
            return "payload", cache_hit

        fetch(False)
        fetch(True)
        fetch(True)
        fetch(True)

        stats = registry.get_metric_stats("cache_hit_ratio", {"cache": "demo_cache"})
        assert stats["latest"] == pytest.approx(3 / 4)
    finally:
        metrics_manager._metrics_registry = None
