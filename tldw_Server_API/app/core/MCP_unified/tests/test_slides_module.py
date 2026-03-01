import base64
import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.implementations.slides_module import SlidesModule
from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig


@dataclass
class FakeRow:
    id: str
    title: str
    description: str | None
    theme: str
    marp_theme: str | None
    template_id: str | None
    settings: str | None
    slides: str
    slides_text: str
    source_type: str | None
    source_ref: str | None
    source_query: str | None
    custom_css: str | None
    created_at: str
    last_modified: str
    deleted: int
    client_id: str
    version: int


class FakeSlidesDB:
    def __init__(self) -> None:
        self.rows: Dict[str, FakeRow] = {}
        self._counter = 0

    def create_presentation(self, presentation_id, title, description, theme, marp_theme, template_id, settings, slides, slides_text, source_type, source_ref, source_query, custom_css):
        self._counter += 1
        pid = presentation_id or f"pres-{self._counter}"
        row = FakeRow(
            id=pid,
            title=title,
            description=description,
            theme=theme,
            marp_theme=marp_theme,
            template_id=template_id,
            settings=settings,
            slides=slides,
            slides_text=slides_text,
            source_type=source_type,
            source_ref=source_ref,
            source_query=source_query,
            custom_css=custom_css,
            created_at="now",
            last_modified="now",
            deleted=0,
            client_id="test",
            version=1,
        )
        self.rows[pid] = row
        return row

    def list_presentations(self, limit, offset, include_deleted, sort_column, sort_direction) -> Tuple[List[FakeRow], int]:
        items = list(self.rows.values())
        return items[offset: offset + limit], len(items)

    def search_presentations(self, query, limit, offset, include_deleted):
        items = list(self.rows.values())
        return items[offset: offset + limit], len(items)

    def get_presentation_by_id(self, presentation_id, include_deleted=False):
        row = self.rows.get(presentation_id)
        if not row:
            raise KeyError("presentation_not_found")
        return row

    def update_presentation(self, presentation_id, update_fields, expected_version, operation=None):
        row = self.get_presentation_by_id(presentation_id, include_deleted=True)
        for k, v in update_fields.items():
            setattr(row, k, v)
        row.version += 1
        return row

    def list_presentation_versions(self, presentation_id, limit, offset):
        return [], 0

    def get_presentation_version(self, presentation_id, version):
        raise KeyError("presentation_version_not_found")

    def soft_delete_presentation(self, presentation_id, expected_version):
        row = self.get_presentation_by_id(presentation_id, include_deleted=True)
        row.deleted = 1
        row.version += 1
        return row

    def restore_presentation(self, presentation_id, expected_version):
        row = self.get_presentation_by_id(presentation_id, include_deleted=True)
        row.deleted = 0
        row.version += 1
        return row

    def close_connection(self):
        return None


class FakeGenerator:
    def generate_from_text(self, source_text, title_hint=None, provider=None, model=None, api_key=None, temperature=0.7, max_tokens=4000, max_source_tokens=None, max_source_chars=None, enable_chunking=True, chunk_size_tokens=1000, summary_tokens=200):
        return {"title": title_hint or "Generated", "slides": [{"order": 0, "title": "Slide", "content": "Content"}]}


@pytest.mark.asyncio
async def test_slides_templates_export_and_rag(monkeypatch, tmp_path):
    mod = SlidesModule(ModuleConfig(name="slides"))
    fake_db = FakeSlidesDB()
    mod._open_db = lambda ctx: fake_db  # type: ignore[attr-defined]

    ctx = SimpleNamespace(
        db_paths={"media": str(tmp_path / "media.db"), "chacha": str(tmp_path / "chacha.db")},
        user_id="1",
    )

    created = await mod.execute_tool(
        "slides.presentations.create",
        {"title": "Deck", "slides": json.dumps({"slides": [{"order": 0, "title": "T", "content": "C"}]})},
        context=ctx,
    )
    pres_id = created["presentation_id"]

    templates = await mod.execute_tool("slides.templates.list", {}, context=ctx)
    template_ids = {t["id"] for t in templates["templates"]}
    assert "academic" in template_ids

    template = await mod.execute_tool("slides.templates.get", {"template_id": "academic"}, context=ctx)
    assert template["template"]["id"] == "academic"

    from tldw_Server_API.app.core.Slides import slides_export
    monkeypatch.setattr(slides_export, "export_presentation_bundle", lambda **_kwargs: b"zip")
    monkeypatch.setattr(slides_export, "export_presentation_pdf", lambda **_kwargs: b"pdf")

    exported = await mod.execute_tool("slides.export", {"presentation_id": pres_id, "format": "reveal"}, context=ctx)
    assert base64.b64decode(exported["content_base64"]) == b"zip"

    exported_pdf = await mod.execute_tool("slides.export", {"presentation_id": pres_id, "format": "pdf"}, context=ctx)
    assert base64.b64decode(exported_pdf["content_base64"]) == b"pdf"

    async def _fake_rag_pipeline(**kwargs):
        doc = SimpleNamespace(metadata={"title": "Doc"}, content="RAG content")
        return SimpleNamespace(documents=[doc], generated_answer=None)

    import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as rag_pipeline
    monkeypatch.setattr(rag_pipeline, "unified_rag_pipeline", _fake_rag_pipeline)
    mod._get_generator = lambda: FakeGenerator()  # type: ignore[attr-defined]

    rag_out = await mod.execute_tool(
        "slides.generate.from_rag",
        {"query": "test", "top_k": 1},
        context=ctx,
    )
    assert rag_out["success"] is True
