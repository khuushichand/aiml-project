"""
Integration test for embeddings orchestrator SSE endpoint behind STREAMS_UNIFIED.

Verifies that when the flag is enabled, the endpoint serves SSE via SSEStream
with appropriate headers and emits at least one `event: summary` chunk.
"""

import os
import asyncio
import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_embeddings_orchestrator_events_unified_sse(admin_user, redis_client, monkeypatch):
    # Enable unified streams and prefer data heartbeats
    os.environ["STREAMS_UNIFIED"] = "1"
    os.environ["STREAM_HEARTBEAT_MODE"] = "data"
    try:
        # Patch Redis factory to use the provided test redis instance
        import redis.asyncio as aioredis  # type: ignore

        async def fake_from_url(url, decode_responses=True):
            return redis_client.client

        monkeypatch.setattr(aioredis, "from_url", fake_from_url)

        # Seed one entry so snapshot has non-empty queues
        redis_client.run(redis_client.xadd("embeddings:embedding", {"seq": "0"}))

        from tldw_Server_API.app.main import app

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream("GET", "/api/v1/embeddings/orchestrator/events") as resp:
                assert resp.status_code == 200
                # Header assertions
                ct = resp.headers.get("content-type", "").lower()
                assert ct.startswith("text/event-stream")
                assert resp.headers.get("Cache-Control") == "no-cache"
                assert resp.headers.get("X-Accel-Buffering") == "no"

                saw_event = False
                payload_valid = False
                # Consume a few lines and then stop
                async for ln in resp.aiter_lines():
                    if not ln:
                        continue
                    low = ln.lower()
                    if low.startswith("event: ") and "summary" in low:
                        saw_event = True
                    if ln.startswith("data: "):
                        try:
                            obj = json.loads(ln[6:])
                            # Expect orchestrator-style keys
                            if isinstance(obj, dict) and "queues" in obj and "stages" in obj:
                                payload_valid = True
                                break
                        except Exception:
                            pass

                assert saw_event is True
                assert payload_valid is True
    finally:
        os.environ.pop("STREAMS_UNIFIED", None)
        os.environ.pop("STREAM_HEARTBEAT_MODE", None)

