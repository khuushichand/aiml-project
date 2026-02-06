import pytest

from tldw_Server_API.app.api.v1.endpoints import character_chat_sessions as sessions


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw_scope", "expected"),
    [
        ("chat", "chat"),
        ("character", "character"),
        ("CHARACTER", "character"),
        ("invalid", "chat"),
        ("", "chat"),
        (None, "chat"),
    ],
)
def test_normalize_greeting_scope_defaults(raw_scope, expected):
    assert (
        sessions._normalize_greeting_scope({"greetingScope": raw_scope})
        == expected
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw_scope", "expected"),
    [
        ("chat", "chat"),
        ("character", "character"),
        ("CHARACTER", "character"),
        ("invalid", "character"),
        ("", "character"),
        (None, "character"),
    ],
)
def test_normalize_preset_scope_defaults(raw_scope, expected):
    assert sessions._normalize_preset_scope({"presetScope": raw_scope}) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw_scope", "expected"),
    [
        ("shared", "shared"),
        ("character", "character"),
        ("both", "both"),
        ("BOTH", "both"),
        ("invalid", "shared"),
        ("", "shared"),
        (None, "shared"),
    ],
)
def test_normalize_memory_scope_defaults(raw_scope, expected):
    assert sessions._normalize_memory_scope({"memoryScope": raw_scope}) == expected


@pytest.mark.unit
def test_resolve_author_note_text_invalid_memory_scope_falls_back_to_shared():
    settings = {
        "authorNote": "shared-note",
        "memoryScope": "not-a-valid-scope",
        "characterMemoryById": {"12": {"note": "character-note"}},
    }
    character = {"id": 12}

    resolved = sessions._resolve_author_note_text(settings, character)
    assert resolved == "shared-note"
