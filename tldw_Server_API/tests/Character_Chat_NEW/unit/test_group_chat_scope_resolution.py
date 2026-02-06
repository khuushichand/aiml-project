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


@pytest.mark.unit
def test_author_note_gm_only_excludes_from_prompt():
    """authorNoteGmOnly=True should suppress note for prompt injection."""
    settings = {"authorNote": "secret GM note", "authorNoteGmOnly": True}
    character = {"id": 1}

    assert sessions._resolve_author_note_text(settings, character, for_prompt=True) == ""


@pytest.mark.unit
def test_author_note_gm_only_still_available_for_ui():
    """authorNoteGmOnly=True should still return note text for UI display."""
    settings = {"authorNote": "secret GM note", "authorNoteGmOnly": True}
    character = {"id": 1}

    resolved = sessions._resolve_author_note_text(settings, character, for_prompt=False)
    assert resolved == "secret GM note"


@pytest.mark.unit
def test_author_note_exclude_from_prompt_still_available_for_ui():
    """authorNoteExcludeFromPrompt=True should still return note for UI."""
    settings = {"authorNote": "hidden note", "authorNoteExcludeFromPrompt": True}
    character = {"id": 1}

    assert sessions._resolve_author_note_text(settings, character, for_prompt=True) == ""
    assert sessions._resolve_author_note_text(settings, character, for_prompt=False) == "hidden note"


@pytest.mark.unit
def test_author_note_disabled_hides_from_both():
    """authorNoteEnabled=False should hide from both prompt and UI."""
    settings = {"authorNote": "disabled note", "authorNoteEnabled": False}
    character = {"id": 1}

    assert sessions._resolve_author_note_text(settings, character, for_prompt=True) == ""
    assert sessions._resolve_author_note_text(settings, character, for_prompt=False) == ""


# --- Greeting Staleness Detection ---


@pytest.mark.unit
def test_compute_greetings_checksum_deterministic():
    """Checksum should be stable for same greetings."""
    char = {"first_message": "Hello!", "alternate_greetings": ["Hi!", "Hey!"]}
    c1 = sessions._compute_greetings_checksum(char)
    c2 = sessions._compute_greetings_checksum(char)
    assert c1 == c2
    assert len(c1) == 16  # truncated hex


@pytest.mark.unit
def test_compute_greetings_checksum_changes_on_edit():
    """Checksum should differ when greetings change."""
    char_v1 = {"first_message": "Hello!"}
    char_v2 = {"first_message": "Hello! Updated."}
    assert sessions._compute_greetings_checksum(char_v1) != sessions._compute_greetings_checksum(char_v2)


@pytest.mark.unit
def test_check_greeting_staleness_no_checksum():
    """No warning when chat has no stored checksum (pre-existing chat)."""
    settings = {}
    character = {"first_message": "Hello!"}
    assert sessions._check_greeting_staleness(settings, character) is None


@pytest.mark.unit
def test_check_greeting_staleness_matching():
    """No warning when checksum matches."""
    character = {"first_message": "Hello!"}
    checksum = sessions._compute_greetings_checksum(character)
    settings = {"greetingsChecksum": checksum}
    assert sessions._check_greeting_staleness(settings, character) is None


@pytest.mark.unit
def test_check_greeting_staleness_mismatch():
    """Warning returned when greetings have changed."""
    char_original = {"first_message": "Hello!"}
    checksum = sessions._compute_greetings_checksum(char_original)
    settings = {"greetingsChecksum": checksum}
    char_modified = {"first_message": "Hello! I changed."}
    warning = sessions._check_greeting_staleness(settings, char_modified)
    assert warning is not None
    assert "stale" in warning.lower()


@pytest.mark.unit
def test_greeting_scope_chat_injects_once_for_conversation():
    settings = {"greetingEnabled": True, "greetingScope": "chat"}
    turn_context = {
        "participants": [{"id": 1}, {"id": 2}],
        "primary_character_name": "Alpha",
        "active_character_name": "Beta",
        "participant_aliases": {"alpha", "beta"},
    }
    assert (
        sessions._should_inject_character_scoped_greeting(
            settings=settings,
            turn_context=turn_context,
            history_messages=[],
        )
        is True
    )
    assert (
        sessions._should_inject_character_scoped_greeting(
            settings=settings,
            turn_context=turn_context,
            history_messages=[{"sender": "Alpha", "content": "hello"}],
        )
        is False
    )


