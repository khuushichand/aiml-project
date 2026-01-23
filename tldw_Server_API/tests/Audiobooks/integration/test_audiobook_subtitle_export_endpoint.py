import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.audiobooks import router as audiobooks_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

pytestmark = pytest.mark.integration


def _post_subtitles(client, payload):
    return client.post("/api/v1/audiobooks/subtitles", json=payload)


@pytest.fixture()
def client_user_only(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "false")
    existing_enable = (os.getenv("ROUTES_ENABLE") or "").strip()
    enable_parts = [p for p in existing_enable.replace(" ", ",").split(",") if p]
    if "audiobooks" not in [p.lower() for p in enable_parts]:
        enable_parts.append("audiobooks")
    monkeypatch.setenv("ROUTES_ENABLE", ",".join(enable_parts))

    fastapi_app = FastAPI()
    fastapi_app.include_router(audiobooks_router, prefix="/api/v1")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()


def test_export_subtitles_srt_sentence_mode(client_user_only):
    payload = {
        "format": "srt",
        "mode": "sentence",
        "variant": "wide",
        "alignment": {
            "engine": "kokoro",
            "sample_rate": 24000,
            "words": [
                {"word": "Hello", "start_ms": 0, "end_ms": 400},
                {"word": "world.", "start_ms": 450, "end_ms": 900},
            ],
        },
    }
    resp = _post_subtitles(client_user_only, payload)
    assert resp.status_code == 200
    text = resp.text
    assert "Hello world." in text
    assert "00:00:00,000 --> 00:00:00,900" in text


def test_export_subtitles_from_alignment_output_cached(client_user_only):
    user_id = 1
    alignment_payload = {
        "engine": "kokoro",
        "sample_rate": 24000,
        "words": [
            {"word": "Hello", "start_ms": 0, "end_ms": 400},
            {"word": "world.", "start_ms": 450, "end_ms": 900},
        ],
    }
    outputs_dir = DatabasePaths.get_user_outputs_dir(user_id)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    alignment_filename = "alignment_test.json"
    (outputs_dir / alignment_filename).write_text(json.dumps(alignment_payload), encoding="utf-8")

    cdb = CollectionsDatabase(user_id)
    align_meta = {"project_id": "abk_test_sub", "chapter_id": "ch_001", "chapter_index": 0}
    alignment_row = cdb.create_output_artifact(
        type_="audiobook_alignment",
        title="alignment_test",
        format_="json",
        storage_path=alignment_filename,
        metadata_json=json.dumps(align_meta),
    )

    payload = {
        "format": "srt",
        "mode": "sentence",
        "variant": "wide",
        "alignment_output_id": alignment_row.id,
        "persist": True,
    }
    resp = _post_subtitles(client_user_only, payload)
    assert resp.status_code == 200
    output_id = resp.headers.get("X-Subtitle-Output-Id")
    assert output_id
    first_id = int(output_id)
    row = cdb.get_output_artifact(first_id)
    assert row.type == "audiobook_subtitle"

    resp2 = _post_subtitles(client_user_only, payload)
    assert resp2.status_code == 200
    assert resp2.headers.get("X-Subtitle-Output-Id") == str(first_id)
