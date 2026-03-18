import io
import zipfile

import pytest

from tldw_Server_API.app.core.Slides.slides_export import (
    SlidesAssetsMissingError,
    SlidesExportInputError,
    _normalize_pdf_options,
    export_presentation_bundle,
    export_presentation_markdown,
)

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


def test_export_bundle_includes_assets(tmp_path):
    assets_dir = _build_assets(tmp_path)
    slides = [
        {
            "order": 0,
            "layout": "title",
            "title": "Deck",
            "content": "",
            "speaker_notes": None,
            "metadata": {},
        },
        {
            "order": 1,
            "layout": "content",
            "title": "Slide",
            "content": "Hello",
            "speaker_notes": "Notes",
            "metadata": {
                "images": [
                    {
                        "mime": "image/png",
                        "data_b64": _SAMPLE_PNG_B64,
                        "alt": "Logo",
                        "width": 64,
                        "height": 64,
                    }
                ]
            },
        },
    ]
    bundle = export_presentation_bundle(
        title="Deck",
        slides=slides,
        theme="black",
        settings={"controls": True},
        custom_css=".reveal { color: red; }",
        assets_dir=assets_dir,
    )
    with zipfile.ZipFile(io.BytesIO(bundle)) as zf:
        names = set(zf.namelist())
        assert "index.html" in names
        assert "assets/reveal/reveal.js" in names
        assert "assets/reveal/reveal.css" in names
        assert "assets/reveal/theme/black.css" in names
        assert "assets/reveal/plugin/notes/notes.js" in names
        assert "LICENSE.revealjs.txt" in names
        assert "assets/custom.css" in names
        index_html = zf.read("index.html").decode("utf-8")
        assert "assets/custom.css" in index_html
        assert "data:image/png;base64," in index_html
        assert "alt=\"Logo\"" in index_html


def test_export_bundle_missing_assets(tmp_path):
    assets_dir = tmp_path / "missing"
    assets_dir.mkdir()
    with pytest.raises(SlidesAssetsMissingError):
        export_presentation_bundle(
            title="Deck",
            slides=[],
            theme="black",
            settings=None,
            custom_css=None,
            assets_dir=assets_dir,
        )


def test_export_bundle_blocks_custom_css_url(tmp_path):
    assets_dir = _build_assets(tmp_path)
    with pytest.raises(SlidesExportInputError):
        export_presentation_bundle(
            title="Deck",
            slides=[],
            theme="black",
            settings=None,
            custom_css="@import url('https://example.com')",
            assets_dir=assets_dir,
        )


def test_export_markdown_theme_mapping():
    slides = [
        {"order": 0, "layout": "title", "title": "Deck", "content": "", "speaker_notes": None, "metadata": {}},
    ]
    md = export_presentation_markdown(title="Deck", slides=slides, theme="black")
    assert "marp: true" in md
    assert "theme: default" in md


def test_export_markdown_marp_override():
    slides = [
        {"order": 0, "layout": "title", "title": "Deck", "content": "", "speaker_notes": None, "metadata": {}},
    ]
    md = export_presentation_markdown(title="Deck", slides=slides, theme="black", marp_theme="gaia")
    assert "theme: gaia" in md


def test_export_markdown_includes_images():
    slides = [
        {
            "order": 0,
            "layout": "content",
            "title": "Slide",
            "content": "Hello",
            "speaker_notes": None,
            "metadata": {
                "images": [
                    {
                        "mime": "image/png",
                        "data_b64": _SAMPLE_PNG_B64,
                        "alt": "Logo",
                    }
                ]
            },
        },
    ]
    md = export_presentation_markdown(title="Deck", slides=slides, theme="black")
    assert "![Logo](data:image/png;base64," in md


def test_export_markdown_preserves_text_fallback_for_visual_blocks():
    slides = [
        {
            "order": 0,
            "layout": "content",
            "title": "Timeline",
            "content": "- 1776: Declaration - American independence declared",
            "speaker_notes": None,
            "metadata": {
                "visual_blocks": [
                    {
                        "type": "timeline",
                        "items": [
                            {
                                "label": "1776",
                                "title": "Declaration",
                                "description": "American independence declared",
                            }
                        ],
                    }
                ]
            },
        }
    ]

    md = export_presentation_markdown(title="Deck", slides=slides, theme="black")

    assert "1776" in md
    assert "American independence declared" in md


def test_export_bundle_resolves_output_asset_ref(tmp_path, monkeypatch):
    assets_dir = _build_assets(tmp_path)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.slides_export.resolve_slide_asset",
        lambda asset_ref, **kwargs: {
            "asset_ref": asset_ref,
            "mime": "image/png",
            "data_b64": _SAMPLE_PNG_B64,
            "alt": "Cover",
        },
    )
    slides = [
        {
            "order": 0,
            "layout": "content",
            "title": "Slide",
            "content": "Hello",
            "speaker_notes": None,
            "metadata": {"images": [{"asset_ref": "output:123", "alt": "Cover"}]},
        },
    ]

    bundle = export_presentation_bundle(
        title="Deck",
        slides=slides,
        theme="black",
        settings=None,
        custom_css=None,
        assets_dir=assets_dir,
    )

    with zipfile.ZipFile(io.BytesIO(bundle)) as zf:
        index_html = zf.read("index.html").decode("utf-8")
        assert "data:image/png;base64," in index_html
        assert "alt=\"Cover\"" in index_html


def test_export_markdown_resolves_output_asset_ref(monkeypatch):
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.slides_export.resolve_slide_asset",
        lambda asset_ref, **kwargs: {
            "asset_ref": asset_ref,
            "mime": "image/png",
            "data_b64": _SAMPLE_PNG_B64,
            "alt": "Cover",
        },
    )
    slides = [
        {
            "order": 0,
            "layout": "content",
            "title": "Slide",
            "content": "Hello",
            "speaker_notes": "Narration",
            "metadata": {"images": [{"asset_ref": "output:123", "alt": "Cover"}]},
        }
    ]

    md = export_presentation_markdown(title="Deck", slides=slides, theme="black")

    assert "![Cover](data:image/png;base64," in md


def test_export_markdown_rejects_invalid_image():
    slides = [
        {
            "order": 0,
            "layout": "content",
            "title": "Slide",
            "content": "Hello",
            "speaker_notes": None,
            "metadata": {"images": [{"mime": "image/png", "data_b64": "not-base64"}]},
        },
    ]
    with pytest.raises(SlidesExportInputError):
        export_presentation_markdown(title="Deck", slides=slides, theme="black")


def test_normalize_pdf_options_requires_width_height():
    with pytest.raises(SlidesExportInputError):
        _normalize_pdf_options({"width": "10in"})


def test_normalize_pdf_options_rejects_invalid_format():
    with pytest.raises(SlidesExportInputError):
        _normalize_pdf_options({"format": "!!bad!!"})
