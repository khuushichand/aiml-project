"""
Integration test for chat document-generation streaming using unified SSEStream
behind STREAMS_UNIFIED. We stub the LLM call to return a simple async generator
of text chunks and assert SSE emission with a terminal [DONE].
"""

import asyncio
import os
import shutil
import tempfile
from typing import Any, AsyncIterator

import httpx
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import get_settings


async def _async_text_stream() -> AsyncIterator[str]:
    yield "First line from doc-gen"
    # Simulate a slower producer emitting a later chunk
    await asyncio.sleep(0.02)
    yield "Second line from doc-gen"


def _dup_done_stream() -> AsyncIterator[str]:
    async def _gen():
        yield "Line before done"
        yield "[DONE]"
        yield "[DONE]"
    return _gen()


async def _async_text_stream_slow() -> AsyncIterator[str]:
    # Delay long enough to trigger at least one heartbeat from SSEStream
    await asyncio.sleep(0.06)
    yield "Delayed line 1"
    await asyncio.sleep(0.02)
    yield "Delayed line 2"


@pytest.mark.asyncio
async def test_chat_document_generation_streaming_unified_sse(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="unified_sse_doc_stream_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    os.environ["STREAMS_UNIFIED"] = "1"
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}

        # Monkeypatch DocumentGeneratorService._call_llm to return async generator
        import tldw_Server_API.app.core.Chat.document_generator as gen_mod

        def _stub_call_llm(*args, **kwargs):
            return _async_text_stream()

        gen_mod.DocumentGeneratorService._call_llm = _stub_call_llm  # type: ignore

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Bootstrap: get default character + create chat to have a conversation id
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            assert r.status_code == 201
            conversation_id = r.json()["id"]
            # Ensure at least one message exists to satisfy doc generator
            msg_resp = await client.post(
                f"/api/v1/chats/{conversation_id}/messages",
                headers=headers,
                json={"role": "user", "content": "Hello for doc-gen"},
            )
            assert msg_resp.status_code == 201

            payload = {
                "conversation_id": conversation_id,
                "document_type": "summary",
                "provider": "openai",
                "model": "gpt-x",
                "stream": True,
            }

            async with client.stream(
                "POST",
                "/api/v1/chat/documents/generate",
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

        # Should include our payload lines and finish with DONE
        assert any(ln.startswith("data: ") and "[DONE]" not in ln for ln in lines)
        assert lines[-1].strip().lower() == "data: [done]"
        assert done_count == 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_chat_document_generation_streaming_unified_sse_provider_duplicate_done(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="unified_sse_doc_dupdone_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    os.environ["STREAMS_UNIFIED"] = "1"
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}

        import tldw_Server_API.app.core.Chat.document_generator as gen_mod

        def _stub_call_llm(*args, **kwargs):
            return _dup_done_stream()

        gen_mod.DocumentGeneratorService._call_llm = _stub_call_llm  # type: ignore

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            assert r.status_code == 201
            conversation_id = r.json()["id"]
            msg_resp = await client.post(
                f"/api/v1/chats/{conversation_id}/messages",
                headers=headers,
                json={"role": "user", "content": "Seed message"},
            )
            assert msg_resp.status_code == 201

            payload = {
                "conversation_id": conversation_id,
                "document_type": "summary",
                "provider": "openai",
                "model": "gpt-x",
                "stream": True,
            }

            async with client.stream(
                "POST",
                "/api/v1/chat/documents/generate",
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
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_chat_document_generation_streaming_unified_sse_slow_async_heartbeat(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="unified_sse_doc_heartbeat_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    os.environ["STREAMS_UNIFIED"] = "1"
    # Short heartbeat so it appears before first chunk
    os.environ["STREAM_HEARTBEAT_INTERVAL_S"] = "0.02"
    os.environ["STREAM_HEARTBEAT_MODE"] = "data"
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}

        import tldw_Server_API.app.core.Chat.document_generator as gen_mod

        def _stub_call_llm(*args, **kwargs):
            return _async_text_stream_slow()

        gen_mod.DocumentGeneratorService._call_llm = _stub_call_llm  # type: ignore

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Bootstrap defaults
            r = await client.get("/api/v1/characters/", headers=headers)
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            conversation_id = r.json()["id"]
            msg_resp = await client.post(
                f"/api/v1/chats/{conversation_id}/messages",
                headers=headers,
                json={"role": "user", "content": "Slow seed"},
            )
            assert msg_resp.status_code == 201

            payload = {
                "conversation_id": conversation_id,
                "document_type": "summary",
                "provider": "openai",
                "model": "gpt-x",
                "stream": True,
            }

            async with client.stream(
                "POST",
                "/api/v1/chat/documents/generate",
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
                    if ln.lower().startswith("data:") and "heartbeat" in ln.lower():
                        heartbeat_seen = True

        assert heartbeat_seen is True
        assert any(ln.startswith("data: ") and "[DONE]" not in ln for ln in lines)
        assert lines[-1].strip().lower() == "data: [done]"
        assert done_count == 1
    finally:
        for k in ("STREAM_HEARTBEAT_INTERVAL_S", "STREAM_HEARTBEAT_MODE", "STREAMS_UNIFIED"):
            os.environ.pop(k, None)
        shutil.rmtree(tmpdir, ignore_errors=True)
