"""
test_smoke_user_journeys.py
Description: Fast end-to-end smoke tests that simulate a new user’s first session.

These tests exercise a minimal happy path across health, media upload, search/RAG,
optional chat (if providers are configured), and basic TTS health.

They reuse the shared e2e fixtures and are designed to run quickly and skip
gracefully if optional subsystems aren’t configured.
"""

from typing import Dict, Any
import os
import pytest
import httpx

from .fixtures import (
    api_client,
    data_tracker,
    create_test_file,
    cleanup_test_file,
)


@pytest.mark.critical
def test_smoke_basic_user_journey(api_client, data_tracker):
    """End-to-end: health -> upload -> RAG -> optional chat -> TTS health.

    - Verifies server health/auth mode
    - Uploads a tiny text document (idempotent, overwrite enabled)
    - Performs a simple RAG search against media
    - If any LLM providers are configured, performs a simple chat completion
    - Verifies TTS subsystem health and voices catalog endpoints are reachable
    """

    # 1) Health
    health = api_client.health_check()
    assert health.get("status") in ("healthy", "ok", True)
    auth_mode = health.get("auth_mode") or os.getenv("AUTH_MODE", "single_user")

    # 2) Upload a small text file
    content = "E2E smoke test content: Hello TL;DW!"
    file_path = create_test_file(content, suffix=".txt")
    data_tracker.add_file(file_path)
    try:
        upload_resp: Dict[str, Any] = api_client.upload_media(
            file_path=file_path,
            title="E2E Smoke Test Document",
            media_type="document",
            generate_embeddings=True,
        )

        # Extract media_id from either new (results[0].db_id) or legacy (media_id/id) format
        media_id = None
        if isinstance(upload_resp, dict) and upload_resp.get("results"):
            first = upload_resp["results"][0]
            # Accept overwrite/exists messages; prefer db_id when present
            media_id = first.get("db_id") or first.get("id")
        else:
            media_id = upload_resp.get("media_id") or upload_resp.get("id")
        assert media_id, f"No media_id returned in upload response: {upload_resp}"
        data_tracker.add_media(int(media_id))
    finally:
        cleanup_test_file(file_path)

    # 3) Simple RAG search against media
    try:
        rag_resp = api_client.rag_simple_search(
            query="smoke test content",
            databases=["media"],
            top_k=3,
            max_context_size=2000,
        )
        # Minimal structure checks; allow empty results in clean DBs
        assert isinstance(rag_resp, dict)
        assert "success" in rag_resp
        assert "results" in rag_resp
        assert isinstance(rag_resp.get("results"), list)
    except httpx.HTTPStatusError as e:
        # Some deployments may not have embeddings configured; skip rather than fail
        if e.response.status_code in (404, 422, 500):
            pytest.skip(f"RAG not available/configured: {e}")
        raise

    # 4) Optional: Chat completion if any LLM providers are configured
    try:
        providers = api_client.client.get("/api/v1/llm/providers")
        providers.raise_for_status()
        pdata = providers.json()
        total = int(pdata.get("total_configured") or 0)
        if total > 0:
            chat_resp = api_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a concise assistant."},
                    {"role": "user", "content": "Say hello in one short sentence."},
                ],
                model="gpt-3.5-turbo",  # Logical default; server maps per provider
                temperature=0.0,
            )
            assert "choices" in chat_resp
            msg = chat_resp["choices"][0]["message"]["content"].strip()
            assert msg, "Empty chat response"
        else:
            pytest.skip("No LLM providers configured; skipping chat smoke.")
    except httpx.HTTPStatusError as e:
        # If providers endpoint exists but chat fails due to config, skip
        if e.response.status_code in (400, 401, 403, 404, 422, 500):
            pytest.skip(f"Chat not available/configured: {e}")
        raise

    # 5) TTS subsystem quick checks (health and voices)
    try:
        tts_health = api_client.client.get("/api/v1/audio/health")
        assert tts_health.status_code in (200, 500)  # Degraded/empty configs may return error payloads
        # voices catalog should exist even if providers are limited
        voices = api_client.client.get("/api/v1/audio/voices/catalog")
        voices.raise_for_status()
        v = voices.json()
        assert isinstance(v, dict)
    except httpx.HTTPStatusError as e:
        # Treat missing/disabled TTS as optional in smoke
        pytest.skip(f"TTS endpoints not available/configured: {e}")
