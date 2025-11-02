"""
Verify GET messages endpoints expose tool_calls when requested.
"""

import os
import shutil
import tempfile

import httpx
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import get_settings


@pytest.mark.asyncio
async def test_get_chat_messages_includes_tool_calls_field_when_requested():
    tmpdir = tempfile.mkdtemp(prefix="chacha_tools_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Setup character and chat
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            assert r.status_code == 201
            chat_id = r.json()["id"]

            # Send a message
            r = await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "user", "content": "hi"})
            assert r.status_code == 201

            # Fetch messages with include_tool_calls=true
            r = await client.get(
                f"/api/v1/chats/{chat_id}/messages",
                headers=headers,
                params={"include_tool_calls": True}
            )
            assert r.status_code == 200
            data = r.json()
            assert "messages" in data
            assert any("tool_calls" in m for m in data["messages"])  # field exposed (may be null)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_get_single_message_includes_tool_calls_field_when_requested():
    tmpdir = tempfile.mkdtemp(prefix="chacha_tools_msg_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v1/characters/", headers=headers)
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            chat_id = r.json()["id"]
            r = await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "user", "content": "hi"})
            msg_id = r.json()["id"]

            r = await client.get(f"/api/v1/messages/{msg_id}", headers=headers, params={"include_tool_calls": True})
            assert r.status_code == 200
            msg = r.json()
            assert "tool_calls" in msg
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
