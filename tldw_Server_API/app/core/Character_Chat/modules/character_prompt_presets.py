"""
Character prompt preset helpers.

Resolves per-character prompt preset metadata and formats
system prompts accordingly.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Character_Chat.modules.character_utils import (
    DEFAULT_CHARACTER_NAME,
    DEFAULT_USER_NAME,
    replace_placeholders,
)

DEFAULT_PROMPT_PRESET = "default"
ST_DEFAULT_PROMPT_PRESET = "st_default"

_VALID_PROMPT_PRESETS = {DEFAULT_PROMPT_PRESET, ST_DEFAULT_PROMPT_PRESET}


def _safe_replace(value: Any, char_name: str, user_name: str) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if not text:
        return ""
    try:
        return replace_placeholders(text, char_name, user_name)
    except Exception as exc:
        logger.debug("Preset placeholder replacement failed: {}", exc)
        return text


def resolve_character_prompt_preset(character: dict[str, Any]) -> str:
    extensions: Any = character.get("extensions") if character else None
    if isinstance(extensions, str):
        try:
            extensions = json.loads(extensions)
        except json.JSONDecodeError:
            extensions = {}

    preset_value: Any = None
    if isinstance(extensions, dict):
        tldw_ext = extensions.get("tldw")
        if isinstance(tldw_ext, dict):
            preset_value = tldw_ext.get("prompt_preset") or tldw_ext.get("promptPreset")
        if not preset_value:
            preset_value = extensions.get("prompt_preset") or extensions.get("promptPreset")

    if isinstance(preset_value, str):
        preset = preset_value.strip()
        if preset in _VALID_PROMPT_PRESETS:
            return preset
        if preset:
            logger.debug("Unknown character prompt preset '{}'; using default.", preset)

    return DEFAULT_PROMPT_PRESET


def build_character_system_prompt(
    character: dict[str, Any],
    char_name: str | None,
    user_name: str | None,
    preset: str | None = None,
) -> str:
    resolved_char = char_name or DEFAULT_CHARACTER_NAME
    resolved_user = user_name or DEFAULT_USER_NAME
    resolved_preset = preset or resolve_character_prompt_preset(character or {})

    if resolved_preset == ST_DEFAULT_PROMPT_PRESET:
        sections: list[str] = []
        sections.append(f"You are {resolved_char}.")

        system_prompt = _safe_replace(character.get("system_prompt"), resolved_char, resolved_user)
        if system_prompt:
            sections.append(system_prompt)

        description = _safe_replace(character.get("description"), resolved_char, resolved_user)
        if description:
            sections.append(f"Description:\n{description}")

        personality = _safe_replace(character.get("personality"), resolved_char, resolved_user)
        if personality:
            sections.append(f"Personality:\n{personality}")

        scenario = _safe_replace(character.get("scenario"), resolved_char, resolved_user)
        if scenario:
            sections.append(f"Scenario:\n{scenario}")

        message_example = _safe_replace(character.get("message_example"), resolved_char, resolved_user)
        if message_example:
            sections.append(f"Example dialogue:\n{message_example}")

        post_history = _safe_replace(character.get("post_history_instructions"), resolved_char, resolved_user)
        if post_history:
            sections.append(f"Post-history instructions:\n{post_history}")

        return "\n\n".join([s for s in sections if s]).strip()

    parts = [
        f"You are {resolved_char}.",
        _safe_replace(character.get("description"), resolved_char, resolved_user),
        _safe_replace(character.get("personality"), resolved_char, resolved_user),
        _safe_replace(character.get("scenario"), resolved_char, resolved_user),
        _safe_replace(character.get("system_prompt"), resolved_char, resolved_user),
    ]
    return "\n".join([p for p in parts if p]).strip()
