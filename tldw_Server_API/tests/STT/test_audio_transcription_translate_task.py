"""
Additional tests for OpenAI-compatible audio transcription/translation API
endpoints focusing on the Whisper task parameter and model mapping behaviour.
"""

import tempfile
import os

import numpy as np
import pytest
import soundfile as sf
import httpx

from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.api.v1.endpoints import audio as audio_endpoints
from tldw_Server_API.tests.test_utils import (
    skip_if_whisper_model_not_cached_locally,
)


def _create_test_tone(duration: float = 0.25, sample_rate: int = 16000) -> str:
    """Create a very small test WAV file on disk and return its path."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    data = (0.25 * np.sin(440 * 2 * np.pi * t)).astype(np.float32)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        sf.write(tmp.name, data, sample_rate)
    finally:
        tmp.close()
    return tmp.name


@pytest.mark.asyncio
async def test_transcription_verbose_json_includes_task_and_duration(bypass_api_limits):
    """Ensure verbose_json responses include task and duration metadata."""
    from tldw_Server_API.app.main import app

    skip_if_whisper_model_not_cached_locally("whisper-1")

    path = _create_test_tone()
    try:
        ctx = bypass_api_limits(app)
        transport = httpx.ASGITransport(app=app)
        with ctx:
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                with open(path, "rb") as f:
                    files = {"file": ("test.wav", f, "audio/wav")}
                    data = {
                        "model": "whisper-1",
                        "response_format": "verbose_json",
                    }
                    settings = get_settings()
                    headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
                    resp = await client.post(
                        "/api/v1/audio/transcriptions",
                        headers=headers,
                        files=files,
                        data=data,
                    )

        # In some minimal test builds the endpoint may not be mounted; skip in that case.
        if resp.status_code == 404:
            pytest.skip("audio/transcriptions endpoint not mounted in this build")
        assert resp.status_code == 200
        body = resp.json()
        assert "text" in body
        # Task should be normalized to either "transcribe" or "translate"
        assert body.get("task") in ("transcribe", "translate")
        assert isinstance(body.get("duration"), (int, float))
    finally:
        if os.path.exists(path):
            os.remove(path)


@pytest.mark.asyncio
async def test_translation_endpoint_uses_translate_task_and_allows_auto_language(bypass_api_limits):
    """Verify /audio/translations calls the transcription path with task='translate'."""
    from tldw_Server_API.app.main import app

    skip_if_whisper_model_not_cached_locally("whisper-1")

    path = _create_test_tone()
    try:
        ctx = bypass_api_limits(app)
        transport = httpx.ASGITransport(app=app)
        with ctx:
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                with open(path, "rb") as f:
                    files = {"file": ("test.wav", f, "audio/wav")}
                    data = {
                        "model": "whisper-1",
                        "response_format": "verbose_json",
                    }
                    settings = get_settings()
                    headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}
                    resp = await client.post(
                        "/api/v1/audio/translations",
                        headers=headers,
                        files=files,
                        data=data,
                    )

        if resp.status_code == 404:
            pytest.skip("audio/translations endpoint not mounted in this build")
        assert resp.status_code == 200
        body = resp.json()
        assert "text" in body
        # Translation endpoint should surface task='translate' when verbose_json is requested
        assert body.get("task") == "translate"
    finally:
        if os.path.exists(path):
            os.remove(path)
