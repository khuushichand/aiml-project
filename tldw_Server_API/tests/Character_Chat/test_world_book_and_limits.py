"""
Additional tests for world book entries/associations and basic rate-limiting.
"""

import asyncio
import os
import shutil
import tempfile
import uuid as _uuid

import httpx
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import get_settings


@pytest.mark.asyncio
async def test_world_book_entries_and_attach_flow():
    tmpdir = tempfile.mkdtemp(prefix="chacha_wb_")
    original_user_db = os.environ.get("USER_DB_BASE_DIR")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    from tldw_Server_API.app.core.config import clear_config_cache
    clear_config_cache()
    import tldw_Server_API.app.core.Character_Chat.character_rate_limiter as crl  # noqa: WPS433
    crl._rate_limiter = None
    try:
        from tldw_Server_API.app.main import app

        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Pick default character
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            chars = r.json(); assert isinstance(chars, list) and len(chars) >= 1
            character_id = chars[0]["id"]

            # Create world book
            wb_name = f"WB {_uuid.uuid4()}"
            wb_create = {"name": wb_name, "description": "desc", "scan_depth": 3, "token_budget": 500, "recursive_scanning": False, "enabled": True}
            r = await client.post("/api/v1/characters/world-books", headers=headers, json=wb_create)
            assert r.status_code == 201
            wb_id = r.json()["id"]

            # Add an entry
            entry_payload = {"keywords": ["alpha"], "content": "Alpha content", "priority": 1, "enabled": True}
            r = await client.post(f"/api/v1/characters/world-books/{wb_id}/entries", headers=headers, json=entry_payload)
            assert r.status_code == 201
            entry_id = r.json()["id"]

            # List entries
            r = await client.get(f"/api/v1/characters/world-books/{wb_id}/entries", headers=headers)
            assert r.status_code == 200
            entries = r.json().get("entries", [])
            assert any(e.get("id") == entry_id for e in entries)

            # Attach to character
            r = await client.post(f"/api/v1/characters/{character_id}/world-books", headers=headers, json={"world_book_id": wb_id})
            assert r.status_code == 200

            # Verify attached list
            r = await client.get(f"/api/v1/characters/{character_id}/world-books", headers=headers)
            assert r.status_code == 200
            attached = r.json()
            assert any(wb.get("world_book_id") == wb_id or wb.get("id") == wb_id for wb in attached)

            # Detach
            r = await client.delete(f"/api/v1/characters/{character_id}/world-books/{wb_id}", headers=headers)
            assert r.status_code == 200

            # Verify detached
            r = await client.get(f"/api/v1/characters/{character_id}/world-books", headers=headers)
            assert r.status_code == 200
            attached = r.json()
            assert not any(wb.get("world_book_id") == wb_id or wb.get("id") == wb_id for wb in attached)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if original_user_db is None:
            os.environ.pop("USER_DB_BASE_DIR", None)
        else:
            os.environ["USER_DB_BASE_DIR"] = original_user_db
        clear_config_cache()
        try:
            crl._rate_limiter = None
        except Exception:
            pass


@pytest.mark.asyncio
async def test_legacy_complete_endpoint_rate_limit():
    tmpdir = tempfile.mkdtemp(prefix="chacha_rate_")
    env_overrides = {
        "USER_DB_BASE_DIR": tmpdir,
        "MAX_MESSAGE_SENDS_PER_MINUTE": "5",  # lower per-minute message send limit
    }
    original_env = {key: os.environ.get(key) for key in env_overrides}
    os.environ.update(env_overrides)
    from tldw_Server_API.app.core.config import clear_config_cache
    clear_config_cache()
    import tldw_Server_API.app.core.Character_Chat.character_rate_limiter as crl  # noqa: WPS433
    crl._rate_limiter = None
    original_max_chats = os.environ.get("MAX_CHATS_PER_USER")
    try:
        from tldw_Server_API.app.main import app

        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Ensure chat cap allows at least one new chat in this fresh DB
            r = await client.get("/api/v1/chats/", headers=headers)
            assert r.status_code == 200
            baseline = r.json().get("total", 0)
            os.environ["MAX_CHATS_PER_USER"] = str(baseline + 1)
            clear_config_cache()
            crl._rate_limiter = None

            # Pick default character and create chat
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            assert r.status_code == 201
            chat_id = r.json()["id"]

            # Burst calls to legacy endpoint; expect 429 when >5 within ~1s
            statuses = []
            for _ in range(7):
                resp = await client.post(f"/api/v1/chats/{chat_id}/complete", headers=headers, json={})
                statuses.append(resp.status_code)
            assert any(s == 429 for s in statuses)

            # Verify message send rate limiting (per-minute)
            # We simulate multiple messages quickly; depending on limiter config, we may or may not hit 429 here in tests.
            # In test mode, global limiter is skipped, but CharacterRateLimiter is active; send > max_message_sends_per_minute should 429.
            hits = []
            for i in range(0, 15):
                resp = await client.post(f"/api/v1/chats/{chat_id}/messages", headers=headers, json={"role": "user", "content": f"msg {i}"})
                hits.append(resp.status_code)
                if resp.status_code == 429:
                    break
            assert any(s == 429 for s in hits), "Expected 429 for message send rate limit"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if original_max_chats is None:
            os.environ.pop("MAX_CHATS_PER_USER", None)
        else:
            os.environ["MAX_CHATS_PER_USER"] = original_max_chats
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        clear_config_cache()
        try:
            crl._rate_limiter = None
        except Exception:
            pass
