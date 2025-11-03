"""
Integration test for character chat streaming using unified SSEStream behind the
STREAMS_UNIFIED flag. This validates that the endpoint emits SSE lines and a
single terminal [DONE] when a (stubbed) provider stream is used.
"""

import os
import shutil
import tempfile
from typing import Any, Iterator

import httpx
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import get_settings


def _fake_provider_stream() -> Iterator[str]:
    # OpenAI-like chunks + [DONE]
    yield "data: {\"choices\":[{\"delta\":{\"role\":\"assistant\"}}]}\n\n"
    yield "data: {\"choices\":[{\"delta\":{\"content\":\"Hello unified SSE\"}}]}\n\n"
    yield "data: [DONE]\n\n"


async def _fake_async_provider_stream_slow() -> Any:
    # Delay long enough to trigger at least one heartbeat
    import asyncio
    await asyncio.sleep(0.06)
    yield "data: {\"choices\":[{\"delta\":{\"role\":\"assistant\"}}]}\n\n"
    await asyncio.sleep(0.02)
    yield "data: {\"choices\":[{\"delta\":\"chunk-a\"}]}\n\n"
    await asyncio.sleep(0.02)
    yield "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_character_chat_streaming_unified_sse(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="unified_sse_char_chat_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    os.environ["STREAMS_UNIFIED"] = "1"
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}

        # Monkeypatch provider call in the endpoint module to return a generator
        import tldw_Server_API.app.api.v1.endpoints.character_chat_sessions as mod

        def _stub_chat_api_call(*args, **kwargs):  # returns a generator (sync iterator)
            return _fake_provider_stream()

        mod.perform_chat_api_call = _stub_chat_api_call

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Bootstrap: get default character + create chat
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            assert r.status_code == 201
            chat_id = r.json()["id"]

            # Request SSE streaming
            payload = {
                "provider": "openai",  # force provider path (not offline-sim)
                "model": "gpt-x",
                "stream": True,
                "save_to_db": False,
            }

            async with client.stream(
                "POST",
                f"/api/v1/chats/{chat_id}/complete-v2",
                headers=headers,
                json=payload,
            ) as resp:
                assert resp.status_code == 200
                # Header assertions
                ct = resp.headers.get("content-type", "")
                assert ct.lower().startswith("text/event-stream")
                assert resp.headers.get("Cache-Control") == "no-cache"
                assert resp.headers.get("X-Accel-Buffering") == "no"

                lines = []
                done_count = 0
                async for ln in resp.aiter_lines():
                    if not ln:
                        continue
                    lines.append(ln)
                    if ln.strip().lower() == "data: [done]":
                        done_count += 1

        # Assertions: at least one data chunk and a single DONE
        assert any(ln.startswith("data: ") and "[DONE]" not in ln for ln in lines)
        assert lines[-1].strip().lower() == "data: [done]"
        assert done_count == 1
    finally:
        os.environ.pop("STREAMS_UNIFIED", None)
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_character_chat_streaming_unified_sse_slow_async_heartbeat(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="unified_sse_char_chat_slow_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    os.environ["STREAMS_UNIFIED"] = "1"
    # Configure short heartbeat to observe it before first chunk
    os.environ["STREAM_HEARTBEAT_INTERVAL_S"] = "0.02"
    os.environ["STREAM_HEARTBEAT_MODE"] = "data"
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}

        import tldw_Server_API.app.api.v1.endpoints.character_chat_sessions as mod

        async def _stub_chat_api_call(*args, **kwargs):
            return _fake_async_provider_stream_slow()

        mod.perform_chat_api_call = _stub_chat_api_call  # type: ignore

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Bootstrap: default character + chat
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            assert r.status_code == 201
            chat_id = r.json()["id"]

            payload = {
                "provider": "openai",
                "model": "gpt-x",
                "stream": True,
                "save_to_db": False,
            }

            async with client.stream(
                "POST",
                f"/api/v1/chats/{chat_id}/complete-v2",
                headers=headers,
                json=payload,
            ) as resp:
                assert resp.status_code == 200
                ct = resp.headers.get("content-type", "").lower()
                assert ct.startswith("text/event-stream")
                assert resp.headers.get("Cache-Control") == "no-cache"
                assert resp.headers.get("X-Accel-Buffering") == "no"

                lines = []
                done_count = 0
                heartbeat_seen = False
                async for ln in resp.aiter_lines():
                    if not ln:
                        continue
                    lines.append(ln)
                    if ln.strip().lower() == "data: [done]":
                        done_count += 1
                    low = ln.lower()
                    if low.startswith("data:") and "heartbeat" in low:
                        heartbeat_seen = True

        assert heartbeat_seen is True
        assert any(ln.startswith("data: ") and "[DONE]" not in ln for ln in lines)
        assert lines[-1].strip().lower() == "data: [done]"
        assert done_count == 1
    finally:
        # Cleanup
        for k in ("STREAM_HEARTBEAT_INTERVAL_S", "STREAM_HEARTBEAT_MODE", "STREAMS_UNIFIED"):
            os.environ.pop(k, None)
        shutil.rmtree(tmpdir, ignore_errors=True)


def _fake_provider_stream_with_duplicate_done_sync() -> Iterator[str]:
    yield "data: {\"choices\":[{\"delta\":{\"content\":\"A\"}}]}\n\n"
    yield "data: [DONE]\n\n"
    yield "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_character_chat_streaming_unified_sse_provider_duplicate_done(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="unified_sse_char_dupdone_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    os.environ["STREAMS_UNIFIED"] = "1"
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}

        import tldw_Server_API.app.api.v1.endpoints.character_chat_sessions as mod

        def _stub_chat_api_call(*args, **kwargs):
            return _fake_provider_stream_with_duplicate_done_sync()

        mod.perform_chat_api_call = _stub_chat_api_call  # type: ignore

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Bootstrap defaults
            r = await client.get("/api/v1/characters/", headers=headers)
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            chat_id = r.json()["id"]

            payload = {"provider": "openai", "model": "gpt-x", "stream": True}

            async with client.stream(
                "POST",
                f"/api/v1/chats/{chat_id}/complete-v2",
                headers=headers,
                json=payload,
            ) as resp:
                assert resp.status_code == 200
                ct = resp.headers.get("content-type", "").lower()
                assert ct.startswith("text/event-stream")
                assert resp.headers.get("Cache-Control") == "no-cache"
                assert resp.headers.get("X-Accel-Buffering") == "no"

                done_count = 0
                lines = []
                async for ln in resp.aiter_lines():
                    if not ln:
                        continue
                    lines.append(ln)
                    if ln.strip().lower() == "data: [done]":
                        done_count += 1

        assert any(ln.startswith("data: ") and "[DONE]" not in ln for ln in lines)
        assert lines[-1].strip().lower() == "data: [done]"
        assert done_count == 1
    finally:
        os.environ.pop("STREAMS_UNIFIED", None)
        shutil.rmtree(tmpdir, ignore_errors=True)
