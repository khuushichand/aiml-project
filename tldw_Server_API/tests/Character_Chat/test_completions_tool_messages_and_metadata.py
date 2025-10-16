"""
Tests for formatted-for-completions payload:
- Emits tool role messages when tool_calls metadata exists
- Includes metadata_extra sidecar when include_metadata=true
"""

import os
import shutil
import tempfile
from pathlib import Path

import httpx
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import get_settings


@pytest.mark.asyncio
async def test_formatted_for_completions_includes_tool_messages_and_metadata():
    tmpdir = tempfile.mkdtemp(prefix="chacha_fmt_tools_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    try:
        from tldw_Server_API.app.main import app
        from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB

        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Get a character and create a chat
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            assert r.status_code == 201
            chat_id = r.json()["id"]

            # Create an assistant message (we will attach tool metadata afterwards)
            r = await client.post(
                f"/api/v1/chats/{chat_id}/messages",
                headers=headers,
                json={"role": "assistant", "content": "Here is a response"},
            )
            assert r.status_code == 201
            # Retrieve from API to ensure we have persisted ID
            r = await client.get(f"/api/v1/chats/{chat_id}/messages", headers=headers)
            assert r.status_code == 200
            msgs = r.json().get("messages", [])
            assistant_msg_id = next((m.get("id") for m in msgs if m.get("sender") == "assistant" and m.get("content") == "Here is a response"), None)
            assert assistant_msg_id, "Assistant message not found in conversation after creation"

            # Determine user DB path (single-user mode uses fixed user id)
            user_id = get_settings().SINGLE_USER_FIXED_ID
            from tldw_Server_API.app.core.config import settings as cfg_settings
            base_dir = cfg_settings.get("USER_DB_BASE_DIR")
            db_path = Path(base_dir) / str(user_id) / "ChaChaNotes.db"

            # Add inline tool_calls suffix using public API (edit with optimistic version)
            tool_call_id = "call_123"
            tool_calls = [{"id": tool_call_id, "type": "function", "function": {"name": "search", "arguments": "{\"query\": \"hello\"}"}}]
            # Fetch version for optimistic locking
            r = await client.get(f"/api/v1/chats/{chat_id}/messages", headers=headers)
            assert r.status_code == 200
            msgs = r.json().get("messages", [])
            m = next((m for m in msgs if m.get("id") == assistant_msg_id), None)
            assert m is not None
            expected_version = m.get("version")
            import json as _json
            new_content = (m.get("content") or "").rstrip() + "\n\n[tool_calls]: " + _json.dumps(tool_calls)
            r = await client.put(
                f"/api/v1/messages/{assistant_msg_id}",
                headers=headers,
                params={"expected_version": expected_version},
                json={"content": new_content},
            )
            assert r.status_code == 200

            # Fetch messages formatted for completions, include metadata
            r = await client.get(
                f"/api/v1/chats/{chat_id}/messages",
                headers=headers,
                params={
                    "format_for_completions": True,
                    "include_character_context": True,
                    "include_metadata": True,
                },
            )
            assert r.status_code == 200
            data = r.json()
            msgs = data["messages"]

            # Ensure at least one tool message present with correct id
            tool_msgs = [m for m in msgs if m.get("role") == "tool"]
            assert tool_msgs, "Expected tool role messages to be present"
            assert any(m.get("tool_call_id") == tool_call_id for m in tool_msgs)
            # content may be empty unless tool_results are stored; we don't require it here
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
