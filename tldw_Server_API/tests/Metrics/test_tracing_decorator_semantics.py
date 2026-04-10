import asyncio
import contextlib

import pytest

import tldw_Server_API.app.core.Metrics.traces as traces_module

pytestmark = pytest.mark.unit


def _install_otel_like_tracing_manager(monkeypatch):
    class StubStatusCode:
        ERROR = "ERROR"

    class StubStatus:
        def __init__(self, code, description=None):
            self.code = code
            self.description = description

    class StubSpanContext:
        def __init__(self):
            self.span_id = 1

    class StubSpan:
        def __init__(self):
            self.recorded = []
            self.statuses = []

        def get_span_context(self):
            return StubSpanContext()

        def set_attribute(self, key, value):
            pass

        def record_exception(self, exc):
            self.recorded.append(exc)

        def set_status(self, status):
            self.statuses.append(status)

    class StubTracer:
        def __init__(self):
            self.latest_span = None

        def start_as_current_span(self, *args, **kwargs):
            record_exception = kwargs.get("record_exception", True)
            set_status_on_exception = kwargs.get("set_status_on_exception", True)
            span = StubSpan()
            self.latest_span = span

            @contextlib.contextmanager
            def span_cm():
                try:
                    yield span
                except Exception as exc:
                    if record_exception:
                        span.record_exception(exc)
                    if set_status_on_exception:
                        span.set_status(("auto", str(exc)))
                    raise

            return span_cm()

    class StubTelemetry:
        def __init__(self, tracer):
            self._tracer = tracer

        def get_tracer(self, name=None):
            return self._tracer

    tracer = StubTracer()
    monkeypatch.setattr(traces_module, "OTEL_AVAILABLE", True, raising=False)
    monkeypatch.setattr(traces_module, "Status", StubStatus, raising=False)
    monkeypatch.setattr(traces_module, "StatusCode", StubStatusCode, raising=False)
    monkeypatch.setattr(traces_module, "get_telemetry_manager", lambda: StubTelemetry(tracer), raising=True)

    manager = traces_module.TracingManager()
    monkeypatch.setattr(traces_module, "get_tracing_manager", lambda: manager)
    return tracer


@pytest.mark.asyncio
async def test_trace_method_preserves_async_method_semantics(monkeypatch):
    class StubAsyncSpan:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class StubManager:
        def async_span(self, *args, **kwargs):
            return StubAsyncSpan()

    monkeypatch.setattr(traces_module, "get_tracing_manager", lambda: StubManager())

    class Service:
        @traces_module.trace_method(name="service.work")
        async def work(self):
            return "ok"

    assert asyncio.iscoroutinefunction(Service.work)
    assert await Service().work() == "ok"


def test_trace_operation_records_exception_once_with_real_manager(monkeypatch):
    tracer = _install_otel_like_tracing_manager(monkeypatch)

    @traces_module.trace_operation(name="sync.fail")
    def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        fail()

    assert tracer.latest_span is not None
    assert len(tracer.latest_span.recorded) == 1
    assert len(tracer.latest_span.statuses) == 1


@pytest.mark.asyncio
async def test_trace_operation_records_exception_once_with_real_manager_async(monkeypatch):
    tracer = _install_otel_like_tracing_manager(monkeypatch)

    @traces_module.trace_operation(name="async.fail")
    async def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await fail()

    assert tracer.latest_span is not None
    assert len(tracer.latest_span.recorded) == 1
    assert len(tracer.latest_span.statuses) == 1
