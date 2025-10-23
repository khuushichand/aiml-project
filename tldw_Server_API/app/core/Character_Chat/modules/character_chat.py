"""
Character chat operations module.

This module contains functions for managing chat sessions and messages. It is
the canonical implementation used by the FastAPI endpoints and the public
facade.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from PIL import Image

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)

from .character_db import load_character_and_image
from .character_utils import replace_placeholders


def process_db_messages_to_ui_history(
    db_messages: List[Dict[str, Any]],
    char_name_from_card: str,
    user_name_for_placeholders: Optional[str],
    actual_user_sender_id_in_db: str = "User",
    actual_char_sender_id_in_db: Optional[str] = None,
) -> List[Tuple[Optional[str], Optional[str]]]:
    """Convert database messages to UI-friendly paired chat history format."""

    processed_history: List[Tuple[Optional[str], Optional[str]]] = []
    char_sender_identifier = (
        actual_char_sender_id_in_db if actual_char_sender_id_in_db else char_name_from_card
    )
    user_identifiers = {
        "user",
    }
    char_identifiers = {
        char_name_from_card.lower(),
        "assistant",
        "bot",
        "ai",
        "character",
        "system",
    }

    if actual_user_sender_id_in_db:
        user_identifiers.add(actual_user_sender_id_in_db.lower())
    if char_sender_identifier:
        char_identifiers.add(str(char_sender_identifier).strip().lower())

    user_msg_buffer: Optional[str] = None

    for msg_data in db_messages:
        sender = msg_data.get("sender")
        content = msg_data.get("content", "")

        processed_content = replace_placeholders(content, char_name_from_card, user_name_for_placeholders)

        sender_normalized = str(sender).strip() if isinstance(sender, str) else ""
        sender_lower = sender_normalized.lower()

        if sender_lower in char_identifiers:
            if user_msg_buffer is not None:
                processed_history.append((user_msg_buffer, processed_content))
                user_msg_buffer = None
            else:
                processed_history.append((None, processed_content))
        elif sender_lower in user_identifiers:
            if user_msg_buffer is not None:
                processed_history.append((user_msg_buffer, None))
            user_msg_buffer = processed_content
        else:
            logger.warning(f"Message from unknown sender '{sender}': {processed_content[:50]}...")
            if user_msg_buffer is not None:
                processed_history.append((user_msg_buffer, f"[{sender}] {processed_content}"))
                user_msg_buffer = None
            else:
                processed_history.append((None, f"[{sender}] {processed_content}"))

    if user_msg_buffer is not None:
        processed_history.append((user_msg_buffer, None))

    return processed_history


def load_chat_and_character(
    db: CharactersRAGDB,
    conversation_id_str: str,
    user_name: Optional[str],
    messages_limit: int = 2000,
) -> Tuple[
    Optional[Dict[str, Any]],
    List[Tuple[Optional[str], Optional[str]]],
    Optional[Image.Image],
]:
    """Load an existing chat conversation and associated character data."""

    logger.debug(
        "Loading chat/conversation ID: %s, User: %s, Msg Limit: %s",
        conversation_id_str,
        user_name,
        messages_limit,
    )
    try:
        conversation_data = db.get_conversation_by_id(conversation_id_str)
        if not conversation_data:
            logger.warning("No conversation found with ID: %s", conversation_id_str)
            return None, [], None

        character_id = conversation_data.get("character_id")
        if not character_id:
            logger.error(
                "Conversation %s has no character_id associated.",
                conversation_id_str,
            )
            raw_db_messages = db.get_messages_for_conversation(
                conversation_id_str,
                limit=messages_limit,
                order_by_timestamp="ASC",
            )
            processed_ui_history = process_db_messages_to_ui_history(
                raw_db_messages,
                "Unknown Character",
                user_name,
            )
            return None, processed_ui_history, None

        char_data, _, img = load_character_and_image(db, character_id, user_name)

        if not char_data:
            logger.warning(
                "No character card found for char_id %s (from conv %s)",
                character_id,
                conversation_id_str,
            )
            raw_db_messages = db.get_messages_for_conversation(
                conversation_id_str,
                limit=messages_limit,
                order_by_timestamp="ASC",
            )
            processed_ui_history = process_db_messages_to_ui_history(
                raw_db_messages,
                "Unknown Character",
                user_name,
            )
            return None, processed_ui_history, img

        char_name_from_card = char_data.get("name", "Character")
        raw_db_messages = db.get_messages_for_conversation(
            conversation_id_str,
            limit=messages_limit,
            order_by_timestamp="ASC",
        )
        processed_ui_history = process_db_messages_to_ui_history(
            raw_db_messages,
            char_name_from_card,
            user_name,
            actual_user_sender_id_in_db="User",
            actual_char_sender_id_in_db=char_name_from_card,
        )

        return char_data, processed_ui_history, img

    except CharactersRAGDBError as exc:
        logger.error(
            "Database error in load_chat_and_character for conversation ID %s: %s",
            conversation_id_str,
            exc,
        )
        return None, [], None
    except Exception as exc:
        logger.error(
            "Unexpected error in load_chat_and_character for conv ID %s: %s",
            conversation_id_str,
            exc,
            exc_info=True,
        )
        return None, [], None


def start_new_chat_session(
    db: CharactersRAGDB,
    character_id: int,
    user_name: Optional[str],
    custom_title: Optional[str] = None,
) -> Tuple[
    Optional[str],
    Optional[Dict[str, Any]],
    Optional[List[Tuple[Optional[str], Optional[str]]]],
    Optional[Image.Image],
]:
    """Start a new chat session with the specified character."""

    logger.debug("Starting new chat session for character_id: %s, user: %s", character_id, user_name)

    original_first_message_content: Optional[str] = None
    try:
        raw_char_data_for_first_message = db.get_character_card_by_id(character_id)
        if raw_char_data_for_first_message:
            original_first_message_content = raw_char_data_for_first_message.get("first_message")
        else:
            logger.warning(
                "Could not load raw character data for ID %s to get original first message.",
                character_id,
            )
    except CharactersRAGDBError as exc:
        logger.warning(
            "DB error fetching raw character data for ID %s: %s. Proceeding with caution.",
            character_id,
            exc,
        )

    char_data, initial_ui_history, img = load_character_and_image(db, character_id, user_name)

    if not char_data:
        logger.error("Failed to load character_id %s to start new chat session.", character_id)
        return None, None, None, None

    char_name = char_data.get("name", "Character")
    conv_title = custom_title if custom_title else f"Chat with {char_name} ({time.strftime('%Y-%m-%d %H:%M')})"

    conversation_id_val: Optional[str] = None
    try:
        conv_payload = {
            "character_id": character_id,
            "title": conv_title,
        }
        conversation_id_val = db.add_conversation(conv_payload)

        if not conversation_id_val:
            logger.error(
                "Failed to create conversation record in DB for character %s.",
                char_name,
            )
            return None, char_data, initial_ui_history, img

        logger.info(
            "Created new conversation ID: %s for character '%s'.",
            conversation_id_val,
            char_name,
        )

        message_to_store_in_db: Optional[str] = original_first_message_content

        if message_to_store_in_db is None:
            if initial_ui_history and initial_ui_history[0] and initial_ui_history[0][1]:
                message_to_store_in_db = initial_ui_history[0][1]
                logger.warning(
                    "Storing processed first message for char %s in new conversation %s as raw version was not available.",
                    char_name,
                    conversation_id_val,
                )
            elif char_data.get("first_message"):
                message_to_store_in_db = char_data["first_message"]
                logger.warning(
                    "Storing processed first_message from char_data for char %s in new conversation %s.",
                    char_name,
                    conversation_id_val,
                )

        if message_to_store_in_db:
            db.add_message(
                {
                    "conversation_id": conversation_id_val,
                    "sender": char_name,
                    "content": message_to_store_in_db,
                }
            )
            logger.debug(
                "Added character's first message to new conversation %s.",
                conversation_id_val,
            )
        else:
            logger.warning(
                "Character %s (ID: %s) has no first message to add to new conversation %s.",
                char_name,
                character_id,
                conversation_id_val,
            )
            if not (initial_ui_history and initial_ui_history[0] and initial_ui_history[0][1]):
                initial_ui_history = []

        return conversation_id_val, char_data, initial_ui_history, img

    except (CharactersRAGDBError, InputError, ConflictError) as exc:
        logger.error(
            "Error during new chat session creation for char %s: %s",
            char_name,
            exc,
        )
        return conversation_id_val, char_data, initial_ui_history, img
    except Exception as exc:
        logger.error("Unexpected error in start_new_chat_session: %s", exc, exc_info=True)
        return conversation_id_val, char_data, initial_ui_history, img


def list_character_conversations(
    db: CharactersRAGDB,
    character_id: int,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List active conversations for a given character."""

    try:
        return db.get_conversations_for_character(character_id, limit=limit, offset=offset)
    except CharactersRAGDBError as exc:
        logger.error(
            "Failed to list conversations for character ID %s: %s",
            character_id,
            exc,
        )
        return []
    except Exception as exc:
        logger.error(
            "Unexpected error listing conversations for char ID %s: %s",
            character_id,
            exc,
            exc_info=True,
        )
        return []


