"""
Integration tests for role normalization and message search placeholder handling.
"""

import os
import shutil
import tempfile

import httpx
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import get_settings


@pytest.mark.asyncio
async def test_get_chat_context_and_prepare_roles_normalized():
    tmpdir = tempfile.mkdtemp(prefix="chacha_roles_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Use default character
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]

            # Create chat
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            assert r.status_code == 201
            chat_id = r.json()["id"]

            # Send user + assistant + system messages
            assert (await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "user", "content": "hello"})).status_code == 201
            assert (await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "assistant", "content": "hi there"})).status_code == 201
            assert (await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "system", "content": "note"})).status_code == 201

            # get_chat_context
            r = await client.get(f"/api/v1/chats/{chat_id}/context", headers=headers)
            assert r.status_code == 200
            msgs = r.json()["messages"]
            roles = {m["role"] for m in msgs}
            assert roles.issubset({"user", "assistant", "system"})

            # prepare_chat_completion (should include system preface + normalized roles)
            r = await client.post(
                f"/api/v1/chats/{chat_id}/completions",
                headers=headers,
                json={"include_character_context": True, "limit": 10, "offset": 0}
            )
            assert r.status_code == 200
            data = r.json()
            roles2 = [m["role"] for m in data["messages"]]
            assert roles2[0] == "system"
            assert set(roles2[1:]).issubset({"user", "assistant", "system"})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_complete_v2_uses_normalized_roles_via_stubbed_provider():
    tmpdir = tempfile.mkdtemp(prefix="chacha_complete_v2_roles_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        captured = {}

        # Monkeypatch provider call to capture messages
        import tldw_Server_API.app.api.v1.endpoints.character_chat_sessions as mod

        def _stub_chat_api_call(api_endpoint, messages_payload, **kwargs):
            captured["messages"] = messages_payload
            return {"choices": [{"message": {"content": "ok"}}]}

        mod.perform_chat_api_call = _stub_chat_api_call

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Setup character + chat + a couple of messages
            r = await client.get("/api/v1/characters/", headers=headers)
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            chat_id = r.json()["id"]
            await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "user", "content": "hello"})
            await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "assistant", "content": "hi"})

            # Use a non-local provider to trigger provider call path
            r = await client.post(
                f"/api/v1/chats/{chat_id}/complete-v2",
                headers=headers,
                json={"provider": "openai", "model": "gpt-x", "append_user_message": "test", "save_to_db": False}
            )
            assert r.status_code == 200
            assert "messages" in captured
            roles = {m.get("role") for m in captured["messages"]}
            assert roles.issubset({"system", "user", "assistant", "tool"})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_get_messages_format_for_completions_roles_and_search_placeholders():
    tmpdir = tempfile.mkdtemp(prefix="chacha_msgs_roles_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Setup
            r = await client.get("/api/v1/characters/", headers=headers)
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            chat_id = r.json()["id"]

            # Add messages including a placeholder in assistant content
            await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "user", "content": "Hi"})
            await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "assistant", "content": "Hello {{user}}"})
            await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "system", "content": "sys note"})

            # GET messages with format_for_completions=true and context
            r = await client.get(
                f"/api/v1/chats/{chat_id}/messages",
                headers=headers,
                params={"format_for_completions": True, "include_character_context": True}
            )
            assert r.status_code == 200
            data = r.json()
            roles = [m["role"] for m in data["messages"]]
            assert roles[0] == "system"  # character context
            assert set(roles[1:]).issubset({"user", "assistant", "system", "tool"})

            # Search messages: verify placeholder replacement in response content
            r = await client.get(
                f"/api/v1/chats/{chat_id}/messages/search",
                headers=headers,
                params={"query": "Hello", "limit": 10}
            )
            assert r.status_code == 200
            res = r.json()
            assert any(m.get("content") == "Hello User" for m in res.get("messages", []))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
