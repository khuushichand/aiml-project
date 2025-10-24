"""
Character Card V3 parser and validator (minimal, spec-aligned).

Supports cards with:
- spec: "chara_card_v3"
- spec_version: e.g., "3.0"
- data: { name, description, personality, scenario, first_mes, mes_example, ... }

Maps to DB schema fields consistent with V1/V2 parsers.
"""

from typing import Any, Dict, Optional, Tuple
from loguru import logger


def validate_v3_card(card_data: Dict[str, Any]) -> Tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        # Top-level spec markers are helpful but not mandatory for leniency
        data = card_data.get("data", card_data)
        if not isinstance(data, dict):
            errors.append("'data' node must be a dictionary for v3")
            return False, errors
        # Required core fields for successful mapping
        for f in ["name", "description", "first_mes"]:
            if f not in data or data[f] is None:
                errors.append(f"Missing required field '{f}' in v3 data")
        return (len(errors) == 0), errors
    except Exception as e:
        logger.error(f"Unexpected error validating v3 card: {e}")
        return False, [str(e)]


def parse_v3_card(card_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        data = card_data.get("data", card_data)
        if not isinstance(data, dict):
            return None
        parsed = {
            "name": data.get("name"),
            "description": data.get("description", ""),
            "personality": data.get("personality", ""),
            "scenario": data.get("scenario", ""),
            "first_message": data.get("first_mes", ""),
            "message_example": data.get("mes_example", ""),
            "creator_notes": data.get("creator_notes", ""),
            "system_prompt": data.get("system_prompt", ""),
            "post_history_instructions": data.get("post_history_instructions", ""),
            "alternate_greetings": data.get("alternate_greetings", []),
            "tags": data.get("tags", []),
            "creator": data.get("creator", ""),
            "character_version": data.get("character_version", ""),
            "extensions": data.get("extensions", {}) or {},
        }
        image_value = data.get("char_image") or data.get("image")
        if image_value is not None:
            parsed["image_base64"] = image_value
        if not parsed["name"]:
            return None
        return parsed
    except Exception as e:
        logger.error(f"Error parsing v3 card: {e}")
        return None


__all__ = ["validate_v3_card", "parse_v3_card"]
