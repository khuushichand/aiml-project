import asyncio
import json

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.stream_client import ACPStreamClient
from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage


@pytest.mark.asyncio
async def test_stream_client_call_roundtrip():
    sent = []

    async def send_bytes(data: bytes):
        sent.append(data)

    client = ACPStreamClient(send_bytes=send_bytes)
    await client.start()

    task = asyncio.create_task(client.call("ping", {"a": 1}))
    await asyncio.sleep(0)

    assert sent, "client did not send request"
    payload = json.loads(sent[0].decode("utf-8").strip())
    assert payload["method"] == "ping"
    req_id = payload["id"]

    await client.feed_bytes(
        json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {"ok": True}}).encode("utf-8")
        + b"\n"
    )
    resp = await task
    assert resp.result == {"ok": True}


@pytest.mark.asyncio
async def test_stream_client_notification_handler():
    seen = []

    async def send_bytes(_: bytes):
        return

    async def on_note(msg: ACPMessage):
        seen.append(msg)

    client = ACPStreamClient(send_bytes=send_bytes)
    client.set_notification_handler(on_note)
    await client.start()

    await client.feed_bytes(
        json.dumps({"jsonrpc": "2.0", "method": "session/update", "params": {"x": 1}}).encode("utf-8")
        + b"\n"
    )

    assert len(seen) == 1
    assert seen[0].method == "session/update"


@pytest.mark.asyncio
async def test_stream_client_request_handler():
    sent = []

    async def send_bytes(data: bytes):
        sent.append(data)

    async def on_request(msg: ACPMessage):
        return ACPMessage(jsonrpc="2.0", id=msg.id, result={"outcome": {"outcome": "approved"}})

    client = ACPStreamClient(send_bytes=send_bytes)
    client.set_request_handler(on_request)
    await client.start()

    await client.feed_bytes(
        json.dumps({"jsonrpc": "2.0", "id": 7, "method": "session/request_permission", "params": {}}).encode("utf-8")
        + b"\n"
    )

    assert sent, "client did not send response"
    payload = json.loads(sent[0].decode("utf-8").strip())
    assert payload["id"] == 7
    assert payload["result"]["outcome"]["outcome"] == "approved"
