import pytest


class _StubTracingManager:
    def __init__(self):
        self.spans = []  # (name, attributes)

    # Context manager to mimic manager.span(...)
    def span(self, name, kind=None, attributes=None, links=None):
        class _Ctx:
            def __init__(self, outer, n, attrs):
                self.outer = outer
                self.n = n
                self.attrs = attrs or {}
            def __enter__(self):
                self.outer.spans.append((self.n, dict(self.attrs)))
                return object()
            def __exit__(self, exc_type, exc, tb):
                return False
        return _Ctx(self, name, attributes)


pytestmark = pytest.mark.integration


def test_pg_tracer_basic(prompt_studio_dual_backend_db, monkeypatch):
    label, db = prompt_studio_dual_backend_db
    if label != "postgres":
        pytest.skip("Postgres-specific tracer test")

    from tldw_Server_API.app.core.Metrics import traces
    # Patch get_tracing_manager to return a stub that records spans
    stub_mgr = _StubTracingManager()
    monkeypatch.setattr(traces, "get_tracing_manager", lambda: stub_mgr, raising=True)

    # Use trace_operation on a small function and ensure a span is created
    @traces.trace_operation(name="ps.pg.tracer.test", record_args=True)
    def _do_work(x):
        return x * 2

    out = _do_work(21)
    assert out == 42
    assert stub_mgr.spans, "no spans recorded by stub tracer"
    names = [n for (n, _) in stub_mgr.spans]
    assert "ps.pg.tracer.test" in names
