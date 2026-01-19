import io
import json
import zipfile

import pytest
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.Slides_DB_Deps import get_slides_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.endpoints.slides import router as slides_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.Slides.slides_db import SlidesDatabase


def _build_assets(tmp_path):
    assets_dir = tmp_path / "revealjs"
    (assets_dir / "plugin" / "notes").mkdir(parents=True)
    (assets_dir / "theme").mkdir(parents=True)
    (assets_dir / "reveal.js").write_text("// reveal.js", encoding="utf-8")
    (assets_dir / "reveal.css").write_text("/* reveal.css */", encoding="utf-8")
    (assets_dir / "plugin" / "notes" / "notes.js").write_text("// notes", encoding="utf-8")
    (assets_dir / "theme" / "black.css").write_text("/* theme */", encoding="utf-8")
    (assets_dir / "LICENSE.revealjs.txt").write_text("license", encoding="utf-8")
    return assets_dir


class FakeNotesDB:
    def __init__(self) -> None:
        self.conversations = {"conv_1": {"id": "conv_1", "title": "Conversation"}}
        self.messages = {
            "conv_1": [
                {"sender": "user", "content": "Hello"},
                {"sender": "assistant", "content": "Summary points"},
            ]
        }
        self.notes = {
            "note_1": {"id": "note_1", "title": "Note 1", "content": "Content 1"},
            "note_2": {"id": "note_2", "title": "Note 2", "content": "Content 2"},
        }

    def get_conversation_by_id(self, conversation_id: str):
        return self.conversations.get(conversation_id)

    def get_messages_for_conversation(self, conversation_id: str, *args, **kwargs):
        return self.messages.get(conversation_id, [])

    def get_note_by_id(self, note_id: str):
        return self.notes.get(note_id)


class FakeMediaDB:
    def __init__(self) -> None:
        self.media = {1: {"id": 1, "title": "Media"}}

    def get_media_by_id(self, media_id: int, include_deleted: bool = False, include_trash: bool = False):
        return self.media.get(media_id)


@pytest.fixture()
def slides_client(tmp_path):
    app = FastAPI()
    app.include_router(slides_router, prefix="/api/v1", tags=["slides"])

    async def _override_user():
        return User(id=1, username="tester", email=None, is_active=True, is_admin=True)

    async def _override_principal(request=None):
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="test-user",
            token_type="single_user",
            jti=None,
            roles=["admin"],
            permissions=["media.create", "media.read", "media.update", "media.delete"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        if request is not None:
            request.state.auth = AuthContext(principal=principal, ip=None, user_agent=None, request_id=None)
        return principal

    async def _override_db():
        db = SlidesDatabase(db_path=tmp_path / "Slides.db", client_id="1")
        try:
            yield db
        finally:
            db.close_connection()

    app.dependency_overrides[get_request_user] = _override_user
    app.dependency_overrides[get_auth_principal] = _override_principal
    app.dependency_overrides[get_slides_db_for_user] = _override_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture()
def slides_client_with_sources(tmp_path):
    app = FastAPI()
    app.include_router(slides_router, prefix="/api/v1", tags=["slides"])
    fake_notes = FakeNotesDB()
    fake_media = FakeMediaDB()

    async def _override_user():
        return User(id=1, username="tester", email=None, is_active=True, is_admin=True)

    async def _override_principal(request=None):
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="test-user",
            token_type="single_user",
            jti=None,
            roles=["admin"],
            permissions=["media.create", "media.read", "media.update", "media.delete"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        if request is not None:
            request.state.auth = AuthContext(principal=principal, ip=None, user_agent=None, request_id=None)
        return principal

    async def _override_db():
        db = SlidesDatabase(db_path=tmp_path / "Slides.db", client_id="1")
        try:
            yield db
        finally:
            db.close_connection()

    async def _override_notes_db():
        return fake_notes

    async def _override_media_db():
        return fake_media

    app.dependency_overrides[get_request_user] = _override_user
    app.dependency_overrides[get_auth_principal] = _override_principal
    app.dependency_overrides[get_slides_db_for_user] = _override_db
    app.dependency_overrides[get_chacha_db_for_user] = _override_notes_db
    app.dependency_overrides[get_media_db_for_user] = _override_media_db

    with TestClient(app) as client:
        yield client, fake_notes, fake_media

    app.dependency_overrides.clear()


def _build_llm_stub(title: str):
    payload = {
        "title": title,
        "slides": [
            {
                "order": 0,
                "layout": "title",
                "title": title,
                "content": "",
                "speaker_notes": None,
                "metadata": {},
            }
        ],
    }

    def _stub(api_provider=None, messages=None, **kwargs):
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    return _stub


def _setup_chat_too_large(monkeypatch, fake_notes, fake_media):
    if fake_notes is None:
        return
    fake_notes.messages["conv_1"] = [{"sender": "user", "content": "x" * 50}]


def _setup_notes_too_large(monkeypatch, fake_notes, fake_media):
    if fake_notes is None:
        return
    fake_notes.notes["note_1"]["content"] = "x" * 50


def _setup_media_too_large(monkeypatch, fake_notes, fake_media):
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.slides.get_latest_transcription",
        lambda _db, _media_id: "x" * 50,
    )


def _setup_rag_too_large(monkeypatch, fake_notes, fake_media):
    async def stub_rag_pipeline(*args, **kwargs):
        doc = SimpleNamespace(content="x" * 50, metadata={"title": "Doc"})
        return SimpleNamespace(documents=[doc], generated_answer=None)

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.slides.unified_rag_pipeline",
        stub_rag_pipeline,
    )


