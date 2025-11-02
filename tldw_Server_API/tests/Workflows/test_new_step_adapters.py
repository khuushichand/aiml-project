import os
import time
import types
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_wf(tmp_path, monkeypatch):
    # Force test mode for adapters that check it
    monkeypatch.setenv("TEST_MODE", "1")
    # Provide a temporary USER_DB_BASE_DIR for embedding/chroma
    base = tmp_path / "user_databases"
    base.mkdir(parents=True, exist_ok=True)
    from tldw_Server_API.app.core import config as _cfg
    _cfg.settings["USER_DB_BASE_DIR"] = str(base)
    # Chroma stub client
    monkeypatch.setenv("CHROMADB_FORCE_STUB", "1")

    db = WorkflowsDatabase(str(tmp_path / "wf.db"))

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    def override_db():
        return db

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[wf_mod._get_db] = override_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def _wait_terminal(client: TestClient, run_id: str, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/v1/workflows/runs/{run_id}")
        r.raise_for_status()
        data = r.json()
        if data["status"] in ("succeeded", "failed", "cancelled"):
            return data
        time.sleep(0.05)
    raise AssertionError("run did not complete")


def test_rss_fetch_step_test_mode(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "rss",
        "version": 1,
        "steps": [
            {"id": "a", "type": "rss_fetch", "config": {"urls": ["https://example.com/feed.xml"], "limit": 3}}
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    data = _wait_terminal(client, run_id)
    assert data["status"] == "succeeded"
    out = data.get("outputs") or {}
    assert isinstance(out.get("results"), list)
    assert out.get("count") == 1


def test_embed_step_with_stub(monkeypatch, client_with_wf: TestClient):
    client = client_with_wf
    # Monkeypatch embeddings to avoid heavy deps
    import tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create as EC
    async def _fake_batch(texts, user_app_config, model_id_override=None):
        return [[0.1, 0.2, 0.3] for _ in texts]
    monkeypatch.setattr(EC, "create_embeddings_batch_async", _fake_batch)

    definition = {
        "name": "embedder",
        "version": 1,
        "steps": [
            {"id": "p", "type": "prompt", "config": {"template": "hello world"}},
            {"id": "e", "type": "embed", "config": {"texts": "{{ last.text }}", "collection": "user_1_workflows"}}
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    data = _wait_terminal(client, run_id)
    assert data["status"] == "succeeded"
    out = data.get("outputs") or {}
    assert out.get("upserted") == 1


def test_translate_step_simulated(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "translate",
        "version": 1,
        "steps": [
            {"id": "p", "type": "prompt", "config": {"template": "Bonjour"}},
            {"id": "t", "type": "translate", "config": {"target_lang": "en"}}
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    data = _wait_terminal(client, run_id)
    assert data["status"] == "succeeded"
    out = data.get("outputs") or {}
    assert out.get("target_lang") == "en"
    # In TEST_MODE, returns original text
    assert out.get("text")


def test_notify_step_test_mode(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "notify",
        "version": 1,
        "steps": [
            {"id": "n", "type": "notify", "config": {"url": "https://hooks.slack.com/services/test", "message": "{{ inputs.m }}"}}
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {"m": "Hello"}}).json()["run_id"]
    data = _wait_terminal(client, run_id)
    out = (data.get("outputs") or {})
    assert out.get("test_mode") is True


def test_diff_change_detector(client_with_wf: TestClient):
    client = client_with_wf
    definition = {
        "name": "diff",
        "version": 1,
        "steps": [
            {"id": "p", "type": "prompt", "config": {"template": "hello"}},
            {"id": "d", "type": "diff_change_detector", "config": {"current": "hello world", "method": "ratio", "threshold": 0.99}}
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    data = _wait_terminal(client, run_id)
    assert data["status"] == "succeeded"
    out = data.get("outputs") or {}
    assert out.get("changed") is True


def test_stt_transcribe_with_mock(monkeypatch, tmp_path, client_with_wf: TestClient):
    client = client_with_wf
    # Create a dummy wav file path (we won't actually read it since we mock)
    fake_wav = tmp_path / "fake.wav"
    fake_wav.write_bytes(b"RIFF\x00\x00\x00WAVEfmt ")

    # Patch speech_to_text to avoid heavy deps
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as ATL
    def _fake_stt(path, whisper_model='large-v3', selected_source_lang='en', vad_filter=False, diarize=False, *, word_timestamps=False, return_language=False):
        segments = [{"Text": "hello world", "start_seconds": 0.0, "end_seconds": 1.0}]
        return (segments, 'en') if return_language else segments
    monkeypatch.setattr(ATL, "speech_to_text", _fake_stt)

    definition = {
        "name": "stt",
        "version": 1,
        "steps": [
            {"id": "s", "type": "stt_transcribe", "config": {"file_uri": f"file://{fake_wav}", "model": "large-v3", "word_timestamps": False}}
        ],
    }
    wid = client.post("/api/v1/workflows", json=definition).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{wid}/run", json={"inputs": {}}).json()["run_id"]
    data = _wait_terminal(client, run_id)
    assert data["status"] == "succeeded"
    out = data.get("outputs") or {}
    assert "hello world" in out.get("text", "")
