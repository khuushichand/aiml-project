import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sample_audio_path() -> Path:
    return _repo_root() / "tldw_Server_API/tests/Media_Ingestion_Modification/test_media/sample.wav"


@pytest.mark.e2e
def test_audio_transcription_local_workflow(page, server_url):
    if os.getenv("RUN_AUDIO_E2E", "").lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Audio E2E disabled; set RUN_AUDIO_E2E=1 to enable.")
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available; skipping audio transcription workflow.")

    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    audio_path = _sample_audio_path()
    model_name = os.getenv("TLDW_E2E_AUDIO_MODEL", "whisper-1")

    transcribe_resp = page.request.post(
        "/api/v1/audio/transcriptions",
        headers=headers,
        multipart={
            "file": {
                "name": audio_path.name,
                "mimeType": "audio/wav",
                "buffer": audio_path.read_bytes(),
            },
            "model": model_name,
            "language": "en",
            "response_format": "json",
        },
    )
    _require_ok(transcribe_resp, "transcribe audio")
    transcribe_payload = transcribe_resp.json()
    transcript_text = transcribe_payload.get("text")
    assert transcript_text

    note_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={
            "title": f"Audio transcript {suffix}",
            "content": transcript_text,
            "keywords": ["audio", suffix],
        },
    )
    _require_ok(note_resp, "store transcription note")
    note_payload = note_resp.json()
    note_id = note_payload["id"]
    version = note_payload["version"]

    fetch_resp = page.request.get(f"/api/v1/notes/{note_id}", headers=headers)
    _require_ok(fetch_resp, "fetch transcription note")
    fetched_payload = fetch_resp.json()
    assert fetched_payload["id"] == note_id

    delete_resp = page.request.delete(
        f"/api/v1/notes/{note_id}",
        headers={**headers, "expected-version": str(version)},
    )
    assert delete_resp.status == 204


@pytest.mark.e2e
def test_audio_transcription_external_workflow(page, server_url):
    if os.getenv("TLDW_E2E_EXTERNAL_AUDIO", "").lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("External audio E2E disabled; set TLDW_E2E_EXTERNAL_AUDIO=1 to enable.")

    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    audio_path = _sample_audio_path()
    model_name = os.getenv("TLDW_E2E_AUDIO_EXTERNAL_MODEL", "external:default")

    transcribe_resp = page.request.post(
        "/api/v1/audio/transcriptions",
        headers=headers,
        multipart={
            "file": {
                "name": audio_path.name,
                "mimeType": "audio/wav",
                "buffer": audio_path.read_bytes(),
            },
            "model": model_name,
            "language": "en",
            "response_format": "json",
        },
    )
    _require_ok(transcribe_resp, "transcribe audio (external)")
    transcribe_payload = transcribe_resp.json()
    transcript_text = transcribe_payload.get("text")
    assert transcript_text

    note_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={
            "title": f"Audio transcript external {suffix}",
            "content": transcript_text,
            "keywords": ["audio", "external", suffix],
        },
    )
    _require_ok(note_resp, "store transcription note (external)")
    note_payload = note_resp.json()
    note_id = note_payload["id"]
    version = note_payload["version"]

    fetch_resp = page.request.get(f"/api/v1/notes/{note_id}", headers=headers)
    _require_ok(fetch_resp, "fetch transcription note (external)")

    delete_resp = page.request.delete(
        f"/api/v1/notes/{note_id}",
        headers={**headers, "expected-version": str(version)},
    )
    assert delete_resp.status == 204
