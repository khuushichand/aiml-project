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
@pytest.mark.asyncio
async def test_sse_multiline_and_comments():
    import httpx
    from tldw_Server_API.app.core.http_client import astream_sse, create_async_client

    # Includes comments (:) and multi-line data, and id/retry reordering
    content = (
        b": comment about stream\n\n"
        b"event: notice\n"
        b"id: 42\n"
        b"data: line1\n"
        b"data: line2\n\n"
        b"retry: 5000\n"
        b"data: onlydata\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=content, headers={"Content-Type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    client = create_async_client(transport=transport)
    try:
        events = []
        async for ev in astream_sse(url="http://93.184.216.34/stream", client=client):
            events.append(ev)
            if len(events) >= 2:
                break
        assert events[0].event == "notice"
        assert events[0].id == "42"
        assert events[0].data == "line1\nline2"
        assert events[1].event == "message"
        assert events[1].data == "onlydata"
    finally:
        import asyncio
        await client.aclose()
