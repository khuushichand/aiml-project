"""
Negative tests for world book CRUD and character associations.
"""

import os
import shutil
import tempfile
import uuid as _uuid
import httpx
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import get_settings


@pytest.mark.asyncio
async def test_world_book_duplicate_and_missing_paths():
    tmpdir = tempfile.mkdtemp(prefix="chacha_wb_neg_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Create world book
            name = f"WB {_uuid.uuid4()}"
            body = {"name": name, "description": "d", "scan_depth": 2, "token_budget": 100, "recursive_scanning": False, "enabled": True}
            r = await client.post("/api/v1/characters/world-books", headers=headers, json=body)
            assert r.status_code == 201
            wb_id = r.json()["id"]

            # Duplicate name should 409
            r = await client.post("/api/v1/characters/world-books", headers=headers, json=body)
            assert r.status_code == 409

            # Non-existent get -> 404
            r = await client.get("/api/v1/characters/world-books/999999", headers=headers)
            assert r.status_code == 404

            # Non-existent update -> 404
            r = await client.put("/api/v1/characters/world-books/999999", headers=headers, json={"name": f"WB {_uuid.uuid4()}"})
            assert r.status_code == 404

            # Non-existent delete -> 404
            r = await client.delete("/api/v1/characters/world-books/999999", headers=headers)
            assert r.status_code == 404

            # Entry-level negatives
            # Non-existent entry update -> 404
            r = await client.put("/api/v1/characters/world-books/entries/999999", headers=headers, json={"content": "x"})
            assert r.status_code == 404
            # Non-existent entry delete -> 404
            r = await client.delete("/api/v1/characters/world-books/entries/999999", headers=headers)
            assert r.status_code == 404

            # Choose a character
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]

            # Attach non-existent world book -> 404
            r = await client.post(f"/api/v1/characters/{character_id}/world-books", headers=headers, json={"world_book_id": 999999})
            assert r.status_code == 404

            # Detach non-existent or non-attached -> 404
            r = await client.delete(f"/api/v1/characters/{character_id}/world-books/999999", headers=headers)
            assert r.status_code == 404

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
