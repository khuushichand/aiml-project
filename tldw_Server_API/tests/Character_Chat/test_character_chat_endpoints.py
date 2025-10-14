"""
Integration tests for Character Chat endpoints: sessions, messages, and world books.
"""

import asyncio
import os
import shutil
import tempfile
import pytest
import httpx
import uuid as _uuid

from tldw_Server_API.app.core.AuthNZ.settings import get_settings


@pytest.mark.asyncio
async def test_character_chat_flow_sessions_messages_worldbooks():
    # Use an isolated per-test DB base directory
    tmpdir = tempfile.mkdtemp(prefix="chacha_test_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir

    try:
        from tldw_Server_API.app.main import app

        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1) List characters and pick one
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            chars = r.json()
            assert isinstance(chars, list) and len(chars) >= 1
            character_id = chars[0]["id"]

            # 2) Create chat session
            create_payload = {"character_id": character_id, "title": "Test Chat"}
            r = await client.post("/api/v1/chats/", headers=headers, json=create_payload)
            assert r.status_code == 201
            chat = r.json()
            chat_id = chat["id"]
            chat_version = chat["version"]

            # 3) Update chat session title (optimistic lock)
            r = await client.put(
                f"/api/v1/chats/{chat_id}",
                headers=headers,
                params={"expected_version": chat_version},
                json={"title": "Updated Test Chat"},
            )
            assert r.status_code == 200
            updated_chat = r.json()
            assert updated_chat["title"] == "Updated Test Chat"
            assert updated_chat["version"] == chat_version + 1
            chat_version = updated_chat["version"]

            # 4) Send a user message
            msg_payload = {"role": "user", "content": "Hello there!"}
            r = await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json=msg_payload)
            assert r.status_code == 201
            msg = r.json()
            message_id = msg["id"]
            message_version = msg["version"]

            # 5) Get messages and verify
            r = await client.get(f"/api/v1/chats/{chat_id}/messages", headers=headers)
            assert r.status_code == 200
            msgs = r.json()
            # When not using format_for_completions, response is a dict with messages list
            assert "messages" in msgs
            assert any(m.get("id") == message_id for m in msgs["messages"])  # our message present

            # 6) Delete the message (optimistic lock)
            r = await client.delete(
                f"/api/v1/messages/{message_id}",
                headers=headers,
                params={"expected_version": message_version},
            )
            assert r.status_code == 204

            # 7) Delete the chat session (optimistic lock)
            # Refresh to get current version
            r = await client.get(f"/api/v1/chats/{chat_id}", headers=headers)
            assert r.status_code == 200
            current_chat = r.json()
            r = await client.delete(
                f"/api/v1/chats/{chat_id}",
                headers=headers,
                params={"expected_version": current_chat["version"]},
            )
            assert r.status_code == 204
            # Ensure deleted
            r = await client.get(f"/api/v1/chats/{chat_id}", headers=headers)
            assert r.status_code == 404

            # 8) World book CRUD
            wb_name = f"WB Test {_uuid.uuid4()}"
            wb_create = {
                "name": wb_name,
                "description": "World book for tests",
                "scan_depth": 3,
                "token_budget": 500,
                "recursive_scanning": False,
                "enabled": True,
            }
            r = await client.post("/api/v1/characters/world-books", headers=headers, json=wb_create)
            assert r.status_code == 201
            wb = r.json()
            wb_id = wb["id"]

            r = await client.get("/api/v1/characters/world-books", headers=headers)
            assert r.status_code == 200
            wb_list = r.json()
            assert wb_list.get("total", 0) >= 1

            r = await client.get(f"/api/v1/characters/world-books/{wb_id}", headers=headers)
            assert r.status_code == 200
            wb_get = r.json()
            assert wb_get["id"] == wb_id

            r = await client.put(
                f"/api/v1/characters/world-books/{wb_id}",
                headers=headers,
                json={"name": f"WB Test Updated {_uuid.uuid4()}"},
            )
            assert r.status_code == 200
            wb_upd = r.json()
            assert wb_upd["name"].startswith("WB Test Updated ")

            r = await client.delete(f"/api/v1/characters/world-books/{wb_id}", headers=headers)
            assert r.status_code == 200
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
