import json
import pytest
import asyncio

from tldw_Server_API.app.core.Streaming.streams import SSEStream, WebSocketStream


@pytest.mark.asyncio
async def test_sse_send_json_and_done():
    stream = SSEStream(heartbeat_interval_s=None)

    async def collect(n: int):
        out = []
        async for line in stream.iter_sse():
            out.append(line)
            if len(out) >= n:
                break
        return out

    collector = asyncio.create_task(collect(2))
    await stream.send_json({"hello": "world"})
    await stream.done()
    lines = await collector

    assert lines[0].startswith("data: ")
    payload = json.loads(lines[0].split("data: ", 1)[1])
    assert payload == {"hello": "world"}
    assert lines[1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_sse_error_auto_done():
    stream = SSEStream(heartbeat_interval_s=None)

    async def collect_until_done():
        out = []
        async for line in stream.iter_sse():
            out.append(line)
            if line.strip().lower() == "data: [done]":
                break
        return out

    collector = asyncio.create_task(collect_until_done())
    await stream.error("internal_error", "boom")
    lines = await collector

    assert len(lines) == 2
    err = json.loads(lines[0].split("data: ", 1)[1])
    assert err["error"]["code"] == "internal_error"
    assert err["error"]["message"] == "boom"
    assert lines[1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_sse_raw_line_ensure_terminator():
    stream = SSEStream(heartbeat_interval_s=None)

    async def collect(n: int):
        out = []
        async for line in stream.iter_sse():
            out.append(line)
            if len(out) >= n:
                break
        return out

    collector = asyncio.create_task(collect(1))
    await stream.send_raw_sse_line("data: test")
    lines = await collector
    assert lines[0].endswith("\n\n")


class _FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.closed = None

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code=1000, reason=""):
        self.closed = (code, reason)


@pytest.mark.asyncio
async def test_websocket_basic_flow():
    ws = _FakeWebSocket()
    stream = WebSocketStream(ws, heartbeat_interval_s=None, close_on_done=True)

    await stream.send_event("summary", {"a": 1})
    await stream.error("quota_exceeded", "limit", data={"limit": 1})
    await stream.done()

    assert ws.sent[0] == {"type": "event", "event": "summary", "data": {"a": 1}}
    assert ws.sent[1] == {"type": "error", "code": "quota_exceeded", "message": "limit", "data": {"limit": 1}}
    assert ws.sent[2] == {"type": "done"}
    assert ws.closed == (1000, "done")

