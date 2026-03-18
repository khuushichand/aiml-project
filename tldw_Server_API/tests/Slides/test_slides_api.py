import io
import json
import zipfile

import pytest
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import get_collections_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.Slides_DB_Deps import get_slides_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.endpoints.slides import router as slides_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.Slides.slides_db import SlidesDatabase
from tldw_Server_API.app.core.Slides.slides_export import SlidesExportError, SlidesExportInputError

_SAMPLE_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAn8B9XgU1b0AAAAASUVORK5CYII="
)


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


def _write_templates(tmp_path):
    templates = {
        "templates": [
            {
                "id": "template-1",
                "name": "Template One",
                "theme": "white",
                "marp_theme": "gaia",
                "settings": {"controls": False, "progress": False},
                "default_slides": [
                    {
                        "order": 0,
                        "layout": "title",
                        "title": "Template Title",
                        "content": "",
                        "speaker_notes": None,
                        "metadata": {},
                    },
                    {
                        "order": 1,
                        "layout": "content",
                        "title": "Template Slide",
                        "content": "- Item 1\n- Item 2",
                        "speaker_notes": None,
                        "metadata": {},
                    },
                ],
                "custom_css": ".reveal { font-size: 36px; }",
            }
        ]
    }
    path = tmp_path / "templates.json"
    path.write_text(json.dumps(templates), encoding="utf-8")
    return path


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


class FakeCollectionsDB:
    def get_output_artifact(self, output_id: int):
        return {"id": output_id}

    def resolve_output_storage_path(self, path_value):
        return str(path_value)


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

    async def _override_collections_db():
        return FakeCollectionsDB()

    app.dependency_overrides[get_request_user] = _override_user
    app.dependency_overrides[get_auth_principal] = _override_principal
    app.dependency_overrides[get_slides_db_for_user] = _override_db
    app.dependency_overrides[get_collections_db_for_user] = _override_collections_db

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

    async def _override_collections_db():
        return FakeCollectionsDB()

    app.dependency_overrides[get_request_user] = _override_user
    app.dependency_overrides[get_auth_principal] = _override_principal
    app.dependency_overrides[get_slides_db_for_user] = _override_db
    app.dependency_overrides[get_chacha_db_for_user] = _override_notes_db
    app.dependency_overrides[get_media_db_for_user] = _override_media_db
    app.dependency_overrides[get_collections_db_for_user] = _override_collections_db

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
            "media_id": 1,
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
        "studio_data": {
            "origin": "blank",
            "default_voice": {"provider": "openai", "voice": "alloy"},
        },
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
    assert data["studio_data"] == payload["studio_data"]
    presentation_id = data["id"]
    export_resp = slides_client.get(f"/api/v1/slides/presentations/{presentation_id}/export?format=json")
    assert export_resp.status_code == 200
    exported = export_resp.json()
    assert exported["id"] == presentation_id
    assert exported["studio_data"] == payload["studio_data"]


