import os
import io
import pytest
from fastapi.testclient import TestClient


def test_http_file_size_limit_exceeded(monkeypatch):
    """Uploads an oversized file to trigger 413 without invoking ffmpeg."""
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    settings = get_settings()

    # Create a dummy oversized payload (26 MB) to exceed free-tier 25 MB
    big_bytes = b"0" * (26 * 1024 * 1024)

    with TestClient(app) as client:
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        files = {"file": ("big.wav", io.BytesIO(big_bytes), "audio/wav")}
        data = {"model": "whisper-1", "response_format": "json"}
        resp = client.post("/api/v1/audio/transcriptions", headers=headers, files=files, data=data)
        if resp.status_code == 404:
            pytest.skip("audio/transcriptions endpoint not mounted in this build")
        assert resp.status_code == 413
        assert "exceeds maximum" in resp.json().get("detail", "")


def test_http_concurrent_jobs_cap(monkeypatch):
    """Forces can_start_job to reject to exercise 429 response path."""
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    import tldw_Server_API.app.api.v1.endpoints.audio as audio_ep

    async def _reject(user_id: int):
        return False, "Concurrent job limit reached (1)"

    monkeypatch.setattr(audio_ep, "can_start_job", _reject)

    # Small valid content under size limit
    content = b"0" * (64 * 1024)
    settings = get_settings()
    with TestClient(app) as client:
        headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
        files = {"file": ("ok.wav", io.BytesIO(content), "audio/wav")}
        data = {"model": "whisper-1", "response_format": "json"}
        resp = client.post("/api/v1/audio/transcriptions", headers=headers, files=files, data=data)
        if resp.status_code == 404:
            pytest.skip("audio/transcriptions endpoint not mounted in this build")
        assert resp.status_code == 429
        assert "Concurrent job limit" in resp.json().get("detail", "")
