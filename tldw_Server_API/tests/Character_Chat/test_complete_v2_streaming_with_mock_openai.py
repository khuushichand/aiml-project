"""
Streaming test for complete-v2 using a mock OpenAI-compatible server.
Skips unless MOCK_OPENAI_BASE_URL is set. Requires OPENAI_API_KEY (dummy ok).
"""

import os
import pytest
import httpx

from tldw_Server_API.app.core.AuthNZ.settings import get_settings


pytestmark = pytest.mark.external_api


@pytest.mark.asyncio
async def test_complete_v2_streaming_with_mock_openai():
    base_url = os.getenv("MOCK_OPENAI_BASE_URL")
    if not base_url:
        pytest.skip("MOCK_OPENAI_BASE_URL not set; skipping streaming external test")
    # Ensure env OPENAI_API_BASE_URL is set for the call path
    os.environ["OPENAI_API_BASE_URL"] = base_url
    os.environ.setdefault("OPENAI_API_KEY", "test-mock-key")

    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="chacha_stream_")
    os.environ["USER_DB_BASE_DIR"] = tmpdir
    try:
        from tldw_Server_API.app.main import app
        settings = get_settings()
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Character + chat
            r = await client.get("/api/v1/characters/", headers=headers)
            assert r.status_code == 200
            character_id = r.json()[0]["id"]
            r = await client.post("/api/v1/chats/", headers=headers, json={"character_id": character_id})
            assert r.status_code == 201
            chat_id = r.json()["id"]

            # Streamed completion
            url = f"/api/v1/chats/{chat_id}/complete-v2"
            async with client.stream("POST", url, headers=headers, json={
                "provider": "openai",
                "model": "gpt-4o-mini",
                "append_user_message": "hello mock",
                "save_to_db": False,
                "stream": True
            }) as response:
                assert response.status_code in (200, 502)
                if response.status_code == 200:
                    # Validate SSE-like chunks
                    async for line in response.aiter_lines():
                        if line.strip():
                            assert line.startswith("data: ") or line == "\n"
                            break
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
