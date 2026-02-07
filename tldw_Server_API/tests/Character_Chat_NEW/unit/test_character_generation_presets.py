from tldw_Server_API.app.core.Character_Chat.modules.character_generation_presets import (
    resolve_character_generation_settings,
)


def test_resolve_generation_settings_from_tldw_generation_block():
    character = {
        "extensions": {
            "tldw": {
                "generation": {
                    "temperature": "0.75",
                    "top_p": "0.92",
                    "repetition_penalty": "1.1",
                    "stop": ["END", " STOP "],
                }
            }
        }
    }

    settings = resolve_character_generation_settings(character)
    assert settings == {
        "temperature": 0.75,
        "top_p": 0.92,
        "repetition_penalty": 1.1,
        "stop": ["END", "STOP"],
    }


def test_resolve_generation_settings_falls_back_when_primary_values_invalid():
    character = {
        "temperature": 0.5,
        "extensions": {
            "tldw": {
                "generation": {
                    "temperature": "9.9",
                    "top_p": "invalid",
                    "repetition_penalty": -1,
                    "stop": ["", "   "],
                }
            },
            "top_p": "0.3",
            "stop": "###\nEND",
        },
    }

    settings = resolve_character_generation_settings(character)
    assert settings["temperature"] == 0.5
    assert settings["top_p"] == 0.3
    assert "repetition_penalty" not in settings
    assert settings["stop"] == ["###", "END"]

