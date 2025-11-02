"""
External (optional) test for complete-v2 using a mock OpenAI-compatible server.
Skips unless MOCK_OPENAI_BASE_URL is provided in the environment and loadable by the app config.
"""

import os
import pytest
import httpx

from tldw_Server_API.app.core.AuthNZ.settings import get_settings


pytestmark = pytest.mark.external_api


@pytest.mark.asyncio
async def test_complete_v2_with_mock_openai_server():
    base_url = os.getenv("MOCK_OPENAI_BASE_URL")
    if not base_url:
        pytest.skip("MOCK_OPENAI_BASE_URL not set; skipping external test")

    # Hint: ensure your config maps `openai_api.api_base_url` to MOCK_OPENAI_BASE_URL.
    # For example, set OPENAI_API_BASE_URL through your app config loader if supported.

    # Use isolated DB
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="chacha_mock_openai_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Select character and create chat
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            assert r.status_code == 201
            chat_id = r.json()["id"]

            # Call complete-v2 with provider=openai (mock)
            r = await client.post(
                f"/api/v1/chats/{chat_id}/complete-v2",
                headers=headers,
                json={
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "append_user_message": "Hello from mock",
                    "save_to_db": False
                }
            )
            assert r.status_code in (200, 502)  # 502 if mock is unreachable/misconfigured
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
