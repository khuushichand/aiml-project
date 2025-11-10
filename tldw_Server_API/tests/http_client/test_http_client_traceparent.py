import pytest


pytestmark = pytest.mark.unit


def _has_httpx():
    try:
        import httpx  # noqa: F401
        return True
    except Exception:
        return False


requires_httpx = pytest.mark.skipif(not _has_httpx(), reason="httpx not installed")


@requires_httpx
def test_traceparent_header_injected_with_fake_span(monkeypatch):
    import httpx
    import tldw_Server_API.app.core.http_client as hc

    # Force OTEL available path and provide a fake current span
    class FakeSpanContext:
        def __init__(self):
            # Non-zero IDs to trigger header injection
            self.trace_id = int("0123456789abcdef0123456789abcdef", 16)
            self.span_id = int("0123456789abcdef", 16)

    class FakeSpan:
        def get_span_context(self):
            return FakeSpanContext()

    class FakeTracer:
        @staticmethod
        def get_current_span():
            return FakeSpan()

    monkeypatch.setattr(hc, "_OTEL_AVAILABLE", True)
    monkeypatch.setattr(hc, "_otel_trace", FakeTracer)

    seen = {"traceparent": None}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["traceparent"] = request.headers.get("traceparent")
        return httpx.Response(200, request=request, text="ok")

    transport = httpx.MockTransport(handler)
    client = hc.create_client(transport=transport)
    try:
        resp = hc.fetch(method="GET", url="http://93.184.216.34/trace", client=client)
        assert resp.status_code == 200
        assert seen["traceparent"] is not None
        # Basic shape: 00-<32 hex>-<16 hex>-01
        parts = seen["traceparent"].split("-")
        assert len(parts) == 4
        assert parts[0] == "00"
        assert len(parts[1]) == 32 and len(parts[2]) == 16
    finally:
        client.close()
