import pytest

from tldw_Server_API.app.core.Slides.visual_style_packs import (
    _load_pack_css,
    render_pack_custom_css,
)


@pytest.mark.unit
def test_load_pack_css_rejects_path_traversal(monkeypatch, tmp_path):
    packs_dir = tmp_path / "style_packs"
    packs_dir.mkdir()
    (tmp_path / "secret.css").write_text("body { color: red; }", encoding="utf-8")
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Slides.visual_style_packs._STYLE_PACKS_DIR",
        packs_dir,
    )
    _load_pack_css.cache_clear()

    try:
        assert _load_pack_css("../secret") == ""
    finally:
        _load_pack_css.cache_clear()


@pytest.mark.unit
def test_render_pack_custom_css_omits_unsafe_token_entries():
    css = render_pack_custom_css(
        style_id="notebooklm-blueprint",
        pack_id="technical_grid",
        token_overrides={
            "accent": "#7dd3fc",
            "safe_value": "rgba(125, 211, 252, 0.16)",
            "surface; color:red": "#ffffff",
            "glow": "#67e8f9;\nbackground:url(https://example.com)",
        },
    )

    assert "--accent: #7dd3fc;" in css
    assert "--safe-value: rgba(125, 211, 252, 0.16);" in css
    assert "--surface;" not in css
    assert "background:url(" not in css
    assert "https://example.com" not in css
