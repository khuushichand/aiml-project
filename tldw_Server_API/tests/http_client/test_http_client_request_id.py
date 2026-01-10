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
def test_x_request_id_header_injected(monkeypatch):
     import httpx
    import tldw_Server_API.app.core.http_client as hc
    from tldw_Server_API.app.core.Metrics.traces import get_tracing_manager

    tm = get_tracing_manager()
    tm.set_baggage('request_id', 'req-123')

    seen = {"x_request_id": None}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["x_request_id"] = request.headers.get("X-Request-Id")
        return httpx.Response(200, request=request, text="ok")

    transport = httpx.MockTransport(handler)
    client = hc.create_client(transport=transport)
    try:
        resp = hc.fetch(method="GET", url="http://93.184.216.34/test", client=client)
        assert resp.status_code == 200
        assert seen["x_request_id"] == 'req-123'
    finally:
        client.close()
