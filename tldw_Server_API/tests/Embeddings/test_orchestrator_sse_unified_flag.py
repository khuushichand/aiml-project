"""
Integration test (function-level) for embeddings orchestrator SSE behind STREAMS_UNIFIED, using
direct endpoint invocation to avoid event-loop conflicts with the Redis harness.
"""

import os
import json
import pytest


def test_embeddings_orchestrator_events_unified_sse(redis_client, monkeypatch):
    # Enable unified streams
    os.environ["STREAMS_UNIFIED"] = "1"
    os.environ["STREAM_HEARTBEAT_MODE"] = "data"
    try:
        # Patch Redis factory to use the provided test redis instance
        import redis.asyncio as aioredis  # type: ignore

        async def fake_from_url(url, decode_responses=True):
            return redis_client.client

        monkeypatch.setattr(aioredis, "from_url", fake_from_url)

        # Seed one entry so snapshot has non-empty queues
        redis_client.run(redis_client.client.xadd("embeddings:embedding", {"seq": "0"}))

        # Call endpoint directly and consume one SSE chunk
        from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import orchestrator_events
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User

        admin = User(id=1, username="admin", email="a@x", is_active=True, is_admin=True)

        async def _collect_until_data():
            resp = await orchestrator_events(current_user=admin)
            agen = resp.body_iterator
            acc = []
            saw_event = False
            obj = None
            try:
                for _ in range(10):
                    try:
                        ln = await agen.__anext__()
                    except StopAsyncIteration:
                        break
                    if not ln:
                        continue
                    acc.append(ln)
                    low = ln.lower()
                    if low.startswith("event: ") and "summary" in low:
                        saw_event = True
                    if ln.startswith("data: "):
                        try:
                            obj = json.loads(ln[6:])
                            break
                        except Exception:
                            continue
            finally:
                try:
                    await agen.aclose()
                except Exception:
                    pass
            return saw_event, obj, "".join(acc)

        saw_event, obj, dump = redis_client.run(_collect_until_data())
        assert saw_event is True, f"event line not observed in stream: {dump!r}"
        assert obj is not None, f"data line not observed/parsed in stream: {dump!r}"
        assert isinstance(obj, dict) and "queues" in obj and "stages" in obj
    finally:
        os.environ.pop("STREAMS_UNIFIED", None)
        os.environ.pop("STREAM_HEARTBEAT_MODE", None)
