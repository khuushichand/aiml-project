import pytest

from tldw_Server_API.app.core.AuthNZ import monitoring as monitoring_module
from tldw_Server_API.app.core.AuthNZ.monitoring import AuthNZMonitor, MetricType


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_record_metric_continues_when_prometheus_update_fails(monkeypatch):
    monitor = AuthNZMonitor()
    calls = {"store": 0, "check": 0}

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("prometheus down")

    async def _store(*_args, **_kwargs):
        calls["store"] += 1

    async def _check(*_args, **_kwargs):
        calls["check"] += 1

    monkeypatch.setattr(monitor, "_update_prometheus_metric", _boom)
    monkeypatch.setattr(monitor, "_store_metric_in_db", _store)
    monkeypatch.setattr(monitor, "_check_alert_conditions", _check)
    monkeypatch.setattr(monitoring_module, "PROMETHEUS_AVAILABLE", True)

    await monitor.record_metric(MetricType.AUTH_SUCCESS)

    assert calls["store"] == 1
    assert calls["check"] == 1


@pytest.mark.asyncio
async def test_auth_attempt_uses_attempt_status_label(monkeypatch):
    monitor = AuthNZMonitor()

    class _DummyCounter:
        def __init__(self):
            self.last_labels = None
            self.last_inc = None

        def labels(self, **kwargs):
            self.last_labels = kwargs
            return self

        def inc(self, value):
            self.last_inc = value

    dummy = _DummyCounter()

    monkeypatch.setattr(monitoring_module, "PROMETHEUS_AVAILABLE", True)
    monkeypatch.setattr(monitoring_module, "auth_attempts_total", dummy)

    await monitor._update_prometheus_metric(
        MetricType.AUTH_ATTEMPT,
        1.0,
        labels={"method": "password"},
    )

    assert dummy.last_labels == {"method": "password", "status": "attempt"}
