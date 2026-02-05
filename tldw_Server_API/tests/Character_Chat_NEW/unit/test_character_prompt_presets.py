from tldw_Server_API.app.core.Character_Chat.modules.character_prompt_presets import (
    DEFAULT_PROMPT_PRESET,
    ST_DEFAULT_PROMPT_PRESET,
    build_character_system_prompt,
    resolve_character_prompt_preset,
)


def test_resolve_prompt_preset_from_extensions():
    character = {
        "extensions": {
            "tldw": {"prompt_preset": ST_DEFAULT_PROMPT_PRESET}
        }
    }
    assert resolve_character_prompt_preset(character) == ST_DEFAULT_PROMPT_PRESET


def test_build_prompt_uses_st_sections():
    character = {
        "name": "Ava",
        "description": "An expert guide.",
        "personality": "Warm and direct.",
        "scenario": "Helping a user.",
        "system_prompt": "Stay concise.",
        "message_example": "User: Hi\nAva: Hello!",
        "post_history_instructions": "Ask one follow-up question.",
        "extensions": {
            "tldw": {"prompt_preset": ST_DEFAULT_PROMPT_PRESET}
        }
    }
    prompt = build_character_system_prompt(character, "Ava", "User")
    assert "Example dialogue" in prompt
    assert "Post-history instructions" in prompt


def test_build_prompt_default_excludes_st_sections():
    character = {
        "name": "Ava",
        "description": "An expert guide.",
        "personality": "Warm and direct.",
        "scenario": "Helping a user.",
        "system_prompt": "Stay concise.",
        "message_example": "User: Hi\nAva: Hello!",
        "post_history_instructions": "Ask one follow-up question.",
        "extensions": {
            "tldw": {"prompt_preset": DEFAULT_PROMPT_PRESET}
        }
    }
    prompt = build_character_system_prompt(character, "Ava", "User")
    assert "Example dialogue" not in prompt
    assert "Post-history instructions" not in prompt
