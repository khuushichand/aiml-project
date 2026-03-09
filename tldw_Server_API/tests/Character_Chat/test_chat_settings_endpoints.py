import shutil
import tempfile

import httpx
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings


pytestmark = pytest.mark.integration


def _valid_attachment(*, query: str = "Assess local-vs-web evidence", updated_at: str = "2026-03-08T20:00:00Z") -> dict:
    return {
        "run_id": "run_123",
        "query": query,
        "question": query,
        "outline": [{"title": "Summary"}, {"title": "Risks"}],
        "key_claims": [{"text": "Claim A"}, {"text": "Claim B"}],
        "unresolved_questions": ["What primary source is still missing?"],
        "verification_summary": {"unsupported_claim_count": 1},
        "source_trust_summary": {"high_trust_count": 2},
        "research_url": "/research?run=run_123",
        "attached_at": "2026-03-08T19:55:00Z",
        "updatedAt": updated_at,
    }


async def _create_chat(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    characters = await client.get("/api/v1/characters/", headers=headers)
    assert characters.status_code == 200
    character_id = characters.json()[0]["id"]

    created = await client.post(
        "/api/v1/chats/",
        headers=headers,
        json={"character_id": character_id, "title": "Persisted attachment chat"},
    )
    assert created.status_code == 201
    return created.json()["id"]


@pytest.mark.asyncio
async def test_chat_settings_roundtrip_persists_deep_research_attachment(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="chacha_deep_research_attachment_")
    monkeypatch.setenv("USER_DB_BASE_DIR", tmpdir)
    reset_settings()
    try:
        from tldw_Server_API.app.main import app

        headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            chat_id = await _create_chat(client, headers)
            payload = {
                "settings": {
                    "schemaVersion": 2,
                    "updatedAt": "2026-03-08T20:00:00Z",
                    "deepResearchAttachment": _valid_attachment(),
                }
            }

            put_response = await client.put(
                f"/api/v1/chats/{chat_id}/settings",
                headers=headers,
                json=payload,
            )
            assert put_response.status_code == 200, put_response.text

            get_response = await client.get(
                f"/api/v1/chats/{chat_id}/settings",
                headers=headers,
            )
            assert get_response.status_code == 200, get_response.text
            stored = get_response.json()["settings"]["deepResearchAttachment"]
            assert stored["run_id"] == "run_123"
            assert stored["verification_summary"]["unsupported_claim_count"] == 1
            assert stored["source_trust_summary"]["high_trust_count"] == 2
    finally:
        reset_settings()
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_chat_settings_rejects_unknown_keys_inside_deep_research_attachment(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="chacha_attachment_unknown_key_")
    monkeypatch.setenv("USER_DB_BASE_DIR", tmpdir)
    reset_settings()
    try:
        from tldw_Server_API.app.main import app

        headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            chat_id = await _create_chat(client, headers)
            attachment = _valid_attachment()
            attachment["full_bundle"] = {"too": "much"}

            response = await client.put(
                f"/api/v1/chats/{chat_id}/settings",
                headers=headers,
                json={
                    "settings": {
                        "schemaVersion": 2,
                        "updatedAt": "2026-03-08T20:00:00Z",
                        "deepResearchAttachment": attachment,
                    }
                },
            )
            assert response.status_code == 422, response.text
            assert "deepResearchAttachment" in response.json()["detail"]
    finally:
        reset_settings()
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_chat_settings_rejects_invalid_attachment_updated_at(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="chacha_attachment_bad_updated_at_")
    monkeypatch.setenv("USER_DB_BASE_DIR", tmpdir)
    reset_settings()
    try:
        from tldw_Server_API.app.main import app

        headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            chat_id = await _create_chat(client, headers)
            attachment = _valid_attachment(updated_at="not-a-timestamp")

            response = await client.put(
                f"/api/v1/chats/{chat_id}/settings",
                headers=headers,
                json={
                    "settings": {
                        "schemaVersion": 2,
                        "updatedAt": "2026-03-08T20:00:00Z",
                        "deepResearchAttachment": attachment,
                    }
                },
            )
            assert response.status_code == 422, response.text
            assert "deepResearchAttachment.updatedAt" in response.json()["detail"]
    finally:
        reset_settings()
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_chat_settings_attachment_merge_prefers_newer_attachment_timestamp(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="chacha_attachment_merge_")
    monkeypatch.setenv("USER_DB_BASE_DIR", tmpdir)
    reset_settings()
    try:
        from tldw_Server_API.app.main import app

        headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            chat_id = await _create_chat(client, headers)

            baseline_response = await client.put(
                f"/api/v1/chats/{chat_id}/settings",
                headers=headers,
                json={
                    "settings": {
                        "schemaVersion": 2,
                        "updatedAt": "2026-03-08T20:10:00Z",
                        "greetingEnabled": True,
                        "deepResearchAttachment": _valid_attachment(
                            query="Older attachment",
                            updated_at="2026-03-08T20:00:00Z",
                        ),
                    }
                },
            )
            assert baseline_response.status_code == 200, baseline_response.text

            merge_response = await client.put(
                f"/api/v1/chats/{chat_id}/settings",
                headers=headers,
                json={
                    "settings": {
                        "schemaVersion": 2,
                        "updatedAt": "2026-03-08T20:05:00Z",
                        "authorNote": "older top-level patch should not win",
                        "deepResearchAttachment": _valid_attachment(
                            query="Newer attachment snapshot",
                            updated_at="2026-03-08T20:20:00Z",
                        ),
                    }
                },
            )
            assert merge_response.status_code == 200, merge_response.text
            merged = merge_response.json()["settings"]
            assert merged["greetingEnabled"] is True
            assert merged.get("authorNote") == "older top-level patch should not win"
            assert merged["updatedAt"] == "2026-03-08T20:10:00Z"
            assert merged["deepResearchAttachment"]["query"] == "Newer attachment snapshot"
            assert merged["deepResearchAttachment"]["updatedAt"] == "2026-03-08T20:20:00Z"
    finally:
        reset_settings()
        shutil.rmtree(tmpdir, ignore_errors=True)
