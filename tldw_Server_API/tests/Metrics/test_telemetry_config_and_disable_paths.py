import pytest

import tldw_Server_API.app.core.Metrics.telemetry as telemetry_module
from tldw_Server_API.app.core.Metrics.telemetry import (
    DummyMeter,
    DummyTracer,
    TelemetryConfig,
    TelemetryManager,
)


pytestmark = pytest.mark.unit


def test_named_tracer_and_meter_are_dummy_when_sdk_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")

    manager = TelemetryManager()
    named_tracer = manager.get_tracer("test.named.tracer")
    named_meter = manager.get_meter("test.named.meter")

    assert isinstance(named_tracer, DummyTracer)
    assert isinstance(named_meter, DummyMeter)


def test_telemetry_config_invalid_numeric_env_falls_back_to_defaults(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_PORT", "not-a-number")
    monkeypatch.setenv("METRICS_EXPORT_INTERVAL_MS", "0")
    monkeypatch.setenv("TRACES_EXPORT_BATCH_SIZE", "-1")
    monkeypatch.setenv("TRACES_EXPORT_TIMEOUT_MS", "abc")
    monkeypatch.setenv("METRICS_SAMPLE_RATE", "2.5")

    cfg = TelemetryConfig()

    assert cfg.prometheus_port == 9090
    assert cfg.metrics_export_interval == 60000
    assert cfg.traces_export_batch_size == 512
    assert cfg.traces_export_timeout == 30000
    assert cfg.sample_rate == 1.0


def test_telemetry_config_defaults_trace_exporter_to_console(monkeypatch):
    monkeypatch.delenv("OTEL_TRACES_EXPORTER", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)

    cfg = TelemetryConfig()
    assert cfg.traces_exporters == ["console"]


def test_safe_console_stream_swallows_closed_file_errors():
    class ClosedStream:
        def write(self, message):
            raise ValueError("I/O operation on closed file.")

        def flush(self):
            raise ValueError("I/O operation on closed file.")

    safe = telemetry_module._SafeConsoleStream(ClosedStream())
    safe.write("hello")
    safe.flush()


def test_console_trace_exporter_uses_safe_stream():
    if not telemetry_module.OTEL_AVAILABLE:
        pytest.skip("OpenTelemetry SDK is not available")

    manager = object.__new__(TelemetryManager)
    exporter = TelemetryManager._create_trace_exporter(manager, "console")
    out_stream = getattr(exporter, "out", None)
    assert isinstance(out_stream, telemetry_module._SafeConsoleStream)
