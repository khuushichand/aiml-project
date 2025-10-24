from datetime import datetime

import pytest

from tldw_Server_API.app.core.Metrics import metrics_logger


@pytest.mark.parametrize(
    ("func", "call_args"),
    [
        (metrics_logger.log_counter, ("demo_counter", {"source": "test"}, 2)),
        (metrics_logger.log_histogram, ("demo_histogram", 0.42, {"source": "test"})),
        (metrics_logger.log_gauge, ("demo_gauge", 3.14, {"source": "test"})),
    ],
)
def test_metrics_logger_emits_valid_timestamp(monkeypatch, func, call_args):
    recorded = {}

    class StubLogger:
        def info(self, *args, **kwargs):
            recorded["extra"] = kwargs.get("extra")

    stub = StubLogger()
    monkeypatch.setattr(metrics_logger, "logger", stub)

    func(*call_args)

    extra = recorded.get("extra")
    assert extra is not None, "logger.info should be called with extra data"
    timestamp = extra["timestamp"]
    assert timestamp.endswith("Z")
    assert timestamp.count("Z") == 1

    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