def get_conversation_metadata(db: CharactersRAGDB, conversation_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve metadata for a specific conversation."""

    try:
        return db.get_conversation_by_id(conversation_id)
    except CharactersRAGDBError as exc:
        logger.error(
            "Failed to get metadata for conversation ID %s: %s",
            conversation_id,
            exc,
        )
        return None
    except Exception as exc:
        logger.error(
            "Unexpected error getting conversation metadata for ID %s: %s",
            conversation_id,
            exc,
            exc_info=True,
        )
        return None


def update_conversation_metadata(
    db: CharactersRAGDB,
    conversation_id: str,
    update_data: Dict[str, Any],
    expected_version: int,
) -> bool:
    """Update conversation metadata with optimistic locking."""

    try:
        valid_update_keys = {"title", "rating"}
        payload_to_db = {k: v for k, v in update_data.items() if k in valid_update_keys}

        if not payload_to_db:
            logger.warning(
                "No valid fields to update for conversation ID %s from data: %s",
                conversation_id,
                update_data,
            )

        return db.update_conversation(conversation_id, payload_to_db, expected_version)
    except (CharactersRAGDBError, InputError, ConflictError) as exc:
        logger.error(
            "Failed to update metadata for conversation ID %s: %s",
            conversation_id,
            exc,
        )
        return False
    except Exception as exc:
        logger.error(
            "Unexpected error updating conversation metadata for ID %s: %s",
            conversation_id,
            exc,
            exc_info=True,
        )
        return False


def delete_conversation_by_id(
    db: CharactersRAGDB,
    conversation_id: str,
    expected_version: int,
) -> bool:
    """Soft-delete a conversation using optimistic locking."""

    try:
        success = db.soft_delete_conversation(conversation_id, expected_version)
        if success:
            logger.info("Conversation %s soft-deleted successfully.", conversation_id)
        return success
    except (CharactersRAGDBError, ConflictError) as exc:
        logger.error(
            "Failed to remove conversation ID %s: %s",
            conversation_id,
            exc,
        )
        return False
    except Exception as exc:
        logger.error("Unexpected error removing conversation ID %s: %s", conversation_id, exc, exc_info=True)
        return False


def search_conversations_by_title_query(
    db: CharactersRAGDB,
    title_query: str,
    character_id: Optional[int] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Search conversations by title."""

    try:
        return db.search_conversations_by_title(title_query, character_id, limit)
    except CharactersRAGDBError as exc:
        logger.error(
            "Failed to search conversations with query '%s': %s",
            title_query,
            exc,
        )
        return []
    except Exception as exc:
        logger.error(
            "Unexpected error searching conversations: %s",
            exc,
            exc_info=True,
        )
        return []


def post_message_to_conversation(
    db: CharactersRAGDB,
    conversation_id: str,
    character_name: str,
    message_content: str,
    is_user_message: bool,
    parent_message_id: Optional[str] = None,
    ranking: Optional[int] = None,
    image_data: Optional[bytes] = None,
    image_mime_type: Optional[str] = None,
) -> Optional[str]:
    """Post a new message to a specified conversation."""

    if not conversation_id:
        logger.error("Cannot post message: conversation_id is required.")
        raise InputError("conversation_id is required for posting a message.")
    if not character_name and not is_user_message:
        logger.error("Cannot post character message: character_name is required.")
        raise InputError("character_name is required for character messages.")

    sender_name = "User" if is_user_message else character_name

    if not message_content and not image_data:
        logger.error("Cannot post message: Message must have text content or image data.")
        raise InputError("Message must have text content or image data.")

    msg_payload = {
        "conversation_id": conversation_id,
        "sender": sender_name,
        "content": message_content,
        "parent_message_id": parent_message_id,
        "ranking": ranking,
        "image_data": image_data,
        "image_mime_type": image_mime_type,
    }

    try:
        message_id = db.add_message(msg_payload)
        if message_id:
            logger.info(
                "Posted message ID %s from '%s' to conversation %s.",
                message_id,
                sender_name,
                conversation_id,
            )
            try:
                conversation_meta = db.get_conversation_by_id(conversation_id)
            except CharactersRAGDBError as meta_exc:
                logger.warning(
                    "Non-fatal: unable to fetch conversation %s for metadata update after message %s: %s",
                    conversation_id,
                    message_id,
                    meta_exc,
                )
                conversation_meta = None

            if conversation_meta:
                expected_version = conversation_meta.get("version")
                if isinstance(expected_version, int):
                    try:
                        db.update_conversation(conversation_id, {}, expected_version)
                    except (ConflictError, CharactersRAGDBError) as conv_exc:
                        logger.debug(
                            "Non-fatal: failed to bump conversation metadata for %s after message %s: %s",
                            conversation_id,
                            message_id,
                            conv_exc,
                        )
        else:
            logger.error(
                "Failed to post message from '%s' to conversation %s (DB returned no ID without error).",
                sender_name,
                conversation_id,
            )
        return message_id
    except (CharactersRAGDBError, InputError, ConflictError) as exc:
        logger.error(
            "Error posting message from '%s' to conversation %s: %s",
            sender_name,
            conversation_id,
            exc,
        )
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error posting message to conv %s: %s",
            conversation_id,
            exc,
            exc_info=True,
        )
        if not isinstance(exc, CharactersRAGDBError):
            raise CharactersRAGDBError(f"Unexpected error posting message: {exc}") from exc
        raise


