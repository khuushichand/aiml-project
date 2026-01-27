from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from tldw_Server_API.app.api.v1.endpoints.media.transcription_models import (
    router as transcription_models_router,
)


@pytest.mark.unit
def test_transcription_models_includes_vibevoice_asr():
    app = FastAPI()
    app.include_router(transcription_models_router, prefix="/api/v1/media")

    with TestClient(app) as client:
        resp = client.get("/api/v1/media/transcription-models")
        assert resp.status_code == 200, resp.text
        body = resp.json()

    all_models = set(body.get("all_models") or [])
    assert "vibevoice-asr" in all_models
    assert "microsoft/VibeVoice-ASR" in all_models

    categories = body.get("categories") or {}
    vibe_models = categories.get("VibeVoice-ASR") or []
    vibe_values = {m.get("value") for m in vibe_models if isinstance(m, dict)}
    assert "vibevoice-asr" in vibe_values
