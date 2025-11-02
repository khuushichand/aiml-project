"""
Character chat operations module.

This module contains functions for managing chat sessions and messages. It is
the canonical implementation used by the FastAPI endpoints and the public
facade.
"""

import base64
import time
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from loguru import logger
from PIL import Image

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)

from .character_db import load_character_and_image
from .character_utils import (
    replace_placeholders,
    USER_SENDER_ALIASES as _LEGACY_USER_SENDER_ALIASES,
    NON_CHARACTER_SENDER_ALIASES as _NON_CHARACTER_SENDER_ALIASES,
)
from tldw_Server_API.app.core.config import settings


# Aliases are sourced from character_utils for consistency across modules.


def _extract_message_attachments(msg_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build a normalized attachment list for UI consumption."""

    attachments: Dict[int, Dict[str, Any]] = {}

    def _normalize_payload(position: int, data: Any, mime: Optional[str]) -> None:
        if data is None:
            return
        payload = data.tobytes() if isinstance(data, memoryview) else data
        if isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
        else:
            payload_bytes = bytes(payload)
        attachments[position] = {
            "position": position,
            "data": base64.b64encode(payload_bytes).decode("ascii"),
            "encoding": "base64",
            "size": len(payload_bytes),
            "mime_type": mime,
            "message_id": msg_data.get("id"),
        }

    primary_data = msg_data.get("image_data")
    primary_mime = msg_data.get("image_mime_type")
    if primary_data is not None:
        _normalize_payload(0, primary_data, primary_mime)

    for image_entry in msg_data.get("images") or []:
        if not isinstance(image_entry, dict):
            continue
        position_raw = image_entry.get("position")
        try:
            position_int = int(position_raw) if position_raw is not None else len(attachments)
        except (TypeError, ValueError):
            position_int = len(attachments)
        _normalize_payload(
            position_int,
            image_entry.get("image_data"),
            image_entry.get("image_mime_type"),
        )

    return [attachments[idx] for idx in sorted(attachments.keys())]


def _infer_character_sender_aliases(
    db_messages: List[Dict[str, Any]],
    user_aliases: set[str],
    primary_char_name: str,
) -> List[str]:
    """Infer legacy character sender aliases stored on existing messages."""

    alias_counter: Counter[str] = Counter()
    first_candidate: Optional[str] = None
    primary_lower = primary_char_name.lower()

    for msg in db_messages:
        sender = msg.get("sender")
        if not isinstance(sender, str):
            continue
        normalized = sender.strip()
        if not normalized:
            continue
        lower = normalized.lower()

        if lower == primary_lower:
            continue
        if lower in user_aliases:
            continue
        if lower in _NON_CHARACTER_SENDER_ALIASES:
            continue
        if normalized.startswith("["):
            continue

        alias_counter[normalized] += 1
        if first_candidate is None:
            first_candidate = normalized

    inferred_aliases: List[str] = []
    for alias, count in alias_counter.items():
        if alias.lower() == primary_lower:
            continue
        if count >= 2 or alias == first_candidate:
            inferred_aliases.append(alias)
    return inferred_aliases


def _compute_additional_char_aliases(
    db_messages: List[Dict[str, Any]],
    char_name_from_card: str,
    user_name_for_placeholders: Optional[str],
    actual_user_sender_id_in_db: str,
) -> Tuple[List[str], List[str]]:
    user_aliases = {alias.lower() for alias in _LEGACY_USER_SENDER_ALIASES}
    if actual_user_sender_id_in_db:
        user_aliases.add(actual_user_sender_id_in_db.lower())
    if user_name_for_placeholders:
        user_aliases.add(str(user_name_for_placeholders).strip().lower())

    candidate_aliases = _infer_character_sender_aliases(db_messages, user_aliases, char_name_from_card)
    if not candidate_aliases:
        return [], []

    inferred_user_aliases: List[str] = []
    filtered_char_aliases: List[str] = []
    normalized_alias_map = {alias.lower(): alias for alias in candidate_aliases}

    # Pre-compute lowercase senders for efficient neighbour lookups
    sender_sequence: List[Optional[str]] = []
    for msg in db_messages:
        sender = msg.get("sender")
        sender_sequence.append(str(sender).strip().lower() if isinstance(sender, str) else None)

    def _char_neighbor_set(current_alias: str) -> set[str]:
        neighbors = {char_name_from_card.strip().lower()}
        for other_alias in candidate_aliases:
            normalized_other = other_alias.strip().lower()
            if normalized_other and normalized_other != current_alias:
                neighbors.add(normalized_other)
        return neighbors

    for alias_lower, alias_original in normalized_alias_map.items():
        if not alias_lower:
            continue

        char_context = 0
        user_context = 0
        char_neighbors = _char_neighbor_set(alias_lower)

        for idx, sender_lower in enumerate(sender_sequence):
            if sender_lower != alias_lower:
                continue
            prev_lower = sender_sequence[idx - 1] if idx > 0 else None
            next_lower = sender_sequence[idx + 1] if idx + 1 < len(sender_sequence) else None

            if prev_lower and prev_lower in user_aliases:
                user_context += 1
            if next_lower and next_lower in user_aliases:
                user_context += 1

            if prev_lower and prev_lower in char_neighbors:
                char_context += 1
            if next_lower and next_lower in char_neighbors:
                char_context += 1

        if char_context > user_context and char_context > 0:
            if alias_lower not in user_aliases:
                inferred_user_aliases.append(alias_original)
                user_aliases.add(alias_lower)
        else:
            filtered_char_aliases.append(alias_original)

    return filtered_char_aliases, inferred_user_aliases


def process_db_messages_to_ui_history(
    db_messages: List[Dict[str, Any]],
    char_name_from_card: str,
    user_name_for_placeholders: Optional[str],
    actual_user_sender_id_in_db: str = "User",
    actual_char_sender_id_in_db: Optional[str] = None,
    additional_char_sender_ids: Optional[Iterable[str]] = None,
    additional_user_sender_ids: Optional[Iterable[str]] = None,
    char_first_message: Optional[str] = None,
    keep_trailing_user: bool = True,
) -> List[Tuple[Optional[str], Optional[str]]]:
    """Convert database messages to UI-friendly paired chat history format."""

    rich_history = process_db_messages_to_rich_ui_history(
        db_messages=db_messages,
        char_name_from_card=char_name_from_card,
        user_name_for_placeholders=user_name_for_placeholders,
        actual_user_sender_id_in_db=actual_user_sender_id_in_db,
        actual_char_sender_id_in_db=actual_char_sender_id_in_db,
        additional_char_sender_ids=additional_char_sender_ids,
        additional_user_sender_ids=additional_user_sender_ids,
        char_first_message=char_first_message,
        keep_trailing_user=keep_trailing_user,
    )

    processed_history: List[Tuple[Optional[str], Optional[str]]] = []
    for turn in rich_history:
        user_content = turn["user"]["content"] if turn["user"] else None
        character_content = None
        if turn["character"]:
            character_content = turn["character"]["content"]
        elif turn["non_character"]:
            character_content = turn["non_character"]["content"]
        processed_history.append((user_content, character_content))
    return processed_history


def process_db_messages_to_rich_ui_history(
    db_messages: List[Dict[str, Any]],
    char_name_from_card: str,
    user_name_for_placeholders: Optional[str],
    actual_user_sender_id_in_db: str = "User",
    actual_char_sender_id_in_db: Optional[str] = None,
    additional_char_sender_ids: Optional[Iterable[str]] = None,
    additional_user_sender_ids: Optional[Iterable[str]] = None,
    char_first_message: Optional[str] = None,
    keep_trailing_user: bool = False,
) -> List[Dict[str, Optional[Dict[str, Any]]]]:
    """Convert database messages to UI-friendly structures including metadata."""

    char_sender_identifier = (
        actual_char_sender_id_in_db if actual_char_sender_id_in_db else char_name_from_card
    )
    user_identifiers = {alias.lower() for alias in _LEGACY_USER_SENDER_ALIASES}
    non_character_aliases = {alias.lower() for alias in _NON_CHARACTER_SENDER_ALIASES}
    char_identifiers = {
        char_name_from_card.lower(),
        "assistant",
        "bot",
        "ai",
        "character",
    }

    if actual_user_sender_id_in_db:
        user_identifiers.add(actual_user_sender_id_in_db.lower())
    if char_sender_identifier:
        char_identifiers.add(str(char_sender_identifier).strip().lower())
    if additional_char_sender_ids:
        for alias in additional_char_sender_ids:
            if not alias:
                continue
            alias_norm = str(alias).strip().lower()
            if alias_norm:
                char_identifiers.add(alias_norm)
    if additional_user_sender_ids:
        for alias in additional_user_sender_ids:
            if not alias:
                continue
            alias_norm = str(alias).strip().lower()
            if alias_norm:
                user_identifiers.add(alias_norm)
    if user_name_for_placeholders:
        placeholder_alias = str(user_name_for_placeholders).strip().lower()
        if placeholder_alias:
            user_identifiers.add(placeholder_alias)

    user_msg_detail_buffer: Optional[Dict[str, Any]] = None

    char_first_message_normalized = None
    if isinstance(char_first_message, str):
        char_first_message_normalized = char_first_message.strip()

    def _resolve_ambiguous_sender(
        message_index: int,
        processed_text: str,
        pending_user_buffer: bool,
        character_messages_seen: int,
        user_messages_seen: int,
        next_sender_lower: Optional[str],
    ) -> str:
        if pending_user_buffer:
            return "character"
        processed_text_normalized = processed_text.strip()
        if (
            char_first_message_normalized
            and processed_text_normalized
            and processed_text_normalized == char_first_message_normalized
            and character_messages_seen == 0
        ):
            return "character"
        if user_messages_seen > character_messages_seen:
            return "character"
        if character_messages_seen > user_messages_seen:
            return "user"
        if next_sender_lower:
            # If the following sender is clearly a user (and not a character),
            # then this ambiguous message is best treated as a character reply;
            # conversely, if the next sender is clearly a character (and not a user),
            # bias this message as a character as well to avoid misclassifying
            # consecutive character messages as a user turn.
            if (
                next_sender_lower in user_identifiers
                and next_sender_lower not in char_identifiers
            ):
                return "character"
            if (
                next_sender_lower in char_identifiers
                and next_sender_lower not in user_identifiers
            ):
                return "character"
        if message_index == 0 and char_first_message_normalized:
            return "character"
        return "character"

    character_messages_seen = 0
    user_messages_seen = 0
    total_messages = len(db_messages)

    rich_history: List[Dict[str, Optional[Dict[str, Any]]]] = []

    for idx, msg_data in enumerate(db_messages):
        sender = msg_data.get("sender")
        content = msg_data.get("content", "")

        processed_content = replace_placeholders(content, char_name_from_card, user_name_for_placeholders)

        sender_normalized = str(sender).strip() if isinstance(sender, str) else ""
        sender_lower = sender_normalized.lower()
        sender_lower_raw = str(sender).lower() if isinstance(sender, str) else ""

        is_non_character_sender = False
        if sender_lower:
            if sender_lower in non_character_aliases:
                is_non_character_sender = True
            else:
                for alias in non_character_aliases:
                    if sender_lower.startswith(f"{alias}:"):
                        is_non_character_sender = True
                        break

        if is_non_character_sender:
            formatted_content = processed_content
            if sender_normalized:
                if formatted_content:
                    formatted_content = f"[{sender_normalized}] {processed_content}"
                else:
                    formatted_content = f"[{sender_normalized}]"
            detail = {
                "id": msg_data.get("id"),
                "sender": sender_normalized or sender,
                "content": formatted_content,
                "raw_sender": sender,
                "attachments": _extract_message_attachments(msg_data),
                "metadata": {
                    "timestamp": msg_data.get("timestamp"),
                    "ranking": msg_data.get("ranking"),
                    "version": msg_data.get("version"),
                },
            }
            if user_msg_detail_buffer is not None:
                rich_history.append(
                    {
                        "user": user_msg_detail_buffer,
                        "character": None,
                        "non_character": detail,
                    }
                )
                user_msg_detail_buffer = None
            else:
                rich_history.append(
                    {
                        "user": None,
                        "character": None,
                        "non_character": detail,
                    }
                )
            continue

        in_user_identifiers = sender_lower_raw in user_identifiers if sender_lower_raw else False
        in_char_identifiers = sender_lower_raw in char_identifiers if sender_lower_raw else False

        next_sender_lower: Optional[str] = None
        if idx + 1 < total_messages:
            next_sender_value = db_messages[idx + 1].get("sender")
            if isinstance(next_sender_value, str):
                next_sender_lower = next_sender_value.strip().lower()

        sender_role: Optional[str]
        if in_char_identifiers and not in_user_identifiers:
            sender_role = "character"
        elif in_user_identifiers and not in_char_identifiers:
            sender_role = "user"
        elif in_char_identifiers and in_user_identifiers:
            # Ambiguous: sender matches both user and character aliases.
            # Prefer classifying as a user message unless we have an explicit
            # character sender id and the alias truly belongs to the character.
            # This avoids misclassifying real user messages when the character
            # name collides with user aliases (e.g. char_name == "user").
            _placeholder_alias = str(user_name_for_placeholders).strip().lower() if isinstance(user_name_for_placeholders, str) else ""
            _char_sender_norm = str(char_sender_identifier or "").strip().lower()
            if (
                actual_char_sender_id_in_db  # explicit character sender id provided
                and _placeholder_alias
                and _char_sender_norm
                and _placeholder_alias == _char_sender_norm
                and sender_lower == _char_sender_norm
            ):
                sender_role = "character"
            elif (
                char_first_message_normalized
                and isinstance(processed_content, str)
                and processed_content.strip() == char_first_message_normalized
                and character_messages_seen == 0
            ):
                # Honor explicit first-message hint: treat as character's greeting
                sender_role = "character"
            elif sender_lower in user_identifiers and not actual_char_sender_id_in_db:
                # Default to user when ambiguous only if there is no explicit
                # character sender id provided by the caller.
                sender_role = "user"
            else:
                # Resolve tie using context (parity/neighbor hints)
                sender_role = _resolve_ambiguous_sender(
                    message_index=idx,
                    processed_text=processed_content,
                    pending_user_buffer=user_msg_detail_buffer is not None,
                    character_messages_seen=character_messages_seen,
                    user_messages_seen=user_messages_seen,
                    next_sender_lower=next_sender_lower,
                )
        elif in_user_identifiers:
            sender_role = "user"
        elif in_char_identifiers:
            sender_role = "character"
        else:
            sender_role = None

        if sender_role == "character":
            detail = {
                "id": msg_data.get("id"),
                "sender": sender_normalized or sender,
                "content": processed_content,
                "raw_sender": sender,
                "attachments": _extract_message_attachments(msg_data),
                "metadata": {
                    "timestamp": msg_data.get("timestamp"),
                    "ranking": msg_data.get("ranking"),
                    "version": msg_data.get("version"),
                },
            }
            if user_msg_detail_buffer is not None:
                rich_history.append(
                    {
                        "user": user_msg_detail_buffer,
                        "character": detail,
                        "non_character": None,
                    }
                )
                user_msg_detail_buffer = None
            else:
                rich_history.append(
                    {
                        "user": None,
                        "character": detail,
                        "non_character": None,
                    }
                )
            if sender_lower:
                char_identifiers.add(sender_lower)
            character_messages_seen += 1
            continue

        if sender_role == "user":
            detail = {
                "id": msg_data.get("id"),
                "sender": sender_normalized or sender,
                "content": processed_content,
                "raw_sender": sender,
                "attachments": _extract_message_attachments(msg_data),
                "metadata": {
                    "timestamp": msg_data.get("timestamp"),
                    "ranking": msg_data.get("ranking"),
                    "version": msg_data.get("version"),
                },
            }
            if user_msg_detail_buffer is not None:
                rich_history.append(
                    {
                        "user": user_msg_detail_buffer,
                        "character": None,
                        "non_character": None,
                    }
                )
            user_msg_detail_buffer = detail
            user_messages_seen += 1
            continue

        # Unknown sender handling - preserve legacy behaviour by treating as character
        # Redact message content in logs to avoid leaking sensitive data
        try:
            _len = len(processed_content) if isinstance(processed_content, str) else 0
        except Exception:
            _len = 0
        logger.warning("Message from unknown sender '{}' (content redacted; length={})", sender, _len)
        formatted_content = f"[{sender}] {processed_content}"
        detail = {
            "id": msg_data.get("id"),
            "sender": sender_normalized or sender,
            "content": formatted_content,
            "raw_sender": sender,
            "attachments": _extract_message_attachments(msg_data),
            "metadata": {
                "timestamp": msg_data.get("timestamp"),
                "ranking": msg_data.get("ranking"),
                "version": msg_data.get("version"),
            },
        }
        if user_msg_detail_buffer is not None:
            rich_history.append(
                {
                    "user": user_msg_detail_buffer,
                    "character": detail,
                    "non_character": None,
                }
            )
            user_msg_detail_buffer = None
        else:
            rich_history.append(
                {
                    "user": None,
                    "character": detail,
                    "non_character": None,
                }
            )
        character_messages_seen += 1

    # Optionally append trailing user-only turn if requested
    if keep_trailing_user and user_msg_detail_buffer is not None:
        rich_history.append(
            {
                "user": user_msg_detail_buffer,
                "character": None,
                "non_character": None,
            }
        )

    return rich_history


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
            logger.warning("No conversation found with ID: {}", conversation_id_str)
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
            additional_aliases, extra_user_aliases = _compute_additional_char_aliases(
                raw_db_messages,
                "Unknown Character",
                user_name,
                actual_user_sender_id_in_db="User",
            )
            processed_ui_history = process_db_messages_to_ui_history(
                raw_db_messages,
                "Unknown Character",
                user_name,
                actual_user_sender_id_in_db="User",
                actual_char_sender_id_in_db="Unknown Character",
                additional_char_sender_ids=additional_aliases,
                additional_user_sender_ids=extra_user_aliases,
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
            additional_aliases, extra_user_aliases = _compute_additional_char_aliases(
                raw_db_messages,
                "Unknown Character",
                user_name,
                actual_user_sender_id_in_db="User",
            )
            processed_ui_history = process_db_messages_to_ui_history(
                raw_db_messages,
                "Unknown Character",
                user_name,
                actual_user_sender_id_in_db="User",
                actual_char_sender_id_in_db="Unknown Character",
                additional_char_sender_ids=additional_aliases,
                additional_user_sender_ids=extra_user_aliases,
            )
            return None, processed_ui_history, img

        char_name_from_card = char_data.get("name", "Character")
        raw_db_messages = db.get_messages_for_conversation(
            conversation_id_str,
            limit=messages_limit,
            order_by_timestamp="ASC",
        )
        additional_aliases, extra_user_aliases = _compute_additional_char_aliases(
            raw_db_messages,
            char_name_from_card,
            user_name,
            actual_user_sender_id_in_db="User",
        )
        processed_ui_history = process_db_messages_to_ui_history(
            raw_db_messages,
            char_name_from_card,
            user_name,
            actual_user_sender_id_in_db="User",
            actual_char_sender_id_in_db=char_name_from_card,
            additional_char_sender_ids=additional_aliases,
            additional_user_sender_ids=extra_user_aliases,
            char_first_message=char_data.get("first_message"),
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
    greeting_strategy: Optional[str] = None,
    alternate_index: Optional[int] = None,
) -> Tuple[
    Optional[str],
    Optional[Dict[str, Any]],
    Optional[List[Tuple[Optional[str], Optional[str]]]],
    Optional[Image.Image],
]:
    """Start a new chat session with the specified character."""

    logger.debug("Starting new chat session for character_id: {}, user: {}", character_id, user_name)

    original_first_message_content: Optional[str] = None
    original_alternate_greetings: Optional[List[str]] = None
    try:
        raw_char_data_for_first_message = db.get_character_card_by_id(character_id)
        if raw_char_data_for_first_message:
            original_first_message_content = raw_char_data_for_first_message.get("first_message")
            ag = raw_char_data_for_first_message.get("alternate_greetings")
            if isinstance(ag, list):
                # Ensure only strings
                original_alternate_greetings = [str(x) for x in ag if isinstance(x, (str, bytes))]
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
        logger.error("Failed to load character_id {} to start new chat session.", character_id)
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

        # Apply optional greeting strategy selection using raw (unprocessed) fields
        selected_alt: Optional[str] = None
        try:
            if greeting_strategy in {"alternate_random", "alternate_index"} and original_alternate_greetings:
                if greeting_strategy == "alternate_random":
                    import random as _rnd
                    if original_alternate_greetings:
                        selected_alt = _rnd.choice(original_alternate_greetings)
                elif greeting_strategy == "alternate_index":
                    if isinstance(alternate_index, int) and alternate_index >= 0 and alternate_index < len(original_alternate_greetings):
                        selected_alt = original_alternate_greetings[alternate_index]
        except Exception as _sel_err:
            logger.debug("Alternate greeting selection failed: {}", _sel_err)

        if isinstance(selected_alt, str) and selected_alt.strip():
            message_to_store_in_db = selected_alt

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
            # Ensure returned initial_ui_history aligns with the stored message
            try:
                processed = replace_placeholders(message_to_store_in_db, char_name, user_name)
                if initial_ui_history:
                    initial_ui_history[0] = (None, processed)
                else:
                    initial_ui_history = [(None, processed)]
            except Exception:
                pass
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
        logger.error("Unexpected error in start_new_chat_session: {}", exc, exc_info=True)
        return conversation_id_val, char_data, initial_ui_history, img


def list_character_conversations(
    db: CharactersRAGDB,
    character_id: int,
    limit: int = 50,
    offset: int = 0,
    client_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List active conversations for a given character."""

    try:
        return db.get_conversations_for_character(
            character_id,
            limit=limit,
            offset=offset,
            client_id=client_id,
        )
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
            logger.info("Conversation {} soft-deleted successfully.", conversation_id)
        return success
    except (CharactersRAGDBError, ConflictError) as exc:
        logger.error(
            "Failed to remove conversation ID %s: %s",
            conversation_id,
            exc,
        )
        return False
    except Exception as exc:
        logger.error("Unexpected error removing conversation ID {}: {}", conversation_id, exc, exc_info=True)
        return False


def search_conversations_by_title_query(
    db: CharactersRAGDB,
    title_query: str,
    character_id: Optional[int] = None,
    limit: int = 10,
    client_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search conversations by title."""

    try:
        return db.search_conversations_by_title(
            title_query,
            character_id,
            limit,
            client_id=client_id,
        )
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
    sender_override: Optional[str] = None,
) -> Optional[str]:
    """Post a new message to a specified conversation."""

    if not conversation_id:
        logger.error("Cannot post message: conversation_id is required.")
        raise InputError("conversation_id is required for posting a message.")
    if not character_name and not is_user_message and not sender_override:
        logger.error("Cannot post character message: character_name is required.")
        raise InputError("character_name is required for character messages.")

    sender_name = sender_override or ("User" if is_user_message else character_name)
    if not sender_name:
        logger.error("Cannot post message: sender name could not be determined.")
        raise InputError("sender name could not be determined for message.")

    if not message_content and not image_data:
        logger.error("Cannot post message: Message must have text content or image data.")
        raise InputError("Message must have text content or image data.")

    # Optional preflight image size guard (mirrors DB constraints for clearer API errors)
    if image_data is not None:
        try:
            max_bytes = int(settings.get("MAX_MESSAGE_IMAGE_BYTES", 5 * 1024 * 1024))
        except Exception:
            max_bytes = 5 * 1024 * 1024
        raw = image_data.tobytes() if isinstance(image_data, memoryview) else image_data
        if isinstance(raw, (bytes, bytearray)) and len(raw) > max_bytes:
            raise InputError(f"Image attachment exceeds maximum size of {max_bytes} bytes")

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
        logger.error("Failed to retrieve message ID {}: {}", message_id, exc)
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
    rich_output: bool = False,
    char_first_message_hint: Optional[str] = None,
) -> Union[List[Tuple[Optional[str], Optional[str]]], List[Dict[str, Optional[Dict[str, Any]]]]]:
    """Retrieve and process conversation messages for UI display.

    When ``rich_output`` is True the response contains message metadata and attachments.
    """

    order_upper = order.upper()
    if order_upper not in ["ASC", "DESC"]:
        logger.warning("Invalid order '{}' for message retrieval. Defaulting to ASC.", order)
        order_upper = "ASC"

    try:
        raw_db_messages = db.get_messages_for_conversation(
            conversation_id,
            limit=limit,
            offset=offset,
            order_by_timestamp=order_upper,
        )

        additional_aliases, extra_user_aliases = _compute_additional_char_aliases(
            raw_db_messages,
            character_name,
            user_name,
            actual_user_sender_id_in_db="User",
        )

        messages_for_processing = (
            list(reversed(raw_db_messages)) if order_upper == "DESC" else raw_db_messages
        )

        # Optionally accept a pre-fetched character first_message to avoid a DB hit
        char_first_message_processed: Optional[str] = None
        if isinstance(char_first_message_hint, str) and char_first_message_hint.strip():
            char_first_message_processed = replace_placeholders(
                char_first_message_hint,
                character_name,
                user_name,
            ).strip()
        else:
            try:
                char_card = db.get_character_card_by_name(character_name)
                if char_card and isinstance(char_card.get("first_message"), str):
                    char_first_message_processed = replace_placeholders(
                        char_card["first_message"],
                        character_name,
                        user_name,
                    ).strip()
            except CharactersRAGDBError:
                char_first_message_processed = None
            except Exception:
                char_first_message_processed = None

        rich_history = process_db_messages_to_rich_ui_history(
            messages_for_processing,
            char_name_from_card=character_name,
            user_name_for_placeholders=user_name,
            actual_user_sender_id_in_db="User",
            actual_char_sender_id_in_db=character_name,
            additional_char_sender_ids=additional_aliases,
            additional_user_sender_ids=extra_user_aliases,
            char_first_message=char_first_message_processed,
            keep_trailing_user=not rich_output,
        )

        if order_upper == "DESC":
            rich_history = list(reversed(rich_history))

        if rich_output:
            return rich_history

        processed_ui_history = []
        for turn in rich_history:
            user_content = turn["user"]["content"] if turn["user"] else None
            character_content = None
            if turn["character"]:
                character_content = turn["character"]["content"]
            elif turn["non_character"]:
                character_content = turn["non_character"]["content"]
            processed_ui_history.append((user_content, character_content))
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
            logger.info("Edited message {}", message_id)
        else:
            logger.warning(
                "Failed to edit message %s - version mismatch or message not found",
                message_id,
            )
        return bool(success)
    except (CharactersRAGDBError, InputError, ConflictError) as exc:
        logger.error("Failed to edit content for message ID {}: {}", message_id, exc)
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
        logger.error("Failed to set ranking for message ID {}: {}", message_id, exc)
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
        logger.error("Failed to remove message ID {}: {}", message_id, exc)
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
