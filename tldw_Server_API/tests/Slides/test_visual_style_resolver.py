from tldw_Server_API.app.core.Slides.visual_style_resolver import resolve_builtin_visual_style


def test_resolver_returns_compact_snapshot_without_inline_css():
    resolved = resolve_builtin_visual_style("notebooklm-blueprint")

    assert resolved.snapshot["id"] == "notebooklm-blueprint"
    assert resolved.snapshot["resolution"]["base_theme"] == "night"
    assert resolved.snapshot["resolution"]["style_pack"] == "technical_grid"
    assert resolved.snapshot["resolution"]["style_pack_version"] == 1
    assert resolved.snapshot["resolution"]["token_overrides"]
    assert resolved.snapshot["resolution"]["resolved_settings"]
    assert "custom_css" not in resolved.snapshot
    assert "custom_css" not in resolved.snapshot["resolution"]

    assert resolved.appearance["theme"] == "night"
    assert resolved.appearance["settings"]
    assert resolved.appearance["custom_css"]


def test_resolver_uses_style_specific_token_overrides_for_hand_drawn_styles():
    chalkboard = resolve_builtin_visual_style("notebooklm-chalkboard")
    whiteboard = resolve_builtin_visual_style("notebooklm-whiteboard")
    sketch_noting = resolve_builtin_visual_style("notebooklm-sketch-noting")

    assert chalkboard is not None
    assert whiteboard is not None
    assert sketch_noting is not None

    assert chalkboard.snapshot["resolution"]["token_overrides"]["surface"] == "#0f172a"
    assert whiteboard.snapshot["resolution"]["token_overrides"]["surface"] == "#fdfdfb"
    assert sketch_noting.snapshot["resolution"]["token_overrides"]["surface"] == "#fffaf0"

    assert chalkboard.appearance["custom_css"] != whiteboard.appearance["custom_css"]
    assert chalkboard.appearance["custom_css"] != sketch_noting.appearance["custom_css"]
    assert whiteboard.appearance["custom_css"] != sketch_noting.appearance["custom_css"]
    assert chalkboard.appearance["theme"] == "black"
    assert whiteboard.appearance["theme"] == "white"
