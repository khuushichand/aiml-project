from __future__ import annotations

import os
import tempfile
import time
from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Claims_Extraction.claims_rebuild_service import get_claims_rebuild_service
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.config import settings


def _wait_for_claims_rebuild_completion(timeout: float = 6.0, poll_interval: float = 0.05) -> None:
    svc = get_claims_rebuild_service()
    deadline = time.time() + timeout
    expected_enqueued: int | None = None
    while time.time() < deadline:
        stats = svc.get_stats()
        enqueued = int(stats.get("enqueued", 0) or 0)
        if expected_enqueued is None:
            if enqueued == 0:
                time.sleep(poll_interval)
                continue
            expected_enqueued = enqueued
        processed = int(stats.get("processed", 0) or 0) + int(stats.get("failed", 0) or 0)
        unfinished = getattr(svc._queue, "unfinished_tasks", 0)  # type: ignore[attr-defined]
        if processed >= expected_enqueued and svc.get_queue_length() == 0 and unfinished == 0:
            return
        time.sleep(poll_interval)
    raise AssertionError("Claims rebuild worker did not finish within timeout")


class _User:
    id = 1
    username = "tester"
    is_admin = True


@pytest.mark.integration
@pytest.mark.parametrize(
    ("parse_mode", "expect_llm_object_claim"),
    [
        ("lenient", True),
        ("strict", False),
    ],
)
def test_claims_rebuild_parse_mode_api_behavior(monkeypatch, parse_mode: str, expect_llm_object_claim: bool):
    tmpdir = tempfile.mkdtemp(prefix="claims_api_parse_mode_")
    db_path = os.path.join(tmpdir, "media.db")
    seed_db = MediaDatabase(db_path=db_path, client_id="test_client")
    seed_db.initialize_db()
    media_id, _, _ = seed_db.add_media_with_keywords(
        title="Parse Mode Doc",
        media_type="text",
        content=(
            "Alpha fact sentence for fallback extraction. "
            "Beta fact sentence for fallback extraction."
        ),
        keywords=None,
    )
    seed_db.close_connection()

    original_env = {
        "MINIMAL_TEST_APP": os.environ.get("MINIMAL_TEST_APP"),
        "ROUTES_DISABLE": os.environ.get("ROUTES_DISABLE"),
    }
    os.environ["MINIMAL_TEST_APP"] = "1"
    os.environ["ROUTES_DISABLE"] = "media,audio,audio-websocket"

    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod

    async def _override_db() -> AsyncGenerator[MediaDatabase, None]:
        override_db = MediaDatabase(db_path=db_path, client_id="test_client")
        try:
            yield override_db
        finally:
            try:
                override_db.close_connection()
            except Exception:
                _ = None

    async def _override_user():
        return _User()

    def _fake_chat_api_call(
        api_endpoint,
        messages_payload,
        api_key=None,
        temp=None,
        system_message=None,
        streaming=False,
        model=None,
        response_format=None,
        **kwargs,
    ):
        # Wrapper-less payload parses in lenient mode but fails schema checks in strict mode.
        return '{"text":"LLM object claim"}'

    settings_keys = [
        "CLAIM_EXTRACTOR_MODE",
        "CLAIMS_MAX_PER_CHUNK",
        "CLAIMS_JSON_PARSE_MODE",
    ]
    snapshot = {key: settings.get(key) for key in settings_keys}

    fastapi_app.dependency_overrides[get_media_db_for_user] = _override_db
    fastapi_app.dependency_overrides[get_request_user] = _override_user
    monkeypatch.setattr(ingestion_mod, "chat_api_call", _fake_chat_api_call, raising=False)

    try:
        settings["CLAIM_EXTRACTOR_MODE"] = "openai"
        settings["CLAIMS_MAX_PER_CHUNK"] = 2
        settings["CLAIMS_JSON_PARSE_MODE"] = parse_mode

        with TestClient(fastapi_app) as client:
            r_rebuild = client.post(f"/api/v1/claims/{media_id}/rebuild")
            assert r_rebuild.status_code == 200, r_rebuild.text
            _wait_for_claims_rebuild_completion()

            r_claims = client.get(f"/api/v1/claims/{media_id}", params={"limit": 50})
            assert r_claims.status_code == 200, r_claims.text
            rows = r_claims.json()
            assert isinstance(rows, list) and rows
            texts = [str(row.get("claim_text") or "") for row in rows]

            if expect_llm_object_claim:
                assert any("LLM object claim" in text for text in texts)
            else:
                assert all("LLM object claim" not in text for text in texts)
                assert any("fallback extraction" in text for text in texts)
    finally:
        for key, value in snapshot.items():
            if value is None:
                settings.pop(key, None)
            else:
                settings[key] = value
        try:
            fastapi_app.dependency_overrides.pop(get_media_db_for_user, None)
            fastapi_app.dependency_overrides.pop(get_request_user, None)
        except Exception:
            _ = None
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