_TOO_LARGE_CASES = [
    {
        "id": "prompt",
        "client": "slides_client",
        "path": "/api/v1/slides/generate",
        "payload": {
            "prompt": "x" * 50,
            "title_hint": "Big",
            "theme": "black",
            "max_source_chars": 10,
            "enable_chunking": False,
        },
        "setup": None,
    },
    {
        "id": "chat",
        "client": "slides_client_with_sources",
        "path": "/api/v1/slides/generate/from-chat",
        "payload": {
            "conversation_id": "conv_1",
            "title_hint": "Big Chat",
            "theme": "black",
            "max_source_chars": 10,
            "enable_chunking": False,
        },
        "setup": _setup_chat_too_large,
    },
    {
        "id": "notes",
        "client": "slides_client_with_sources",
        "path": "/api/v1/slides/generate/from-notes",
        "payload": {
            "note_ids": ["note_1"],
            "title_hint": "Big Notes",
            "theme": "black",
            "max_source_chars": 10,
            "enable_chunking": False,
        },
        "setup": _setup_notes_too_large,
    },
    {
        "id": "media",
        "client": "slides_client_with_sources",
        "path": "/api/v1/slides/generate/from-media",
        "payload": {
            "media_id": "1",
            "title_hint": "Big Media",
            "theme": "black",
            "max_source_chars": 10,
            "enable_chunking": False,
        },
        "setup": _setup_media_too_large,
    },
    {
        "id": "rag",
        "client": "slides_client",
        "path": "/api/v1/slides/generate/from-rag",
        "payload": {
            "query": "Big query",
            "title_hint": "Big RAG",
            "theme": "black",
            "max_source_chars": 10,
            "enable_chunking": False,
        },
        "setup": _setup_rag_too_large,
    },
]


