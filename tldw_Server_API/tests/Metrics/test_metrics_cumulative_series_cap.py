import pytest

import tldw_Server_API.app.core.Metrics.metrics_manager as metrics_manager
from tldw_Server_API.app.core.Metrics.metrics_manager import MetricDefinition, MetricType


pytestmark = pytest.mark.unit


def test_cumulative_counter_series_cap_drops_new_label_sets(monkeypatch):
    monkeypatch.setenv("METRICS_CUMULATIVE_SERIES_MAX_PER_METRIC", "1")
    metrics_manager._metrics_registry = None
    registry = metrics_manager.get_metrics_registry()

    try:
        registry.register_metric(
            MetricDefinition(
                name="cap_counter_total",
                type=MetricType.COUNTER,
                description="counter cap test",
                labels=["series"],
            )
        )

        registry.increment("cap_counter_total", labels={"series": "a"})
        registry.increment("cap_counter_total", labels={"series": "b"})  # dropped
        registry.increment("cap_counter_total", labels={"series": "a"})

        assert registry.get_cumulative_counter("cap_counter_total", {"series": "a"}) == 2
        assert registry.get_cumulative_counter("cap_counter_total", {"series": "b"}) == 0

        text = registry.export_prometheus_format()
        assert 'cap_counter_total{series="a"}' in text
        assert 'cap_counter_total{series="b"}' not in text
    finally:
        metrics_manager._metrics_registry = None


def test_cumulative_histogram_series_cap_drops_new_label_sets(monkeypatch):
    monkeypatch.setenv("METRICS_CUMULATIVE_SERIES_MAX_PER_METRIC", "1")
    metrics_manager._metrics_registry = None
    registry = metrics_manager.get_metrics_registry()

    try:
        registry.register_metric(
            MetricDefinition(
                name="cap_hist_seconds",
                type=MetricType.HISTOGRAM,
                description="hist cap test",
                labels=["series"],
                buckets=[0.1, 1.0],
            )
        )

        registry.observe("cap_hist_seconds", 0.2, labels={"series": "a"})
        registry.observe("cap_hist_seconds", 0.3, labels={"series": "b"})  # dropped
        registry.observe("cap_hist_seconds", 0.4, labels={"series": "a"})

        text = registry.export_prometheus_format()
        assert 'cap_hist_seconds_count{series="a"} 2' in text
        assert 'cap_hist_seconds_count{series="b"}' not in text
    finally:
        metrics_manager._metrics_registry = None
