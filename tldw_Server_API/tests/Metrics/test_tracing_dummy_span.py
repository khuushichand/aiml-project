import contextlib

import pytest


pytestmark = pytest.mark.unit


def test_tracing_manager_handles_span_without_context(monkeypatch):
    from tldw_Server_API.app.core.Metrics import traces

    class StubSpan:
        def record_exception(self, *args, **kwargs):
            pass

        def set_status(self, *args, **kwargs):
            pass

    @contextlib.contextmanager
    def span_cm():
        yield StubSpan()

    class StubTracer:
        def start_as_current_span(self, *args, **kwargs):
            return span_cm()

    class StubTelemetry:
        def get_tracer(self, name=None):
            return StubTracer()

    monkeypatch.setattr(traces, "OTEL_AVAILABLE", True, raising=False)
    monkeypatch.setattr(traces, "get_telemetry_manager", lambda: StubTelemetry(), raising=True)

    manager = traces.TracingManager()
    with manager.span("dummy-span") as span:
        assert span is not None

    assert manager.active_spans == {}