def test_slides_create_and_export_json(slides_client):
    payload = {
        "title": "Deck",
        "description": None,
        "theme": "black",
        "settings": {"controls": True},
        "slides": [
            {"order": 0, "layout": "title", "title": "Deck", "content": "", "speaker_notes": None, "metadata": {}},
            {"order": 1, "layout": "content", "title": "Slide", "content": "- A\n- B", "speaker_notes": None, "metadata": {}},
        ],
        "custom_css": None,
    }
    resp = slides_client.post("/api/v1/slides/presentations", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Deck"
    presentation_id = data["id"]
    export_resp = slides_client.get(f"/api/v1/slides/presentations/{presentation_id}/export?format=json")
    assert export_resp.status_code == 200
    exported = export_resp.json()
    assert exported["id"] == presentation_id


def test_slides_export_reveal(slides_client, tmp_path, monkeypatch):
    assets_dir = _build_assets(tmp_path)
    monkeypatch.setenv("SLIDES_REVEALJS_ASSETS_DIR", str(assets_dir))
    payload = {
        "title": "Deck",
        "description": None,
        "theme": "black",
        "settings": {"controls": True},
        "slides": [
            {"order": 0, "layout": "title", "title": "Deck", "content": "", "speaker_notes": None, "metadata": {}},
        ],
        "custom_css": None,
    }
    resp = slides_client.post("/api/v1/slides/presentations", json=payload)
    presentation_id = resp.json()["id"]
    export_resp = slides_client.get(f"/api/v1/slides/presentations/{presentation_id}/export?format=revealjs")
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"].startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(export_resp.content)) as zf:
        assert "index.html" in zf.namelist()


def test_slides_export_markdown_marp_override(slides_client):
    payload = {
        "title": "Deck",
        "description": None,
        "theme": "black",
        "marp_theme": "gaia",
        "settings": {"controls": True},
        "slides": [
            {"order": 0, "layout": "title", "title": "Deck", "content": "", "speaker_notes": None, "metadata": {}},
        ],
        "custom_css": None,
    }
    resp = slides_client.post("/api/v1/slides/presentations", json=payload)
    assert resp.status_code == 201
    presentation_id = resp.json()["id"]
    export_resp = slides_client.get(f"/api/v1/slides/presentations/{presentation_id}/export?format=markdown")
    assert export_resp.status_code == 200
    assert "theme: gaia" in export_resp.text


def test_slides_generate_from_prompt_uses_stubbed_llm(slides_client, monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.slides_generator.perform_chat_api_call",
        _build_llm_stub("Generated Deck"),
    )

    resp = slides_client.post(
        "/api/v1/slides/generate",
        json={
            "title_hint": "Generated Deck",
            "prompt": "Summarize key findings.",
            "theme": "black",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Generated Deck"
    assert data["source_type"] == "prompt"


def test_slides_generate_from_rag_explicit_sources(slides_client, monkeypatch):
    sources_seen = {}

    async def stub_rag_pipeline(*args, **kwargs):
        sources_seen["sources"] = kwargs.get("sources")
        doc = SimpleNamespace(content="Doc content", metadata={"title": "Doc"})
        return SimpleNamespace(documents=[doc], generated_answer=None)

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.slides.unified_rag_pipeline",
        stub_rag_pipeline,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.slides_generator.perform_chat_api_call",
        _build_llm_stub("RAG Deck"),
    )

    resp = slides_client.post(
        "/api/v1/slides/generate/from-rag",
        json={
            "query": "Risks in roadmap",
            "title_hint": "RAG Deck",
            "theme": "black",
        },
    )
    assert resp.status_code == 200
    assert sources_seen["sources"] == ["media_db", "notes", "chats"]


def test_slides_generate_from_chat_uses_stubbed_llm(slides_client_with_sources, monkeypatch):
    client, _, _ = slides_client_with_sources
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.slides_generator.perform_chat_api_call",
        _build_llm_stub("Chat Deck"),
    )
    resp = client.post(
        "/api/v1/slides/generate/from-chat",
        json={
            "conversation_id": "conv_1",
            "title_hint": "Chat Deck",
            "theme": "black",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Chat Deck"
    assert data["source_type"] == "chat"
    assert data["source_ref"] == "conv_1"


def test_slides_generate_from_notes_uses_stubbed_llm(slides_client_with_sources, monkeypatch):
    client, _, _ = slides_client_with_sources
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.slides_generator.perform_chat_api_call",
        _build_llm_stub("Notes Deck"),
    )
    resp = client.post(
        "/api/v1/slides/generate/from-notes",
        json={
            "note_ids": ["note_1", "note_2"],
            "title_hint": "Notes Deck",
            "theme": "black",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Notes Deck"
    assert data["source_type"] == "notes"
    assert data["source_ref"] == ["note_1", "note_2"]


def test_slides_generate_from_media_uses_stubbed_llm(slides_client_with_sources, monkeypatch):
    client, _, _ = slides_client_with_sources
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.slides.get_latest_transcription",
        lambda _db, _media_id: "Transcript content",
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.slides_generator.perform_chat_api_call",
        _build_llm_stub("Media Deck"),
    )
    resp = client.post(
        "/api/v1/slides/generate/from-media",
        json={
            "media_id": "1",
            "title_hint": "Media Deck",
            "theme": "black",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Media Deck"
    assert data["source_type"] == "media"
    assert data["source_ref"] == 1


def test_slides_generate_from_chat_missing_conversation(slides_client_with_sources):
    client, fake_notes, _ = slides_client_with_sources
    fake_notes.conversations.pop("conv_1", None)
    resp = client.post(
        "/api/v1/slides/generate/from-chat",
        json={
            "conversation_id": "conv_1",
            "title_hint": "Chat Deck",
            "theme": "black",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "conversation_not_found"


def test_slides_generate_from_notes_missing_note(slides_client_with_sources):
    client, fake_notes, _ = slides_client_with_sources
    fake_notes.notes.pop("note_2", None)
    resp = client.post(
        "/api/v1/slides/generate/from-notes",
        json={
            "note_ids": ["note_1", "note_2"],
            "title_hint": "Notes Deck",
            "theme": "black",
        },
    )
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["missing_note_ids"] == ["note_2"]


def test_slides_generate_from_media_missing_media(slides_client_with_sources):
    client, _, fake_media = slides_client_with_sources
    fake_media.media.pop(1, None)
    resp = client.post(
        "/api/v1/slides/generate/from-media",
        json={
            "media_id": "1",
            "title_hint": "Media Deck",
            "theme": "black",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "media_not_found"


def test_slides_generate_from_media_missing_transcript(slides_client_with_sources, monkeypatch):
    client, _, _ = slides_client_with_sources
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.slides.get_latest_transcription",
        lambda _db, _media_id: None,
    )
    resp = client.post(
        "/api/v1/slides/generate/from-media",
        json={
            "media_id": "1",
            "title_hint": "Media Deck",
            "theme": "black",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "media_transcript_not_found"


def test_slides_generate_invalid_prompt(slides_client):
    resp = slides_client.post(
        "/api/v1/slides/generate",
        json={
            "prompt": "   ",
            "title_hint": "Bad",
            "theme": "black",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "prompt_required"


def test_slides_generate_invalid_conversation_id(slides_client):
    resp = slides_client.post(
        "/api/v1/slides/generate/from-chat",
        json={
            "conversation_id": "   ",
            "title_hint": "Bad",
            "theme": "black",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "conversation_id_required"


def test_slides_generate_invalid_note_ids(slides_client):
    resp = slides_client.post(
        "/api/v1/slides/generate/from-notes",
        json={
            "note_ids": [],
            "title_hint": "Bad",
            "theme": "black",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "note_ids_required"


def test_slides_generate_invalid_media_id(slides_client):
    resp = slides_client.post(
        "/api/v1/slides/generate/from-media",
        json={
            "media_id": "not-a-number",
            "title_hint": "Bad",
            "theme": "black",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "media_id_invalid"


def test_slides_generate_invalid_rag_query(slides_client):
    resp = slides_client.post(
        "/api/v1/slides/generate/from-rag",
        json={
            "query": "   ",
            "title_hint": "Bad",
            "theme": "black",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "query_required"


@pytest.mark.parametrize("case", _TOO_LARGE_CASES, ids=[c["id"] for c in _TOO_LARGE_CASES])
def test_slides_generate_too_large(case, request, monkeypatch):
    fake_notes = None
    fake_media = None
    if case["client"] == "slides_client_with_sources":
        client, fake_notes, fake_media = request.getfixturevalue("slides_client_with_sources")
    else:
        client = request.getfixturevalue("slides_client")
    setup = case.get("setup")
    if setup:
        setup(monkeypatch, fake_notes, fake_media)
    resp = client.post(case["path"], json=case["payload"])
    assert resp.status_code == 413
    detail = resp.json()["detail"]
    assert detail["code"] == "input_too_large"
    assert detail["max_source_chars"] == 10
