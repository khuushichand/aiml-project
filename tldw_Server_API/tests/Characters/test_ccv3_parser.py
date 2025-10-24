import json

import pytest

from tldw_Server_API.app.core.Character_Chat.ccv3_parser import validate_v3_card, parse_v3_card
from tldw_Server_API.app.core.Character_Chat.modules.character_io import import_character_card_from_json_string


def test_ccv3_validate_and_parse_happy_path():
    card = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            "name": "V3 Hero",
            "description": "A brave v3 hero",
            "personality": "Bold",
            "scenario": "Epic quest",
            "first_mes": "Greetings from v3!",
            "mes_example": "USER: Hi\nASSISTANT: Hello"
        }
    }
    ok, errs = validate_v3_card(card)
    assert ok and not errs

    parsed = parse_v3_card(card)
    assert parsed is not None
    assert parsed["name"] == "V3 Hero"
    assert parsed["first_message"].startswith("Greetings")

    # Through import dispatcher
    parsed2 = import_character_card_from_json_string(json.dumps(card))
    assert parsed2 is not None
    assert parsed2["name"] == "V3 Hero"


def test_ccv3_missing_required_fields_returns_none():
    card = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            "name": "No First Message",
            "description": "Missing first_mes"
        }
    }
    ok, errs = validate_v3_card(card)
    assert not ok
    assert any("first_mes" in e for e in errs)

    parsed = import_character_card_from_json_string(json.dumps(card))
    # Validation fails; importer should fall through and not produce a usable card
    assert parsed is None


@pytest.mark.parametrize("image_key", ["char_image", "image"])
def test_ccv3_parser_preserves_image_fields(image_key):
    sample_b64 = "aGVsbG8="
    card = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            "name": "ImageHero",
            "description": "Has an avatar",
            "personality": "Friendly",
            "scenario": "Testing",
            "first_mes": "Hello!",
            "mes_example": "User: Hi\nAssistant: Hello",
            image_key: sample_b64,
        },
    }

    parsed = parse_v3_card(card)
    assert parsed is not None
    assert parsed.get("image_base64") == sample_b64

    imported = import_character_card_from_json_string(json.dumps(card))
    assert imported is not None
    assert imported.get("image_base64") == sample_b64
