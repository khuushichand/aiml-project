import contextlib

import pytest

import tldw_Server_API.app.core.Metrics.telemetry as telemetry_module
from tldw_Server_API.app.core.Metrics.telemetry import TelemetryManager


pytestmark = pytest.mark.unit


def test_trace_context_marks_custom_exception_on_span(monkeypatch):
    class TestError(Exception):
        pass

    class StubStatusCode:
        ERROR = "error"

    class StubStatus:
        def __init__(self, code, description):
            self.code = code
            self.description = description

    class StubSpan:
        def __init__(self):
            self.recorded = []
            self.statuses = []

        def set_attribute(self, key, value):
            pass

        def record_exception(self, exception):
            self.recorded.append(exception)

        def set_status(self, status):
            self.statuses.append(status)

    span = StubSpan()

    @contextlib.contextmanager
    def span_cm():
        yield span

    class StubTracer:
        def start_as_current_span(self, *args, **kwargs):
            return span_cm()

    monkeypatch.setattr(telemetry_module, "OTEL_AVAILABLE", True, raising=False)
    monkeypatch.setattr(telemetry_module, "StatusCode", StubStatusCode, raising=False)
    monkeypatch.setattr(telemetry_module, "Status", StubStatus, raising=False)

    manager = TelemetryManager()
    monkeypatch.setattr(manager, "get_tracer", lambda name=None: StubTracer(), raising=True)

    with pytest.raises(TestError):
        with manager.trace_context("test.operation"):
            raise TestError("boom")

    assert len(span.recorded) == 1
    assert isinstance(span.recorded[0], TestError)
    assert len(span.statuses) == 1
    assert span.statuses[0].code == StubStatusCode.ERROR
    assert span.statuses[0].description == "boom"
