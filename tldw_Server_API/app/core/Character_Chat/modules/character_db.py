"""
Character database operations module.

This module contains functions for CRUD operations on character data and UI
helpers for loading characters and their associated assets.
"""

import base64
import binascii
import io
import json
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image
from loguru import logger

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)

from .character_utils import (
    extract_character_id_from_ui_choice,
    replace_placeholders,
)


def _prepare_character_data_for_db_storage(
    input_data: Dict[str, Any],
    is_update: bool = False,
) -> Dict[str, Any]:
    """
    Prepares character data (from a dictionary, often derived from a Pydantic model)
    for DB insertion/update. Handles 'image_base64' to bytes conversion and ensures
    list/dict fields are properly materialised.
    """

    db_data = input_data.copy()

    for key in (
        "name",
        "description",
        "personality",
        "scenario",
        "system_prompt",
        "post_history_instructions",
        "first_message",
        "message_example",
        "creator_notes",
        "creator",
        "character_version",
    ):
        if key in db_data:
            val = db_data[key]
            if isinstance(val, tuple):
                try:
                    db_data[key] = val[0] if val else ""
                except Exception:
                    db_data[key] = str(val)
            elif not isinstance(val, (str, type(None))):
                db_data[key] = str(val)

    if "image_base64" in db_data:
        base64_str = db_data.pop("image_base64")
        if base64_str and isinstance(base64_str, str):
            try:
                if "," in base64_str and base64_str.startswith("data:image"):
                    base64_str = base64_str.split(",", 1)[1]
                base64_str_clean = "".join(str(base64_str).split())
                if not base64_str_clean:
                    raise ValueError("image_base64 data is empty after removing whitespace.")
                image_bytes = base64.b64decode(base64_str_clean, validate=True)

                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    has_alpha = "A" in img.getbands()
                    if has_alpha and img.mode != "RGBA":
                        img = img.convert("RGBA")
                    elif not has_alpha and img.mode not in ["RGB", "L"]:
                        img = img.convert("RGB")

                    max_size = (512, 768)
                    if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                        img.thumbnail(max_size, Image.Resampling.LANCZOS)
                        logger.info(
                            "Resized character image from %s to fit within %s",
                            img.size,
                            max_size,
                        )

                    output = io.BytesIO()
                    img.save(
                        output,
                        format="WEBP",
                        quality=85,
                        method=6,
                        optimize=True,
                    )
                    db_data["image"] = output.getvalue()
                    logger.info(
                        "Optimized character image: %s -> %s bytes",
                        len(image_bytes),
                        len(db_data["image"]),
                    )
                except Exception as img_err:
                    logger.warning("Could not optimise image, using original bytes: {}", img_err)
                    db_data["image"] = image_bytes
            except (binascii.Error, ValueError) as exc:
                logger.error("Invalid image_base64 data for character: {}", exc)
                raise InputError(f"Invalid image_base64 data: {exc}")
        else:
            db_data["image"] = None
    elif not is_update and "image" not in db_data:
        db_data["image"] = None

    for field_name in ["alternate_greetings", "tags"]:
        if field_name in db_data and isinstance(db_data[field_name], str):
            try:
                db_data[field_name] = json.loads(db_data[field_name])
                if not isinstance(db_data[field_name], list):
                    logger.warning(
                        "Field '%s' was a JSON string but not a list. Resetting to empty list.",
                        field_name,
                    )
                    db_data[field_name] = []
            except json.JSONDecodeError:
                logger.warning(
                    "Field '%s' is not valid JSON string. Defaulting to empty list.",
                    field_name,
                )
                db_data[field_name] = []
        elif field_name in db_data and db_data[field_name] is None:
            db_data[field_name] = []

    if "extensions" in db_data and isinstance(db_data["extensions"], str):
        try:
            db_data["extensions"] = json.loads(db_data["extensions"])
            if not isinstance(db_data["extensions"], dict):
                logger.warning(
                    "Field 'extensions' was a JSON string but not a dict. Resetting to empty dict."
                )
                db_data["extensions"] = {}
        except json.JSONDecodeError:
            logger.warning("Field 'extensions' is not valid JSON string. Resetting to empty dict.")
            db_data["extensions"] = {}
    elif "extensions" in db_data and db_data["extensions"] is None:
        db_data["extensions"] = {}

    return db_data


