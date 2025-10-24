"""Tests for character template helpers."""

from tldw_Server_API.app.core.Character_Chat.modules.character_templates import (
    get_character_template,
)


def test_get_character_template_returns_deep_copy():
    """Mutating one template instance must not affect subsequent calls."""
    original = get_character_template("assistant")
    assert original is not None
    assert "tags" in original

    original["tags"].append("mutated-tag")
    original.setdefault("extensions", {})["extra"] = "value"

    follow_up = get_character_template("assistant")
    assert follow_up is not None
    assert "mutated-tag" not in follow_up["tags"]
    assert "extra" not in (follow_up.get("extensions") or {})
    assert original is not follow_up
