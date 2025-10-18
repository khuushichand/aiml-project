"""Character helpers used by the chat module.

These functions provide a thin compatibility layer around the Character_Chat
package so the chat codebase can rely on the same storage and validation logic.
"""

from __future__ import annotations

import base64
import time
from typing import Any, Dict, List, Optional

from tldw_Server_API.app.core.Character_Chat.modules import character_db
from tldw_Server_API.app.core.Character_Chat.modules.character_utils import get_character_list_for_ui
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter, log_histogram
from tldw_Server_API.app.core.Utils.Utils import logging


_FIELD_ALIASES = {
    "description": ("description",),
    "personality": ("personality",),
    "scenario": ("scenario",),
    "system_prompt": ("system_prompt", "system"),
    "post_history_instructions": ("post_history_instructions", "post_history"),
    "first_message": ("first_message", "mes_example_greeting"),
    "message_example": ("message_example", "mes_example"),
    "creator_notes": ("creator_notes",),
    "alternate_greetings": ("alternate_greetings",),
    "tags": ("tags",),
    "creator": ("creator",),
    "character_version": ("character_version",),
    "extensions": ("extensions",),
}


def _extract_canonical_fields(character_data: Dict[str, Any]) -> Dict[str, Any]:
    """Translate incoming payload keys to the canonical DB field names."""
    canonical: Dict[str, Any] = {}

    if "name" in character_data:
        canonical["name"] = character_data["name"]

    for canonical_key, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if alias in character_data:
                canonical[canonical_key] = character_data[alias]
                break

    if "image_base64" in character_data:
        image_base64 = character_data["image_base64"]
        if isinstance(image_base64, str) and image_base64:
            canonical["image_base64"] = image_base64
        elif image_base64 in ("", None):
            canonical["image_base64"] = image_base64
    else:
        image_value = character_data.get("image")
        if isinstance(image_value, str) and image_value:
            # Preserve legacy behaviour: callers provide base64 data (optionally data URLs).
            canonical["image_base64"] = image_value.split(",", 1)[1] if "," in image_value else image_value

    return canonical


def save_character(
    db: CharactersRAGDB,
    character_data: Dict[str, Any],
    expected_version: Optional[int] = None,
) -> Optional[int]:
    """Create or update a character card via the shared Character_Chat helpers."""
    log_counter("save_character_attempt")
    start_time = time.time()

    char_name = character_data.get("name")
    if not char_name:
        logging.error("Character name is required to save.")
        return None

    canonical_payload = _extract_canonical_fields(character_data)

    try:
        existing_char = db.get_character_card_by_name(char_name)
        if existing_char:
            logging.info("Character '%s' found (ID: %s). Attempting update.", char_name, existing_char["id"])
            current_db_version = existing_char.get("version")
            if expected_version is not None and current_db_version != expected_version:
                logging.error(
                    "Version mismatch for character '%s'. Expected %s, DB has %s.",
                    char_name,
                    expected_version,
                    current_db_version,
                )
                raise ConflictError(
                    f"Version mismatch for character '{char_name}'. Expected {expected_version}, DB has {current_db_version}",
                    entity="character_cards",
                    entity_id=existing_char.get("id"),
                )

            update_payload = {key: value for key, value in canonical_payload.items() if key != "name"}
            if not update_payload:
                logging.info(
                    "No updatable fields provided for existing character '%s'. Skipping update, returning ID.",
                    char_name,
                )
                return existing_char.get("id")

            success = character_db.update_existing_character_details(
                db,
                existing_char["id"],
                update_payload,
                current_db_version,
            )
            if success:
                log_histogram("save_character_duration", time.time() - start_time)
                log_counter("save_character_success")
                return existing_char["id"]
            logging.error("Update helper reported failure for character '%s'.", char_name)
            log_counter("save_character_error_unspecified")
            return None

        logging.info("Character '%s' not found. Attempting to add new.", char_name)
        char_id = character_db.create_new_character_from_data(db, canonical_payload)
        if char_id:
            log_histogram("save_character_duration", time.time() - start_time)
            log_counter("save_character_success")
            return char_id

        logging.error("Character DB helper returned no ID while creating '%s'.", char_name)
        log_counter("save_character_error_unspecified")
        return None

    except ConflictError as conflict_error:
        log_counter("save_character_error_conflict", labels={"error": str(conflict_error)})
        logging.error("Conflict error saving character '%s': %s", char_name, conflict_error, exc_info=True)
        return None
    except InputError as input_error:
        log_counter("save_character_error_db", labels={"error": str(input_error)})
        logging.error("Input error saving character '%s': %s", char_name, input_error, exc_info=True)
        return None
    except CharactersRAGDBError as db_error:
        log_counter("save_character_error_db", labels={"error": str(db_error)})
        logging.error("Database error saving character '%s': %s", char_name, db_error, exc_info=True)
        return None
    except Exception as generic_error:  # pragma: no cover - defensive guard
        log_counter("save_character_error_generic", labels={"error": str(generic_error)})
        logging.error("Generic error saving character '%s': %s", char_name, generic_error, exc_info=True)
        return None


def load_characters(db: CharactersRAGDB) -> Dict[str, Dict[str, Any]]:
    """Return all character cards keyed by name with base64-encoded images."""
    log_counter("load_characters_attempt")
    start_time = time.time()
    characters_map: Dict[str, Dict[str, Any]] = {}

    try:
        all_cards = db.list_character_cards(limit=10_000)
        for card_dict in all_cards:
            char_name = card_dict.get("name")
            if not char_name:
                logging.warning(
                    "Character card found with no name (ID: %s). Skipping.",
                    card_dict.get("id"),
                )
                continue

            image_value = card_dict.get("image")
            if isinstance(image_value, (bytes, bytearray)):
                card_dict["image_base64"] = base64.b64encode(image_value).decode("utf-8")
            characters_map[char_name] = card_dict

        load_duration = time.time() - start_time
        log_histogram("load_characters_duration", load_duration)
        log_counter("load_characters_success", labels={"character_count": len(characters_map)})
        logging.info("Loaded %s characters from DB.", len(characters_map))
        return characters_map

    except CharactersRAGDBError as db_error:
        log_counter("load_characters_error_db", labels={"error": str(db_error)})
        logging.error("Database error loading characters: %s", db_error, exc_info=True)
        return {}
    except Exception as generic_error:  # pragma: no cover - defensive guard
        log_counter("load_characters_error_generic", labels={"error": str(generic_error)})
        logging.error("Generic error loading characters: %s", generic_error, exc_info=True)
        return {}


def get_character_names(db: CharactersRAGDB) -> List[str]:
    """Return a sorted list of character names."""
    log_counter("get_character_names_attempt")
    start_time = time.time()

    try:
        names = [entry["name"] for entry in get_character_list_for_ui(db) if entry.get("name")]
        names.sort()

        log_histogram("get_character_names_duration", time.time() - start_time)
        log_counter("get_character_names_success", labels={"name_count": len(names)})
        return names
    except CharactersRAGDBError as db_error:
        log_counter("get_character_names_error_db", labels={"error": str(db_error)})
        logging.error("Database error getting character names: %s", db_error, exc_info=True)
        return []
    except Exception as generic_error:  # pragma: no cover - defensive guard
        log_counter("get_character_names_error_generic", labels={"error": str(generic_error)})
        logging.error("Generic error getting character names: %s", generic_error, exc_info=True)
        return []