def create_new_character_from_data(db: CharactersRAGDB, character_payload: Dict[str, Any]) -> Optional[int]:
    """Create a new character in the database from a dictionary payload."""

    try:
        if "name" not in character_payload or not character_payload["name"]:
            raise InputError("Character 'name' is required and cannot be empty.")

        existing_char = db.get_character_card_by_name(character_payload["name"])
        if existing_char:
            raise ConflictError(
                f"Character with name '{character_payload['name']}' already exists (ID: {existing_char['id']})."
            )

        db_ready_data = _prepare_character_data_for_db_storage(character_payload, is_update=False)
        char_id = db.add_character_card(db_ready_data)
        if char_id:
            logger.info("Character '{}' created with ID: {}", db_ready_data["name"], char_id)
        return char_id
    except (InputError, ConflictError) as exc:
        logger.error("Error creating new character: {}", exc)
        raise
    except CharactersRAGDBError as exc:
        logger.error("Database error creating character: {}", exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error creating character: {}", exc, exc_info=True)
        raise CharactersRAGDBError(f"Unexpected error creating character: {exc}") from exc


def get_character_details(db: CharactersRAGDB, character_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve full character details by ID."""

    try:
        return db.get_character_card_by_id(character_id)
    except CharactersRAGDBError as exc:
        logger.error("Database error getting character {}: {}", character_id, exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error getting character {}: {}", character_id, exc, exc_info=True)
        raise CharactersRAGDBError(f"Unexpected error getting character: {exc}") from exc


def update_existing_character_details(
    db: CharactersRAGDB,
    character_id: int,
    update_payload: Dict[str, Any],
    expected_version: int,
) -> bool:
    """
    Update an existing character's details. Handles image data and ensures JSON fields
    are correctly formatted for the DB. Propagates DB errors.
    """

    try:
        if not update_payload:
            logger.info(
                "No specific fields to update for character ID %s, DB layer will touch if version matches.",
                character_id,
            )
            return bool(db.update_character_card(character_id, {}, expected_version))

        new_name = update_payload.get("name")
        if new_name is not None:
            current_char = db.get_character_card_by_id(character_id)
            if not current_char:
                raise InputError(f"Character with ID {character_id} not found for update.")
            if new_name != current_char.get("name"):
                existing_char_with_new_name = db.get_character_card_by_name(new_name)
                if existing_char_with_new_name and existing_char_with_new_name.get("id") != character_id:
                    raise ConflictError(
                        f"Another character with name '{new_name}' already exists (ID: {existing_char_with_new_name['id']})."
                    )

        db_ready_data = _prepare_character_data_for_db_storage(update_payload, is_update=True)
        success = db.update_character_card(character_id, db_ready_data, expected_version)
        if success:
            logger.info("Character ID {} updated successfully.", character_id)
        return bool(success)
    except (InputError, ConflictError, CharactersRAGDBError) as exc:
        logger.error("Error updating character {}: {}", character_id, exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error updating character {}: {}", character_id, exc, exc_info=True)
        raise CharactersRAGDBError(f"Unexpected error updating character: {exc}") from exc


def delete_character_from_db(db: CharactersRAGDB, character_id: int, expected_version: int) -> bool:
    """Soft-delete a character from the database."""

    try:
        success = db.soft_delete_character_card(character_id, expected_version)
        if success:
            logger.info("Character ID {} soft-deleted successfully.", character_id)
        return bool(success)
    except (ConflictError, CharactersRAGDBError) as exc:
        logger.error("Error soft-deleting character {}: {}", character_id, exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error soft-deleting character {}: {}", character_id, exc, exc_info=True)
        raise CharactersRAGDBError(f"Unexpected error deleting character: {exc}") from exc


def search_characters_by_query_text(
    db: CharactersRAGDB,
    search_term: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Search character cards using FTS based on the search term."""

    try:
        return db.search_character_cards(search_term, limit=limit)
    except CharactersRAGDBError as exc:
        logger.error("Error searching characters for '{}': {}", search_term, exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error searching characters: {}", exc, exc_info=True)
        raise CharactersRAGDBError(f"Unexpected error searching characters: {exc}") from exc


def load_character_and_image(
    db: CharactersRAGDB,
    character_id: int,
    user_name: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], List[Tuple[Optional[str], Optional[str]]], Optional[Image.Image]]:
    """
    Load character data, first message chat history, and optional image.
    Placeholders are processed using the supplied user name.
    """

    logger.debug("Loading character and image for ID: {}, User: {}", character_id, user_name)
    try:
        char_data = db.get_character_card_by_id(character_id)
        if not char_data:
            logger.warning("No character data found for ID: {}", character_id)
            return None, [], None

        char_name_from_card = char_data.get("name", "Character")

        fields_to_process = [
            "description",
            "personality",
            "scenario",
            "system_prompt",
            "post_history_instructions",
            "first_message",
            "message_example",
            "creator_notes",
        ]
        for field in fields_to_process:
            if field in char_data and char_data[field] and isinstance(char_data[field], str):
                char_data[field] = replace_placeholders(char_data[field], char_name_from_card, user_name)

        if "alternate_greetings" in char_data and isinstance(char_data["alternate_greetings"], list):
            char_data["alternate_greetings"] = [
                replace_placeholders(ag, char_name_from_card, user_name)
                for ag in char_data["alternate_greetings"]
                if isinstance(ag, str)
            ]

        first_mes_content = char_data.get("first_message")
        if not first_mes_content:
            first_mes_content = replace_placeholders(
                "Hello, I am {{char}}. How can I help you, {{user}}?",
                char_name_from_card,
                user_name,
            )

        chat_history: List[Tuple[Optional[str], Optional[str]]] = [(None, first_mes_content)]

        img: Optional[Image.Image] = None
        image_field = char_data.get("image")
        if isinstance(image_field, memoryview):
            try:
                image_field = image_field.tobytes()
            except TypeError:
                image_field = bytes(image_field)
            char_data["image"] = image_field
        elif isinstance(image_field, bytearray):
            image_field = bytes(image_field)
            char_data["image"] = image_field
        elif hasattr(image_field, "tobytes") and not isinstance(image_field, bytes):
            try:
                image_field = image_field.tobytes()  # type: ignore[attr-defined]
                char_data["image"] = image_field
            except Exception:
                pass

        if isinstance(image_field, bytes) and image_field:
            try:
                img = Image.open(io.BytesIO(image_field)).convert("RGBA")
                logger.debug(f"Successfully loaded image for character '{char_name_from_card}'")
            except Exception as exc:
                logger.error(
                    f"Error processing image for character '{char_name_from_card}' (ID: {character_id}): {exc}"
                )

        return char_data, chat_history, img

    except CharactersRAGDBError as exc:
        logger.error("Database error in load_character_and_image for ID {}: {}", character_id, exc)
        return None, [], None
    except Exception as exc:
        logger.error(
            "Unexpected error in load_character_and_image for ID %s: %s",
            character_id,
            exc,
            exc_info=True,
        )
        return None, [], None


def load_character_wrapper(
    db: CharactersRAGDB,
    character_id_or_ui_choice: Union[int, str],
    user_name: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], List[Tuple[Optional[str], Optional[str]]], Optional[Image.Image]]:
    """Wrapper around load_character_and_image accepting either an ID or UI string."""

    try:
        if isinstance(character_id_or_ui_choice, str):
            char_id_int = extract_character_id_from_ui_choice(character_id_or_ui_choice)
        elif isinstance(character_id_or_ui_choice, int):
            char_id_int = character_id_or_ui_choice
        else:
            raise ValueError("character_id_or_ui_choice must be int or string.")

        return load_character_and_image(db, char_id_int, user_name)
    except ValueError as exc:
        logger.error("Error in load_character_wrapper with input '{}': {}", character_id_or_ui_choice, exc)
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error in load_character_wrapper for '%s': %s",
            character_id_or_ui_choice,
            exc,
            exc_info=True,
        )
        raise
