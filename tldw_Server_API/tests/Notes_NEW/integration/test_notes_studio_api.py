"""Integration tests for Notes Studio API endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_rate_limiter_dep
from tldw_Server_API.app.api.v1.endpoints import notes as notes_endpoint
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_notes_studio_db(tmp_path, monkeypatch):
    db_path = tmp_path / "notes_studio_integration.db"
    db = CharactersRAGDB(str(db_path), client_id="notes_studio_user")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    class _NoopRateLimiter:
        async def check_user_rate_limit(self, *_args, **_kwargs):
            return True, {}

    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user

    def override_db_dep():
        return db

    fastapi_app = FastAPI()
    fastapi_app.include_router(notes_endpoint.router, prefix="/api/v1/notes")

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = override_db_dep
    fastapi_app.dependency_overrides[get_rate_limiter_dep] = lambda: _NoopRateLimiter()

    with TestClient(fastapi_app) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


def _create_source_note(client: TestClient, *, title: str, content: str) -> str:
    response = client.post("/api/v1/notes/", json={"title": title, "content": content})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_notes_studio_derive_fetch_and_regenerate_flow(client_with_notes_studio_db: TestClient):
    client = client_with_notes_studio_db
    excerpt = "The mitochondrion is the powerhouse of the cell."
    source_note_id = _create_source_note(
        client,
        title="Biology",
        content=(
            "Cells need energy.\n"
            "The mitochondrion is the powerhouse of the cell.\n"
            "ATP supports cellular work."
        ),
    )

    derive_response = client.post(
        "/api/v1/notes/studio/derive",
        json={
            "source_note_id": source_note_id,
            "excerpt_text": excerpt,
            "template_type": "cornell",
            "handwriting_mode": "accented",
        },
    )
    assert derive_response.status_code == 201, derive_response.text
    derived = derive_response.json()
    note_id = derived["note"]["id"]

    assert derived["note"]["title"] == "Biology Study Notes"
    assert derived["studio_document"]["source_note_id"] == source_note_id
    assert derived["studio_document"]["excerpt_snapshot"] == excerpt
    assert derived["studio_document"]["excerpt_hash"].startswith("sha256:")
    assert derived["is_stale"] is False

    note_response = client.get(f"/api/v1/notes/{note_id}")
    assert note_response.status_code == 200
    note_payload = note_response.json()
    assert note_payload["studio"]["source_note_id"] == source_note_id

    fetch_response = client.get(f"/api/v1/notes/studio/{note_id}")
    assert fetch_response.status_code == 200
    fetched = fetch_response.json()
    assert fetched["studio_document"]["note_id"] == note_id
    assert fetched["is_stale"] is False

    drift_response = client.patch(
        f"/api/v1/notes/{note_id}",
        json={"content": "Manual drift"},
    )
    assert drift_response.status_code == 200, drift_response.text

    stale_response = client.get(f"/api/v1/notes/studio/{note_id}")
    assert stale_response.status_code == 200
    assert stale_response.json()["is_stale"] is True
    assert stale_response.json()["stale_reason"] == "companion_content_hash_mismatch"

    regenerate_response = client.post(f"/api/v1/notes/studio/{note_id}/regenerate")
    assert regenerate_response.status_code == 200, regenerate_response.text
    regenerated = regenerate_response.json()
    assert regenerated["is_stale"] is False
    assert "## Summary" in regenerated["note"]["content"]


def test_notes_studio_diagram_manifest_round_trip(client_with_notes_studio_db: TestClient):
    client = client_with_notes_studio_db
    source_note_id = _create_source_note(
        client,
        title="History",
        content="The printing press accelerated the spread of written knowledge across Europe.",
    )

    derive_response = client.post(
        "/api/v1/notes/studio/derive",
        json={
            "source_note_id": source_note_id,
            "excerpt_text": "The printing press accelerated the spread of written knowledge across Europe.",
            "template_type": "lined",
            "handwriting_mode": "off",
        },
    )
    assert derive_response.status_code == 201, derive_response.text
    payload = derive_response.json()
    note_id = payload["note"]["id"]
    sections = payload["studio_document"]["payload_json"]["sections"]

    diagram_response = client.post(
        f"/api/v1/notes/studio/{note_id}/diagram",
        json={
            "diagram_type": "flowchart",
            "source_section_ids": [sections[0]["id"], sections[1]["id"]],
        },
    )
    assert diagram_response.status_code == 200, diagram_response.text
    manifest = diagram_response.json()["studio_document"]["diagram_manifest_json"]

    assert manifest["diagram_type"] == "flowchart"
    assert manifest["source_section_ids"] == [sections[0]["id"], sections[1]["id"]]
    assert manifest["canonical_source"]
    assert manifest["cached_svg"].startswith("<svg")
    assert manifest["render_hash"].startswith("sha256:")
    assert manifest["status"] == "ready"


@pytest.mark.parametrize("excerpt_text", ["   ", "Excerpt missing from source"])
def test_notes_studio_rejects_invalid_excerpt_requests(
    client_with_notes_studio_db: TestClient,
    excerpt_text: str,
):
    client = client_with_notes_studio_db
    source_note_id = _create_source_note(
        client,
        title="Source",
        content="Useful content for excerpt validation.",
    )

    response = client.post(
        "/api/v1/notes/studio/derive",
        json={
            "source_note_id": source_note_id,
            "excerpt_text": excerpt_text,
            "template_type": "lined",
            "handwriting_mode": "accented",
        },
    )

    assert response.status_code == 400