def test_slides_create_canonicalizes_presentation_studio_slide_metadata(slides_client):
    payload = {
        "title": "Deck",
        "description": None,
        "theme": "black",
        "studio_data": {
            "origin": "blank",
        },
        "slides": [
            {
                "order": 0,
                "layout": "title",
                "title": "Deck",
                "content": "",
                "speaker_notes": "",
                "metadata": {
                    "studio": {
                        "slideId": "slide-1",
                        "audio": {"status": "missing"},
                        "image": {"status": "missing"},
                    }
                },
            }
        ],
        "custom_css": None,
    }

    resp = slides_client.post("/api/v1/slides/presentations", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    studio = data["slides"][0]["metadata"]["studio"]
    assert studio["slideId"] == "slide-1"
    assert studio["transition"] == "fade"
    assert studio["timing_mode"] == "auto"
    assert studio["manual_duration_ms"] is None
    assert studio["audio"]["status"] == "missing"
    assert studio["image"]["status"] == "missing"

    export_resp = slides_client.get(f"/api/v1/slides/presentations/{data['id']}/export?format=json")
    assert export_resp.status_code == 200
    exported = export_resp.json()
    exported_studio = exported["slides"][0]["metadata"]["studio"]
    assert exported_studio["transition"] == "fade"
    assert exported_studio["timing_mode"] == "auto"
    assert exported_studio["manual_duration_ms"] is None


def test_slides_create_rejects_invalid_image(slides_client):
    payload = {
        "title": "Deck",
        "theme": "black",
        "slides": [
            {
                "order": 0,
                "layout": "content",
                "title": "Slide",
                "content": "",
                "speaker_notes": None,
                "metadata": {"images": [{"mime": "image/png", "data_b64": "not-base64"}]},
            }
        ],
    }
    resp = slides_client.post("/api/v1/slides/presentations", json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "image_data_b64_invalid"


def test_slides_create_and_export_markdown_with_image_asset_ref(slides_client, monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.slides.resolve_slide_asset",
        lambda asset_ref, **kwargs: {
            "asset_ref": asset_ref,
            "mime": "image/png",
            "data_b64": _SAMPLE_PNG_B64,
            "alt": "Cover",
        },
    )
    payload = {
        "title": "Deck",
        "theme": "black",
        "slides": [
            {
                "order": 0,
                "layout": "content",
                "title": "Slide",
                "content": "Hello",
                "speaker_notes": None,
                "metadata": {"images": [{"asset_ref": "output:123", "alt": "Cover"}]},
            }
        ],
    }

    resp = slides_client.post("/api/v1/slides/presentations", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["slides"][0]["metadata"]["images"][0]["asset_ref"] == "output:123"

    export_resp = slides_client.get(f"/api/v1/slides/presentations/{data['id']}/export?format=markdown")
    assert export_resp.status_code == 200
    assert "![Cover](data:image/png;base64," in export_resp.text


def test_slides_export_offloads_blocking_markdown_and_reveal_generation(
    slides_client, monkeypatch, tmp_path
):
    assets_dir = _build_assets(tmp_path)
    monkeypatch.setenv("SLIDES_REVEALJS_ASSETS_DIR", str(assets_dir))
    offloaded_calls: list[str] = []

    async def _fake_to_thread(func, *args, **kwargs):
        offloaded_calls.append(getattr(func, "__name__", repr(func)))
        return func(*args, **kwargs)

    monkeypatch.setattr("tldw_Server_API.app.api.v1.endpoints.slides.asyncio.to_thread", _fake_to_thread)
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.slides.resolve_slide_asset",
        lambda asset_ref, **kwargs: {
            "asset_ref": asset_ref,
            "mime": "image/png",
            "data_b64": _SAMPLE_PNG_B64,
            "alt": "Cover",
        },
    )
    payload = {
        "title": "Deck",
        "theme": "black",
        "slides": [
            {
                "order": 0,
                "layout": "content",
                "title": "Slide",
                "content": "Hello",
                "speaker_notes": "Narration",
                "metadata": {"images": [{"asset_ref": "output:123", "alt": "Cover"}]},
            }
        ],
    }

    create_resp = slides_client.post("/api/v1/slides/presentations", json=payload)
    assert create_resp.status_code == 201, create_resp.text
    presentation_id = create_resp.json()["id"]

    markdown_resp = slides_client.get(
        f"/api/v1/slides/presentations/{presentation_id}/export?format=markdown"
    )
    assert markdown_resp.status_code == 200, markdown_resp.text

    reveal_resp = slides_client.get(
        f"/api/v1/slides/presentations/{presentation_id}/export?format=revealjs"
    )
    assert reveal_resp.status_code == 200, reveal_resp.text

    assert "export_presentation_markdown" in offloaded_calls
    assert "export_presentation_bundle" in offloaded_calls


def test_slides_export_reveal(slides_client, tmp_path, monkeypatch):
    assets_dir = _build_assets(tmp_path)
    monkeypatch.setenv("SLIDES_REVEALJS_ASSETS_DIR", str(assets_dir))
    payload = {
        "title": "Deck",
        "description": None,
        "theme": "black",
        "settings": {"controls": True},
        "slides": [
            {
                "order": 0,
                "layout": "title",
                "title": "Deck",
                "content": "",
                "speaker_notes": None,
                "metadata": {
                    "images": [
                        {
                            "mime": "image/png",
                            "data_b64": _SAMPLE_PNG_B64,
                            "alt": "Logo",
                            "width": 16,
                            "height": 16,
                        }
                    ]
                },
            },
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
        index_html = zf.read("index.html").decode("utf-8")
        assert "data:image/png;base64," in index_html
        assert "alt=\"Logo\"" in index_html


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


def test_slides_export_pdf(slides_client, monkeypatch):
    captured = {}

    def _stub_export(**kwargs):
        captured["options"] = kwargs.get("pdf_options")
        return b"%PDF-1.4\n%stub"

    monkeypatch.setattr("tldw_Server_API.app.api.v1.endpoints.slides.export_presentation_pdf", _stub_export)
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
    export_resp = slides_client.get(
        f"/api/v1/slides/presentations/{presentation_id}/export?format=pdf&pdf_format=Letter&pdf_landscape=true&pdf_margin_top=0.2in"
    )
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"].startswith("application/pdf")
    assert export_resp.content.startswith(b"%PDF")
    options = captured.get("options") or {}
    assert options.get("format") == "Letter"
    assert options.get("landscape") is True
    assert (options.get("margin") or {}).get("top") == "0.2in"


def test_slides_export_pdf_input_error(slides_client, monkeypatch):
    def _stub_export(**kwargs):
        raise SlidesExportInputError("pdf_format_invalid")

    monkeypatch.setattr("tldw_Server_API.app.api.v1.endpoints.slides.export_presentation_pdf", _stub_export)
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
    export_resp = slides_client.get(f"/api/v1/slides/presentations/{presentation_id}/export?format=pdf")
    assert export_resp.status_code == 422
    assert export_resp.json()["detail"] == "pdf_format_invalid"


def test_slides_export_pdf_failure(slides_client, monkeypatch):
    def _stub_export(**kwargs):
        raise SlidesExportError("pdf_render_failed")

    monkeypatch.setattr("tldw_Server_API.app.api.v1.endpoints.slides.export_presentation_pdf", _stub_export)
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
    export_resp = slides_client.get(f"/api/v1/slides/presentations/{presentation_id}/export?format=pdf")
    assert export_resp.status_code == 500
    assert export_resp.json()["detail"] == "pdf_render_failed"


def test_slides_templates_list_and_get(slides_client, tmp_path, monkeypatch):
    templates_path = _write_templates(tmp_path)
    monkeypatch.setenv("SLIDES_TEMPLATES_PATH", str(templates_path))
    list_resp = slides_client.get("/api/v1/slides/templates")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["templates"][0]["id"] == "template-1"

    get_resp = slides_client.get("/api/v1/slides/templates/template-1")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Template One"


def test_slides_styles_list_returns_builtin_and_user_styles(slides_client):
    create_resp = slides_client.post(
        "/api/v1/slides/styles",
        json={
            "name": "Exam Sprint",
            "description": "Recall-first deck",
            "generation_rules": {"exam_focus": True, "bullet_bias": "high"},
            "artifact_preferences": ["stat_group"],
            "appearance_defaults": {"theme": "white"},
            "fallback_policy": {"mode": "key-points"},
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created_id = create_resp.json()["id"]

    list_resp = slides_client.get("/api/v1/slides/styles")
    assert list_resp.status_code == 200
    styles = list_resp.json()["styles"]

    assert any(item["scope"] == "builtin" and item["id"] == "timeline" for item in styles)
    assert any(item["scope"] == "user" and item["id"] == created_id for item in styles)


def test_slides_styles_crud_for_user_styles(slides_client):
    create_resp = slides_client.post(
        "/api/v1/slides/styles",
        json={
            "name": "Exam Sprint",
            "description": "Recall-first deck",
            "generation_rules": {"exam_focus": True, "bullet_bias": "high"},
            "artifact_preferences": ["stat_group"],
            "appearance_defaults": {"theme": "white"},
            "fallback_policy": {"mode": "key-points"},
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    style_id = created["id"]
    assert created["scope"] == "user"
    assert created["generation_rules"]["exam_focus"] is True

    get_resp = slides_client.get(f"/api/v1/slides/styles/{style_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Exam Sprint"

    patch_resp = slides_client.patch(
        f"/api/v1/slides/styles/{style_id}",
        json={
            "name": "Exam Sprint Updated",
            "generation_rules": {"exam_focus": True, "bullet_bias": "medium"},
            "artifact_preferences": ["comparison_matrix"],
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    patched = patch_resp.json()
    assert patched["name"] == "Exam Sprint Updated"
    assert patched["generation_rules"]["bullet_bias"] == "medium"
    assert patched["artifact_preferences"] == ["comparison_matrix"]

    delete_resp = slides_client.delete(f"/api/v1/slides/styles/{style_id}")
    assert delete_resp.status_code == 204

    missing_resp = slides_client.get(f"/api/v1/slides/styles/{style_id}")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["detail"] == "visual_style_not_found"


def test_slides_styles_reject_builtin_mutation(slides_client):
    patch_resp = slides_client.patch(
        "/api/v1/slides/styles/timeline",
        json={"name": "Rewritten Timeline"},
    )
    assert patch_resp.status_code == 403
    assert patch_resp.json()["detail"] == "builtin_visual_style_read_only"


def test_slides_styles_reject_non_string_custom_css(slides_client):
    create_resp = slides_client.post(
        "/api/v1/slides/styles",
        json={
            "name": "Broken CSS Style",
            "description": "Should fail validation",
            "generation_rules": {},
            "artifact_preferences": [],
            "appearance_defaults": {
                "theme": "white",
                "custom_css": {"selector": ".reveal"},
            },
            "fallback_policy": {"mode": "outline"},
        },
    )
    assert create_resp.status_code == 422
    assert create_resp.json()["detail"] == "invalid_visual_style_custom_css"


def test_slides_create_rejects_resolved_style_with_non_string_custom_css(slides_client, monkeypatch):
    def _broken_style(_self, style_id: str):
        return SimpleNamespace(
            id=style_id,
            scope="user",
            name="Broken CSS Style",
            style_payload=json.dumps(
                {
                    "description": "Broken style payload",
                    "generation_rules": {},
                    "artifact_preferences": [],
                    "appearance_defaults": {
                        "theme": "white",
                        "custom_css": {"selector": ".reveal"},
                    },
                    "fallback_policy": {"mode": "outline"},
                }
            ),
            created_at="2026-03-17T00:00:00Z",
            updated_at="2026-03-17T00:00:00Z",
        )

    monkeypatch.setattr(SlidesDatabase, "get_visual_style_by_id", _broken_style)

    resp = slides_client.post(
        "/api/v1/slides/presentations",
        json={
            "title": "Broken Style Deck",
            "visual_style_id": "broken-css-style",
            "visual_style_scope": "user",
            "slides": [
                {
                    "order": 0,
                    "layout": "title",
                    "title": "Broken",
                    "content": "",
                    "speaker_notes": None,
                    "metadata": {},
                }
            ],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "invalid_visual_style_custom_css"


def test_slides_create_with_template_defaults(slides_client, tmp_path, monkeypatch):
    templates_path = _write_templates(tmp_path)
    monkeypatch.setenv("SLIDES_TEMPLATES_PATH", str(templates_path))
    resp = slides_client.post(
        "/api/v1/slides/presentations",
        json={
            "title": "Deck",
            "template_id": "template-1",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["theme"] == "white"
    assert data["marp_theme"] == "gaia"
    assert data["template_id"] == "template-1"
    assert data["custom_css"] == ".reveal { font-size: 36px; }"
    assert data["slides"][0]["title"] == "Template Title"


def test_slides_create_persists_visual_style_snapshot(slides_client):
    resp = slides_client.post(
        "/api/v1/slides/presentations",
        json={
            "title": "History Deck",
            "visual_style_id": "timeline",
            "visual_style_scope": "builtin",
            "slides": [
                {
                    "order": 0,
                    "layout": "title",
                    "title": "History",
                    "content": "",
                    "speaker_notes": None,
                    "metadata": {},
                }
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    payload = resp.json()
    assert payload["visual_style_id"] == "timeline"
    assert payload["visual_style_scope"] == "builtin"
    assert payload["visual_style_name"] == "Timeline"
    assert payload["visual_style_version"] == 1
    assert payload["visual_style_snapshot"]["id"] == "timeline"
    assert payload["visual_style_snapshot"]["scope"] == "builtin"


def test_slides_patch_updates_visual_style_snapshot(slides_client):
    create_resp = slides_client.post(
        "/api/v1/slides/presentations",
        json={
            "title": "History Deck",
            "slides": [
                {
                    "order": 0,
                    "layout": "title",
                    "title": "History",
                    "content": "",
                    "speaker_notes": None,
                    "metadata": {},
                }
            ],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    presentation_id = create_resp.json()["id"]
    patch_resp = slides_client.patch(
        f"/api/v1/slides/presentations/{presentation_id}",
        json={
            "visual_style_id": "timeline",
            "visual_style_scope": "builtin",
        },
        headers={"If-Match": create_resp.headers["ETag"]},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    payload = patch_resp.json()
    assert payload["visual_style_id"] == "timeline"
    assert payload["visual_style_scope"] == "builtin"
    assert payload["visual_style_snapshot"]["id"] == "timeline"


def test_slides_generate_with_template_defaults(slides_client, tmp_path, monkeypatch):
    templates_path = _write_templates(tmp_path)
    monkeypatch.setenv("SLIDES_TEMPLATES_PATH", str(templates_path))
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.slides_generator.perform_chat_api_call",
        _build_llm_stub("Generated Deck"),
    )
    resp = slides_client.post(
        "/api/v1/slides/generate",
        json={
            "title_hint": "Generated Deck",
            "prompt": "Summarize key findings.",
            "template_id": "template-1",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["theme"] == "white"
    assert data["marp_theme"] == "gaia"
    assert data["template_id"] == "template-1"
    assert data["custom_css"] == ".reveal { font-size: 36px; }"


def test_slides_generate_with_visual_style_snapshot(slides_client, monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.slides_generator.perform_chat_api_call",
        _build_llm_stub("Generated History Deck"),
    )
    resp = slides_client.post(
        "/api/v1/slides/generate",
        json={
            "title_hint": "Generated History Deck",
            "prompt": "Summarize key history milestones.",
            "visual_style_id": "timeline",
            "visual_style_scope": "builtin",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["visual_style_id"] == "timeline"
    assert data["visual_style_scope"] == "builtin"
    assert data["visual_style_snapshot"]["id"] == "timeline"
    assert data["theme"] == "beige"


def test_slides_reorder(slides_client):
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
    presentation_id = resp.json()["id"]
    etag = resp.headers["ETag"]
    reorder_resp = slides_client.post(
        f"/api/v1/slides/presentations/{presentation_id}/reorder",
        json={"order": [1, 0]},
        headers={"If-Match": etag},
    )
    assert reorder_resp.status_code == 200
    reordered = reorder_resp.json()
    assert reordered["slides"][0]["title"] == "Slide"


def test_slides_versions_and_restore(slides_client):
    payload = {
        "title": "Deck",
        "description": None,
        "theme": "black",
        "settings": {"controls": True},
        "studio_data": {
            "origin": "blank",
            "default_voice": {"provider": "openai", "voice": "alloy"},
        },
        "slides": [
            {"order": 0, "layout": "title", "title": "Deck", "content": "", "speaker_notes": None, "metadata": {}},
        ],
        "custom_css": None,
    }
    resp = slides_client.post("/api/v1/slides/presentations", json=payload)
    assert resp.status_code == 201
    presentation_id = resp.json()["id"]
    etag = resp.headers["ETag"]

    update_resp = slides_client.patch(
        f"/api/v1/slides/presentations/{presentation_id}",
        json={
            "title": "Updated",
            "studio_data": {
                "origin": "extension_capture",
                "default_voice": {"provider": "openai", "voice": "verse"},
            },
        },
        headers={"If-Match": etag},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["studio_data"]["origin"] == "extension_capture"
    new_etag = update_resp.headers["ETag"]

    versions_resp = slides_client.get(f"/api/v1/slides/presentations/{presentation_id}/versions")
    assert versions_resp.status_code == 200
    versions_data = versions_resp.json()
    assert versions_data["total"] == 2
    assert versions_data["versions"][0]["version"] == 2

    version_resp = slides_client.get(f"/api/v1/slides/presentations/{presentation_id}/versions/1")
    assert version_resp.status_code == 200
    assert version_resp.json()["title"] == "Deck"
    assert version_resp.json()["studio_data"] == payload["studio_data"]

    restore_resp = slides_client.post(
        f"/api/v1/slides/presentations/{presentation_id}/versions/1/restore",
        headers={"If-Match": new_etag},
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["title"] == "Deck"
    assert restore_resp.json()["studio_data"] == payload["studio_data"]


def test_slides_patch_persists_presentation_studio_timing_and_transition_metadata(slides_client):
    create_resp = slides_client.post(
        "/api/v1/slides/presentations",
        json={
            "title": "Deck",
            "description": None,
            "theme": "black",
            "studio_data": {"origin": "blank"},
            "slides": [
                {
                    "order": 0,
                    "layout": "content",
                    "title": "Slide",
                    "content": "Body",
                    "speaker_notes": "Narration",
                    "metadata": {
                        "studio": {
                            "slideId": "slide-1",
                            "audio": {"status": "ready", "duration_ms": 12000},
                            "image": {"status": "ready"},
                        }
                    },
                }
            ],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    presentation_id = create_resp.json()["id"]
    etag = create_resp.headers["ETag"]

    patch_resp = slides_client.patch(
        f"/api/v1/slides/presentations/{presentation_id}",
        json={
            "slides": [
                {
                    "order": 0,
                    "layout": "content",
                    "title": "Slide",
                    "content": "Body",
                    "speaker_notes": "Narration",
                    "metadata": {
                        "studio": {
                            "slideId": "slide-1",
                            "transition": "wipe",
                            "timing_mode": "manual",
                            "manual_duration_ms": 45000,
                            "audio": {"status": "ready", "duration_ms": 12000},
                            "image": {"status": "ready"},
                        }
                    },
                }
            ]
        },
        headers={"If-Match": etag},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    patched = patch_resp.json()
    patched_studio = patched["slides"][0]["metadata"]["studio"]
    assert patched_studio["transition"] == "wipe"
    assert patched_studio["timing_mode"] == "manual"
    assert patched_studio["manual_duration_ms"] == 45000
    new_etag = patch_resp.headers["ETag"]

    version_resp = slides_client.get(f"/api/v1/slides/presentations/{presentation_id}/versions/1")
    assert version_resp.status_code == 200
    version_studio = version_resp.json()["slides"][0]["metadata"]["studio"]
    assert version_studio["transition"] == "fade"
    assert version_studio["timing_mode"] == "auto"
    assert version_studio["manual_duration_ms"] is None

    restore_resp = slides_client.post(
        f"/api/v1/slides/presentations/{presentation_id}/versions/1/restore",
        headers={"If-Match": new_etag},
    )
    assert restore_resp.status_code == 200
    restored_studio = restore_resp.json()["slides"][0]["metadata"]["studio"]
    assert restored_studio["transition"] == "fade"
    assert restored_studio["timing_mode"] == "auto"
    assert restored_studio["manual_duration_ms"] is None

    export_resp = slides_client.get(f"/api/v1/slides/presentations/{presentation_id}/export?format=json")
    assert export_resp.status_code == 200
    exported_studio = export_resp.json()["slides"][0]["metadata"]["studio"]
    assert exported_studio["transition"] == "fade"
    assert exported_studio["timing_mode"] == "auto"
    assert exported_studio["manual_duration_ms"] is None

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
            "media_id": 1,
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
            "media_id": 1,
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
            "media_id": 1,
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