def retrieve_message_details(
    db: CharactersRAGDB,
    message_id: str,
    character_name_for_placeholders: str,
    user_name_for_placeholders: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Retrieve a specific message by its ID and process placeholder content."""

    try:
        message_data = db.get_message_by_id(message_id)
        if not message_data:
            return None

        if "content" in message_data and isinstance(message_data["content"], str):
            message_data["content"] = replace_placeholders(
                message_data["content"],
                character_name_for_placeholders,
                user_name_for_placeholders,
            )
        return message_data
    except CharactersRAGDBError as exc:
        logger.error("Failed to retrieve message ID %s: %s", message_id, exc)
        return None
    except Exception as exc:
        logger.error(
            "Unexpected error retrieving message ID %s: %s",
            message_id,
            exc,
            exc_info=True,
        )
        return None


def retrieve_conversation_messages_for_ui(
    db: CharactersRAGDB,
    conversation_id: str,
    character_name: str,
    user_name: Optional[str],
    limit: int = 2000,
    offset: int = 0,
    order: str = "ASC",
) -> List[Tuple[Optional[str], Optional[str]]]:
    """Retrieve and process conversation messages for UI display."""

    order_upper = order.upper()
    if order_upper not in ["ASC", "DESC"]:
        logger.warning("Invalid order '%s' for message retrieval. Defaulting to ASC.", order)
        order_upper = "ASC"

    try:
        raw_db_messages = db.get_messages_for_conversation(
            conversation_id,
            limit=limit,
            offset=offset,
            order_by_timestamp=order_upper,
        )

        processed_ui_history = process_db_messages_to_ui_history(
            raw_db_messages,
            char_name_from_card=character_name,
            user_name_for_placeholders=user_name,
            actual_user_sender_id_in_db="User",
            actual_char_sender_id_in_db=character_name,
        )
        return processed_ui_history

    except CharactersRAGDBError as exc:
        logger.error(
            "Failed to retrieve and process messages for conversation ID %s: %s",
            conversation_id,
            exc,
        )
        return []
    except Exception as exc:
        logger.error(
            "Unexpected error retrieving UI messages for conversation %s: %s",
            conversation_id,
            exc,
            exc_info=True,
        )
        return []


def edit_message_content(
    db: CharactersRAGDB,
    message_id: str,
    new_content: str,
    expected_version: int,
) -> bool:
    """Update the text content of a specific message."""

    try:
        update_payload = {"content": new_content}
        success = db.update_message(message_id, update_payload, expected_version)
        if success:
            logger.info("Edited message %s", message_id)
        else:
            logger.warning(
                "Failed to edit message %s - version mismatch or message not found",
                message_id,
            )
        return bool(success)
    except (CharactersRAGDBError, InputError, ConflictError) as exc:
        logger.error("Failed to edit content for message ID %s: %s", message_id, exc)
        return False
    except Exception as exc:
        logger.error(
            "Unexpected error editing message content for ID %s: %s",
            message_id,
            exc,
            exc_info=True,
        )
        return False


def set_message_ranking(
    db: CharactersRAGDB,
    message_id: str,
    ranking: int,
    expected_version: int,
) -> bool:
    """Set or update the ranking of a specific message."""

    update_payload = {"ranking": ranking}
    try:
        return bool(db.update_message(message_id, update_payload, expected_version))
    except (CharactersRAGDBError, InputError, ConflictError) as exc:
        logger.error("Failed to set ranking for message ID %s: %s", message_id, exc)
        return False
    except Exception as exc:
        logger.error(
            "Unexpected error setting message ranking for ID %s: %s",
            message_id,
            exc,
            exc_info=True,
        )
        return False


def remove_message_from_conversation(
    db: CharactersRAGDB,
    message_id: str,
    expected_version: int,
) -> bool:
    """Soft-delete a message from a conversation."""

    try:
        return bool(db.soft_delete_message(message_id, expected_version))
    except (CharactersRAGDBError, ConflictError) as exc:
        logger.error("Failed to remove message ID %s: %s", message_id, exc)
        return False
    except Exception as exc:
        logger.error(
            "Unexpected error removing message ID %s: %s",
            message_id,
            exc,
            exc_info=True,
        )
        return False


def find_messages_in_conversation(
    db: CharactersRAGDB,
    conversation_id: str,
    search_query: str,
    character_name_for_placeholders: str,
    user_name_for_placeholders: Optional[str],
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Search for messages within a specific conversation by content."""

    try:
        found_messages = db.search_messages_by_content(
            content_query=search_query,
            conversation_id=conversation_id,
            limit=limit,
        )

        processed_results = []
        for msg_data in found_messages:
            if "content" in msg_data and isinstance(msg_data["content"], str):
                msg_data["content"] = replace_placeholders(
                    msg_data["content"],
                    character_name_for_placeholders,
                    user_name_for_placeholders,
                )
            processed_results.append(msg_data)
        return processed_results
    except CharactersRAGDBError as exc:
        logger.error(
            "Failed to search messages in conversation ID %s for '%s': %s",
            conversation_id,
            search_query,
            exc,
        )
        return []
    except Exception as exc:
        logger.error(
            "Unexpected error searching messages in conversation %s: %s",
            conversation_id,
            exc,
            exc_info=True,
        )
        return []
