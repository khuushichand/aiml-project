import os
import time
import asyncio
import json
import pytest


pytestmark = pytest.mark.performance


def _perf_enabled() -> bool:


    return os.getenv("PERF", "0").lower() in {"1", "true", "yes", "y", "on"}


pytestmark = pytest.mark.skipif(not _perf_enabled(), reason="set PERF=1 to run performance checks")


def test_non_streaming_throughput_openai_mock():


    """Quick non-streaming throughput check using MockTransport.

    Prints approximate QPS; does not assert strict thresholds to avoid flakiness.
    """
    import httpx
    from tldw_Server_API.app.core.http_client import create_client, fetch_json

    def handler(request: httpx.Request) -> httpx.Response:
        # Simulate OpenAI chat completion response
        payload = {
            "choices": [
                {"message": {"content": "ok"}}
            ]
        }
        return httpx.Response(200, request=request, text=json.dumps(payload), headers={"content-type": "application/json"})

    transport = httpx.MockTransport(handler)
    client = create_client(transport=transport)
    try:
        N = int(os.getenv("PERF_NON_STREAMING_N", "200"))
        t0 = time.time()
        for _ in range(N):
            out = fetch_json(method="POST", url="http://93.184.216.34/v1/chat/completions", client=client, json={})
            assert out.get("choices")
        dt = time.time() - t0
        qps = N / dt if dt > 0 else float("inf")
        print(f"non_streaming_throughput ops={N} time={dt:.3f}s qps={qps:.1f}")
    finally:
        client.close()


@pytest.mark.asyncio
async def test_streaming_throughput_openai_mock():
    """Quick streaming overhead check using a fixed SSE sequence via MockTransport.

    Prints approximate event rate.
    """
    import httpx
    from tldw_Server_API.app.core.http_client import create_async_client, astream_sse

    sse_body = (
        b"data: {\"choices\":[{\"delta\":{\"content\":\"a\"}}]}\n\n"
        b"data: {\"choices\":[{\"delta\":\"b\"}]}\n\n"
        b"data: {\"choices\":[{\"delta\":{\"content\":\"c\"}}]}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=sse_body, headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    async with create_async_client(transport=transport) as client:
        N = int(os.getenv("PERF_STREAM_EVENTS", "100"))
        t0 = time.time()
        count = 0
        for _ in range(N):
            async for _evt in astream_sse(url="http://93.184.216.34/v1/stream", client=client):
                count += 1
        dt = time.time() - t0
        eps = count / dt if dt > 0 else float("inf")
        print(f"streaming_events total={count} time={dt:.3f}s eps={eps:.1f}")


def test_download_throughput_mock(tmp_path):


    """Quick download throughput check using MockTransport and small payloads."""
    import httpx
    from tldw_Server_API.app.core.http_client import create_client, download

    payload = b"x" * 8192

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=payload, headers={"Content-Length": str(len(payload))})

    transport = httpx.MockTransport(handler)
    client = create_client(transport=transport)
    try:
        N = int(os.getenv("PERF_DOWNLOADS_N", "50"))
        t0 = time.time()
        for i in range(N):
            out = download(url=f"http://93.184.216.34/file-{i}", dest=tmp_path / f"f{i}.bin", client=client)
            assert out.exists()
        dt = time.time() - t0
        qps = N / dt if dt > 0 else float("inf")
        print(f"download_throughput ops={N} time={dt:.3f}s qps={qps:.1f}")
    finally:
        client.close()
