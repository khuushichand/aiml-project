import pytest

from tldw_Server_API.app.core.Metrics import metrics_logger
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.unit
def test_metrics_logger_bridge_records_counter():
    registry = get_metrics_registry()
    registry.reset()

    metric_name = "bridge_counter_test_total"
    metrics_logger.log_counter(metric_name, labels={"source": "test"}, value=2)

    assert registry.get_cumulative_counter(metric_name, {"source": "test"}) == 2


@pytest.mark.unit
def test_metrics_logger_bridge_records_histogram():
    registry = get_metrics_registry()
    registry.reset()

    metric_name = "bridge_histogram_test_seconds"
    metrics_logger.log_histogram(metric_name, 0.5, labels={"source": "test"})

    stats = registry.get_metric_stats(metric_name, labels={"source": "test"})
    assert stats.get("count") == 1
    assert stats.get("latest") == 0.5


@pytest.mark.unit
def test_metrics_logger_bridge_records_gauge():
    registry = get_metrics_registry()
    registry.reset()

    metric_name = "bridge_gauge_test"
    metrics_logger.log_gauge(metric_name, 3.14, labels={"source": "test"})

    stats = registry.get_metric_stats(metric_name, labels={"source": "test"})
    assert stats.get("count") == 1
    assert stats.get("latest") == 3.14
