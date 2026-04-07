from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.implementations.slides_module import SlidesModule


class _FakeSlidesDb:
    def __init__(self, presentation: SimpleNamespace) -> None:
        self._presentation = presentation
        self.closed = False

    def get_presentation_by_id(self, presentation_id: str):
        assert presentation_id == "pres-1"
        return self._presentation

    def close_connection(self) -> None:
        self.closed = True


def _build_presentation_row() -> SimpleNamespace:
    return SimpleNamespace(
        id="pres-1",
        title="Styled Deck",
        description=None,
        theme="night",
        marp_theme=None,
        template_id=None,
        settings=json.dumps({"controls": True}),
        studio_data=None,
        slides=json.dumps(
            [
                {
                    "order": 0,
                    "layout": "title",
                    "title": "Deck",
                    "content": "",
                    "speaker_notes": None,
                    "metadata": {},
                }
            ]
        ),
        slides_text="",
        source_type="manual",
        source_ref=None,
        source_query=None,
        custom_css=".reveal { color: red; }",
        visual_style_snapshot=json.dumps(
            {
                "id": "notebooklm-blueprint",
                "scope": "builtin",
                "name": "Blueprint",
                "resolution": {
                    "style_pack": "technical_grid",
                    "resolved_theme": "night",
                },
            }
        ),
        created_at="2026-03-29T00:00:00Z",
        last_modified="2026-03-29T00:00:00Z",
        deleted=False,
        client_id="test-client",
        version=1,
    )


@pytest.mark.parametrize(
    ("fmt", "export_path", "payload", "expected_mime_type"),
    [
        (
            "reveal",
            "tldw_Server_API.app.core.Slides.slides_export.export_presentation_bundle",
            b"PK\x03\x04stub",
            "application/zip",
        ),
        (
            "pdf",
            "tldw_Server_API.app.core.Slides.slides_export.export_presentation_pdf",
            b"%PDF-1.4\n%stub",
            "application/pdf",
        ),
    ],
)
def test_slides_module_export_passes_visual_style_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    fmt: str,
    export_path: str,
    payload: bytes,
    expected_mime_type: str,
) -> None:
    presentation = _build_presentation_row()
    fake_db = _FakeSlidesDb(presentation)
    module = SlidesModule(ModuleConfig(name="slides"))
    monkeypatch.setattr(module, "_open_db", lambda context: fake_db)

    captured: dict[str, object] = {}

    def _stub_export(**kwargs):
        captured["visual_style_snapshot"] = kwargs.get("visual_style_snapshot")
        return payload

    monkeypatch.setattr(export_path, _stub_export)

    result = module._export_presentation_sync(
        context=SimpleNamespace(),
        args={"presentation_id": "pres-1", "format": fmt},
    )

    assert captured["visual_style_snapshot"] == {
        "id": "notebooklm-blueprint",
        "scope": "builtin",
        "name": "Blueprint",
        "resolution": {
            "style_pack": "technical_grid",
            "resolved_theme": "night",
        },
    }
    assert result["mime_type"] == expected_mime_type
    assert base64.b64decode(result["content_base64"]) == payload
    assert result["success"] is True
    assert fake_db.closed is True