@pytest.mark.unit
def test_greeting_scope_character_injects_per_character_first_reply():
    settings = {"greetingEnabled": True, "greetingScope": "character"}
    turn_context = {
        "participants": [{"id": 1}, {"id": 2}],
        "primary_character_name": "Alpha",
        "active_character_name": "Beta",
        "participant_aliases": {"alpha", "beta"},
    }
    assert (
        sessions._should_inject_character_scoped_greeting(
            settings=settings,
            turn_context=turn_context,
            history_messages=[{"sender": "Alpha", "content": "hello"}],
        )
        is True
    )


# --- Per-Chat Preset Overrides ---


@pytest.mark.unit
def test_effective_prompt_preset_defaults_to_character():
    """Without chat override, falls back to character preset."""
    settings = {}
    character = {}  # no extensions -> default preset
    assert sessions._resolve_effective_prompt_preset(settings, character) == "default"


@pytest.mark.unit
def test_effective_prompt_preset_chat_override():
    """When preset scope is chat, chat override applies."""
    settings = {"chatPresetOverrideId": "st_default", "presetScope": "chat"}
    character = {}
    assert sessions._resolve_effective_prompt_preset(settings, character) == "st_default"


@pytest.mark.unit
def test_effective_prompt_preset_invalid_chat_override_falls_back():
    """Invalid chat preset falls back to global default in chat scope."""
    settings = {"chatPresetOverrideId": "nonexistent", "presetScope": "chat"}
    character = {}
    assert sessions._resolve_effective_prompt_preset(settings, character) == "default"


@pytest.mark.unit
def test_effective_prompt_preset_character_scope_ignores_chat_override():
    settings = {"chatPresetOverrideId": "st_default", "presetScope": "character"}
    character = {"extensions": {"tldw": {"prompt_preset": "default"}}}
    assert sessions._resolve_effective_prompt_preset(settings, character) == "default"


@pytest.mark.unit
def test_effective_generation_settings_no_override():
    """Without overrides, returns character generation settings."""
    settings = {}
    character = {"extensions": {"tldw": {"generation": {"temperature": 0.7}}}}
    result = sessions._resolve_effective_generation_settings(settings, character)
    assert result.get("temperature") == 0.7


@pytest.mark.unit
def test_effective_generation_settings_chat_override():
    """Chat generationOverrides take precedence over character settings."""
    settings = {"generationOverrides": {"temperature": 1.5}}
    character = {"extensions": {"tldw": {"generation": {"temperature": 0.7}}}}
    result = sessions._resolve_effective_generation_settings(settings, character)
    assert result["temperature"] == 1.5


@pytest.mark.unit
def test_effective_generation_settings_chat_generation_override_preferred():
    settings = {
        "chatGenerationOverride": {"temperature": 1.1},
        "generationOverrides": {"temperature": 1.5},
    }
    character = {"extensions": {"tldw": {"generation": {"temperature": 0.7}}}}
    result = sessions._resolve_effective_generation_settings(settings, character)
    assert result["temperature"] == 1.1


@pytest.mark.unit
def test_effective_generation_settings_disabled_chat_override_is_ignored():
    settings = {"chatGenerationOverride": {"enabled": False, "temperature": 1.2}}
    character = {"extensions": {"tldw": {"generation": {"temperature": 0.7}}}}
    result = sessions._resolve_effective_generation_settings(settings, character)
    assert result["temperature"] == 0.7


@pytest.mark.unit
def test_effective_generation_settings_partial_override():
    """Partial overrides only replace specified keys."""
    settings = {"generationOverrides": {"top_p": 0.5}}
    character = {"extensions": {"tldw": {"generation": {"temperature": 0.7, "top_p": 0.9}}}}
    result = sessions._resolve_effective_generation_settings(settings, character)
    assert result["temperature"] == 0.7
    assert result["top_p"] == 0.5
