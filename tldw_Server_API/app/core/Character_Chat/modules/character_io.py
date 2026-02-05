"""
Character I/O operations module.

This module contains functions for importing and exporting character cards.
"""

import base64
import binascii
import io
import json
import os
import struct
import time
import uuid
import zlib
from typing import Any, Optional, Union

import yaml
from loguru import logger
from PIL import Image

from tldw_Server_API.app.core.Character_Chat.character_limits import get_character_limits
from tldw_Server_API.app.core.Character_Chat.constants import MAX_PNG_METADATA_BYTES
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)

# Import validation and parsing functions from character_validation module
from . import character_validation as _character_validation

# Import database functions from character_db module
from .character_db import create_new_character_from_data


class DatabaseCountError(CharactersRAGDBError):
    """Raised when counting messages for a conversation fails."""

    def __init__(self, conversation_id: Union[str, int, None], original_exception: Exception) -> None:
        message = f"Failed to count messages for conversation {conversation_id}: {original_exception}"
        super().__init__(message)
        self.conversation_id = conversation_id
        self.original_exception = original_exception


def extract_json_from_image_file(image_file_input: Union[str, bytes, io.BytesIO]) -> Optional[str]:
    """Extracts 'chara' metadata (Base64 encoded JSON) from an image file.

    Typically used for PNG character cards (e.g., TavernAI format) that embed
    character data in a 'chara' metadata chunk.

    Args:
        image_file_input (Union[str, bytes, io.BytesIO]): The image data,
            which can be a file path (str), raw image bytes, or a BytesIO stream.

    Returns:
        Optional[str]: The decoded JSON string from the 'chara' metadata if
        found, valid, and successfully decoded. Returns None if the 'chara'
        metadata is not found, the image cannot be processed, or if there's
        an error during decoding or JSON validation.
    """
    file_name_for_log = "image_stream"

    def _create_image_source() -> tuple[Optional[io.BytesIO], Optional[bytes], str]:
        """Create BytesIO source from various input types. Returns (source, raw_bytes, filename)."""
        nonlocal file_name_for_log
        raw_bytes: Optional[bytes] = None
        if isinstance(image_file_input, str) and os.path.exists(image_file_input):
            file_name_for_log = image_file_input
            with open(image_file_input, 'rb') as f_bytes:
                raw_bytes = f_bytes.read()
        elif isinstance(image_file_input, bytes):
            raw_bytes = image_file_input
        elif hasattr(image_file_input, 'read'):  # File-like object
            if hasattr(image_file_input, 'name') and image_file_input.name:
                file_name_for_log = image_file_input.name
            try:
                image_file_input.seek(0)
            except Exception:
                pass
            raw_bytes = image_file_input.read()
            try:
                image_file_input.seek(0)  # Reset original stream pointer
            except Exception:
                pass
        else:
            logger.error("extract_json_from_image_file: Invalid input type. Must be file path, bytes, or BytesIO.")
            return None, None, file_name_for_log

        if not raw_bytes:
            logger.error("extract_json_from_image_file: No image data provided.")
            return None, None, file_name_for_log
        return io.BytesIO(raw_bytes), raw_bytes, file_name_for_log

    def _normalize_key(raw_key: Any) -> str:
        if isinstance(raw_key, bytes):
            return raw_key.decode('utf-8', errors='replace').lower()
        return str(raw_key).lower()

    def _try_parse_json_text(raw_text: str) -> Optional[str]:
        trimmed = raw_text.strip()
        if not trimmed:
            return None
        if trimmed.startswith("data:") and "base64," in trimmed:
            trimmed = trimmed.split("base64,", 1)[1].strip()
        if trimmed[:1] in ("{", "["):
            try:
                json.loads(trimmed)
                return trimmed
            except json.JSONDecodeError:
                return None
        return None

    def _try_base64_json(raw_value: Union[str, bytes], context_label: Optional[str] = None) -> Optional[str]:
        if isinstance(raw_value, str):
            normalized = "".join(raw_value.split())
            if normalized.startswith("data:") and "base64," in normalized:
                normalized = normalized.split("base64,", 1)[1].strip()
            if not normalized:
                return None
            padded = normalized + ("=" * (-len(normalized) % 4))
            raw_bytes = padded
        else:
            raw_bytes = raw_value
        try:
            decoded = base64.b64decode(raw_bytes)
        except binascii.Error as exc:
            if context_label:
                logger.error(
                    f"Error decoding '{context_label}' metadata from '{file_name_for_log}': {exc}"
                )
            return None
        try:
            decoded_text = decoded.decode('utf-8').lstrip("\ufeff").strip()
        except UnicodeDecodeError as exc:
            if context_label:
                logger.error(
                    f"Error decoding '{context_label}' metadata from '{file_name_for_log}': {exc}"
                )
            return None
        if not decoded_text:
            return None
        try:
            json.loads(decoded_text)
            return decoded_text
        except json.JSONDecodeError as exc:
            if context_label:
                logger.error(
                    f"Error decoding '{context_label}' metadata from '{file_name_for_log}': {exc}"
                )
            return None

    def _decode_candidate_value(raw_value: Any, context_label: Optional[str] = None) -> Optional[str]:
        if raw_value is None:
            return None
        if isinstance(raw_value, dict):
            for sub_value in raw_value.values():
                decoded = _decode_candidate_value(sub_value, context_label=context_label)
                if decoded:
                    return decoded
            return None
        if isinstance(raw_value, (list, tuple)):
            for entry in raw_value:
                decoded = _decode_candidate_value(entry, context_label=context_label)
                if decoded:
                    return decoded
            return None
        if isinstance(raw_value, bytes):
            try:
                raw_text = raw_value.decode('utf-8')
                decoded = _try_parse_json_text(raw_text)
                if decoded:
                    return decoded
            except UnicodeDecodeError:
                pass
            return _try_base64_json(raw_value, context_label=context_label)
        if isinstance(raw_value, str):
            decoded = _try_parse_json_text(raw_value)
            if decoded:
                return decoded
            return _try_base64_json(raw_value, context_label=context_label)
        return None

    def _iter_metadata_items(metadata: dict[str, Any]) -> list[tuple[Any, Any]]:
        items: list[tuple[Any, Any]] = []
        for key, value in metadata.items():
            items.append((key, value))
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    items.append((sub_key, sub_value))
        return items

    def _extract_from_metadata_items(items: list[tuple[Any, Any]], source_label: str) -> Optional[str]:
        if not items:
            return None
        preferred_keys = {"chara", "character"}
        attempted_keys: set[str] = set()
        for key, value in items:
            normalized_key = _normalize_key(key)
            if normalized_key not in preferred_keys:
                continue
            attempted_keys.add(normalized_key)
            decoded = _decode_candidate_value(value, context_label=normalized_key)
            if decoded:
                logger.info(
                    f"Successfully extracted 'chara' JSON from '{file_name_for_log}' (key: {key}, source: {source_label})."
                )
                return decoded
        for key, value in items:
            if _normalize_key(key) in attempted_keys:
                continue
            decoded = _decode_candidate_value(value)
            if decoded:
                logger.info(
                    f"Successfully extracted character JSON from '{file_name_for_log}' (key: {key}, source: {source_label})."
                )
                return decoded
        available_keys = sorted({_normalize_key(key) for key, _ in items})
        logger.debug(
            f"No valid character data found in image metadata for '{file_name_for_log}' "
            f"(source: {source_label}). Available keys: {available_keys}"
        )
        return None

    def _extract_png_text_chunks(raw_bytes: bytes) -> dict[str, str]:
        if not raw_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            return {}
        pos = 8
        chunks: dict[str, str] = {}

        def _safe_decompress(data: bytes) -> Optional[bytes]:
            if not data:
                return b""
            try:
                max_bytes = MAX_PNG_METADATA_BYTES
                decompressor = zlib.decompressobj()
                chunk = decompressor.decompress(data, max_bytes + 1)
                if len(chunk) > max_bytes or decompressor.unconsumed_tail:
                    logger.warning("PNG metadata chunk exceeded max size (>{} bytes).", max_bytes)
                    return None
                chunk += decompressor.flush()
                if len(chunk) > max_bytes:
                    logger.warning("PNG metadata chunk exceeded max size after flush (>{} bytes).", max_bytes)
                    return None
                return chunk
            except Exception as exc:
                logger.debug("Failed to decompress PNG metadata chunk: {}", exc)
                return None

        while pos + 8 <= len(raw_bytes):
            length = struct.unpack(">I", raw_bytes[pos:pos + 4])[0]
            chunk_type = raw_bytes[pos + 4:pos + 8]
            data_start = pos + 8
            data_end = data_start + length
            if data_end + 4 > len(raw_bytes):
                break
            data = raw_bytes[data_start:data_end]
            pos = data_end + 4

            if chunk_type == b'tEXt':
                if b'\x00' not in data:
                    continue
                keyword, text = data.split(b'\x00', 1)
                if len(text) > MAX_PNG_METADATA_BYTES:
                    logger.warning("PNG tEXt metadata exceeded max size (>{} bytes).", MAX_PNG_METADATA_BYTES)
                    continue
                chunks[keyword.decode('latin-1', errors='ignore')] = text.decode('utf-8', errors='replace')
            elif chunk_type == b'zTXt':
                if b'\x00' not in data:
                    continue
                keyword, rest = data.split(b'\x00', 1)
                if not rest:
                    continue
                compression_method = rest[:1]
                compressed_text = rest[1:]
                if compression_method != b'\x00':
                    continue
                try:
                    text = _safe_decompress(compressed_text)
                    if text is None:
                        continue
                    chunks[keyword.decode('latin-1', errors='ignore')] = text.decode('utf-8', errors='replace')
                except Exception:
                    continue
            elif chunk_type == b'iTXt':
                parts = data.split(b'\x00', 5)
                if len(parts) < 6:
                    continue
                keyword = parts[0].decode('latin-1', errors='ignore')
                compression_flag = parts[1][:1]
                compression_method = parts[2][:1]
                text = parts[5]
                if compression_flag == b'\x01':
                    if compression_method != b'\x00':
                        continue
                    try:
                        text = _safe_decompress(text)
                        if text is None:
                            continue
                    except Exception:
                        continue
                if len(text) > MAX_PNG_METADATA_BYTES:
                    logger.warning("PNG iTXt metadata exceeded max size (>{} bytes).", MAX_PNG_METADATA_BYTES)
                    continue
                chunks[keyword] = text.decode('utf-8', errors='replace')
        return chunks

    def _extract_from_png_bytes(raw_bytes: Optional[bytes]) -> Optional[str]:
        if not raw_bytes:
            return None
        try:
            chunks = _extract_png_text_chunks(raw_bytes)
        except Exception as e:
            logger.debug(f"Failed to parse PNG text chunks for '{file_name_for_log}': {e}")
            return None
        if not chunks:
            return None
        return _extract_from_metadata_items(list(chunks.items()), "png-chunks")

    def _extract_metadata(img_obj: Image.Image, raw_bytes: Optional[bytes]) -> Optional[str]:
        metadata_sources: list[tuple[str, dict[str, Any]]] = []
        if hasattr(img_obj, 'info') and isinstance(img_obj.info, dict):
            metadata_sources.append(("info", img_obj.info))
        text_metadata = getattr(img_obj, 'text', None)
        if isinstance(text_metadata, dict):
            metadata_sources.append(("text", text_metadata))

        if not metadata_sources:
            return _extract_from_png_bytes(raw_bytes)

        for label, metadata in metadata_sources:
            decoded = _extract_from_metadata_items(_iter_metadata_items(metadata), label)
            if decoded:
                return decoded
        return _extract_from_png_bytes(raw_bytes)

    try:
        image_source, raw_bytes, file_name_for_log = _create_image_source()
        if image_source is None:
            return None

        logger.debug(f"Attempting to extract JSON from image: {file_name_for_log}")

        # Use context managers for proper resource cleanup (fallback for mocks without __enter__)
        try:
            with image_source:
                img_obj = Image.open(image_source)
                if hasattr(img_obj, "__enter__") and hasattr(img_obj, "__exit__"):
                    with img_obj as opened:
                        if opened.format not in ['PNG', 'WEBP']:
                            logger.warning(
                                f"Image '{file_name_for_log}' is not in PNG or WEBP format "
                                f"(format: {opened.format}). 'chara' metadata extraction may fail.")

                        result = _extract_metadata(opened, raw_bytes)
                        if result:
                            return result
                        return None

                try:
                    if img_obj.format not in ['PNG', 'WEBP']:
                        logger.warning(
                            f"Image '{file_name_for_log}' is not in PNG or WEBP format "
                            f"(format: {img_obj.format}). 'chara' metadata extraction may fail.")

                    return _extract_metadata(img_obj, raw_bytes)
                finally:
                    if hasattr(img_obj, "close"):
                        try:
                            img_obj.close()
                        except Exception:
                            pass
        except OSError as e:
            # Catches PIL.UnidentifiedImageError and other file I/O issues
            logger.error(
                f"Cannot open or read image file (or not a valid image): {file_name_for_log}. Error: {e}",
                exc_info=True)
            fallback = _extract_from_png_bytes(raw_bytes)
            if fallback:
                return fallback
            return None

    except FileNotFoundError:
        logger.error(f"Image file not found for JSON extraction: {file_name_for_log}")
    except Exception as e:
        logger.error(f"Unexpected error extracting JSON from image '{file_name_for_log}': {e}", exc_info=True)
    return None


def import_character_card_from_json_string(json_content_str: str) -> Optional[dict[str, Any]]:
    """Imports and parses a character card from a JSON string.

    This function attempts to parse a character card from the provided JSON
    string. It automatically detects whether the card is V1 or V2 format.
    For V2 cards (identified by 'spec' or 'spec_version' fields, or
    heuristically by a 'data' node), it performs V2 structural validation.
    If V2 processing fails or is not applicable, it attempts V1 parsing.
    The parsed data is then mapped to a dictionary with keys corresponding
    to the application's database schema.

    Args:
        json_content_str (str): A string containing the character card data
            in JSON format.

    Returns:
        Optional[Dict[str, Any]]: A dictionary with character data mapped to
        DB schema field names (e.g., 'first_message', 'message_example') if
        parsing and validation are successful. Returns None if the JSON is
        invalid, the card structure is unrecognized, critical fields are
        missing (like 'name' after parsing), or any other parsing error occurs.
    """
    if not json_content_str or not json_content_str.strip():
        logger.error("JSON content string is empty or whitespace.")
        return None
    try:
        card_data_dict = json.loads(json_content_str.strip())

        parsed_card: Optional[dict[str, Any]] = None

        # Enhanced format detection supporting more character card formats
        # Check for various format indicators
        # Character Card v3 explicit markers
        is_explicit_v3_spec = card_data_dict.get('spec') == 'chara_card_v3'
        is_explicit_v3_version = str(card_data_dict.get('spec_version', '')).startswith("3.")

        is_explicit_v2_spec = card_data_dict.get('spec') == 'chara_card_v2'
        is_explicit_v2_version_str = str(card_data_dict.get('spec_version', ''))
        is_explicit_v2_version = is_explicit_v2_version_str.startswith("2.")

        # Check for Tavern/SillyTavern format
        has_tavern_fields = all(field in card_data_dict for field in ['name', 'description', 'first_mes'])

        # Check for Pygmalion format
        has_pygmalion_fields = 'char_name' in card_data_dict and 'char_persona' in card_data_dict

        # Check for Text Generation WebUI format
        has_textgen_fields = 'context' in card_data_dict and 'greeting' in card_data_dict

        # Check for Alpaca/instruction format
        has_alpaca_fields = 'instruction' in card_data_dict or 'input' in card_data_dict

        has_data_node_heuristic = isinstance(card_data_dict.get('data'), dict) and \
                                  'name' in card_data_dict['data']  # Heuristic for implicit V2

        # Try V3 first if explicitly marked
        if is_explicit_v3_spec or is_explicit_v3_version:
            logger.debug("Attempting V3 validation based on card structure/spec.")
            try:
                from tldw_Server_API.app.core.Character_Chat.ccv3_parser import parse_v3_card, validate_v3_card
                is_valid_v3_struct, v3_errors = validate_v3_card(card_data_dict)
                if is_valid_v3_struct:
                    parsed_card = parse_v3_card(card_data_dict)
                    if parsed_card and parsed_card.get('name'):
                        logger.info("V3 card parsed successfully.")
                    else:
                        logger.warning("V3 parsing failed after validation; will try other formats.")
                else:
                    logger.warning(f"V3 validation failed: {'; '.join(v3_errors)}; falling back.")
            except Exception as e:
                logger.warning(f"V3 parsing import failed or not available: {e}")

        attempt_v2_processing = (parsed_card is None) and (
            is_explicit_v2_spec
            or is_explicit_v2_version
            or (has_data_node_heuristic and not is_explicit_v2_spec and not is_explicit_v2_version)
        )

        if attempt_v2_processing:
            logger.debug("Attempting V2 validation based on card structure/spec.")
            strict_spec = bool(is_explicit_v2_spec or is_explicit_v2_version)
            is_valid_v2_struct, v2_errors = _character_validation.validate_v2_card(
                card_data_dict,
                strict_spec=strict_spec,
            )

            if not is_valid_v2_struct:
                logger.error(f"V2 Card structural validation failed: {'; '.join(v2_errors)}.")
                if is_explicit_v2_spec or is_explicit_v2_version:
                    logger.error("Card explicitly declared as V2 but failed V2 structural validation. Import aborted.")
                    return None
                else:  # Implicit V2 guess failed validation
                    logger.warning(
                        "Heuristically identified V2 card failed V2 structural validation. Will attempt V1 parsing as fallback.")
                    # No 'return None' here, proceed to V1 attempt below
            else:  # V2 structural validation passed
                logger.info("V2 Card structural validation passed. Attempting to parse as V2 character card.")
                parsed_card = _character_validation.parse_v2_card(card_data_dict)
                if not parsed_card:
                    logger.warning(
                        "V2 parsing failed despite passing V2 structural validation. This might indicate an issue with the parser or an edge case. Attempting V1 parsing as fallback.")
                    # `parsed_card` is None, will fall through to V1 attempt

        # Try other known formats before falling back to V1
        if parsed_card is None:
            # Try Pygmalion format
            if has_pygmalion_fields:
                logger.info("Attempting to parse as Pygmalion format character card.")
                parsed_card = _character_validation.parse_pygmalion_card(card_data_dict)

            # Try Text Generation WebUI format
            elif has_textgen_fields:
                logger.info("Attempting to parse as Text Generation WebUI format character card.")
                parsed_card = _character_validation.parse_textgen_card(card_data_dict)

            # Try Alpaca/instruction format
            elif has_alpaca_fields:
                logger.info("Attempting to parse as Alpaca/instruction format.")
                parsed_card = _character_validation.parse_alpaca_card(card_data_dict)

        # Fallback to V1 if other formats didn't work
        if parsed_card is None:
            logger.info("Attempting to parse as V1 character card.")
            try:
                # parse_v1_card raises ValueError if required fields are missing, or returns None on other errors
                parsed_card = _character_validation.parse_v1_card(card_data_dict)
            except ValueError as ve_v1:
                logger.error(f"V1 card parsing error (likely missing required V1 fields): {ve_v1}")
                parsed_card = None  # Ensure parsed_card is None on this error

        # Final check and return
        if parsed_card and parsed_card.get('name'):  # Name is fundamental
            logger.info(f"Successfully parsed card: '{parsed_card.get('name')}'")
            return parsed_card
        else:
            if parsed_card and not parsed_card.get('name'):
                logger.error("Parsed card is missing 'name'. Import failed.")
            else:  # parsed_card is None
                logger.error("All parsing attempts (V2 and V1) failed to produce a valid card.")
            return None

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error from string: {e}. Content (start): {json_content_str[:150]}...")
    except Exception as e:  # Catch any other unexpected errors during the process
        logger.error(f"Unexpected error parsing card from JSON string: {e}", exc_info=True)
    return None


def load_character_card_from_string_content(content_str: str) -> Optional[dict[str, Any]]:
    """Load a character card from a string (JSON or YAML format).

    Args:
        content_str: The string content containing character data

    Returns:
        Parsed character data dictionary, or None on error
    """
    if not content_str or not content_str.strip():
        logger.error("Content string is empty or whitespace.")
        return None

    trimmed_content = content_str.lstrip()
    treat_as_frontmatter = trimmed_content.startswith("---")

    # Try JSON first when content doesn't look like YAML frontmatter
    if not treat_as_frontmatter:
        try:
            parsed = import_character_card_from_json_string(content_str)
            if parsed:
                return parsed
        except Exception:
            logger.debug("Failed JSON parsing attempt for character card string.", exc_info=True)

    # Try YAML
    try:
        yaml_data = yaml.safe_load(content_str)
        if isinstance(yaml_data, dict):
            json_str = json.dumps(yaml_data)
            parsed_from_yaml = import_character_card_from_json_string(json_str)
            if parsed_from_yaml:
                return parsed_from_yaml
    except ImportError:
        # Surface import errors (e.g., yaml not installed)
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML frontmatter: {e}")
    except Exception as e:
        logger.error(f"Unexpected error parsing YAML content: {e}", exc_info=True)

    # Fallback: treat the raw content as a plain-text description
    unique_name = f"Character {uuid.uuid4().hex[:8]}"
    fallback_payload = {
        "name": unique_name,
        "description": content_str,
        "personality": content_str[:500] or "Plain text import",
        "scenario": "Imported from plain text",
        "first_mes": "Hello! I'm a character created from plain text content.",
        "mes_example": "User: Hello\nCharacter: Hi there! Let's continue from your notes.",
        "tags": ["plain-text"],
    }
    try:
        return import_character_card_from_json_string(json.dumps(fallback_payload))
    except Exception as e:
        logger.error(f"Unexpected error parsing content: {e}", exc_info=True)
        return None


def _infer_character_name_from_filename(file_name: Optional[str]) -> str:
    if not file_name:
        return "Imported Character"
    base_name = os.path.basename(file_name)
    base_name = os.path.splitext(base_name)[0]
    if base_name.lower().endswith(".card"):
        base_name = base_name[:-5]
    base_name = base_name.replace("_", " ").replace("-", " ").strip()
    base_name = " ".join(base_name.split())
    return base_name or "Imported Character"


def _build_image_only_character(file_name: Optional[str], image_bytes: Optional[bytes]) -> dict[str, Any]:
    name = _infer_character_name_from_filename(file_name)
    payload: dict[str, Any] = {
        "name": name,
        "description": "Imported from image file without embedded character data.",
        "personality": "Image-only import.",
        "scenario": "Imported from image file.",
        "first_message": f"Hello! I'm {name}.",
        "message_example": "User: Hello\nCharacter: Hi there! I was imported from an image.",
        "tags": ["image-only-import"],
        "extensions": {"image_only_import": True},
    }
    if image_bytes:
        payload["image"] = image_bytes
    return payload


def import_and_save_character_from_file(
    db: CharactersRAGDB,
    file_path: Optional[str] = None,
    file_content: Optional[Union[str, bytes]] = None,
    file_type: Optional[str] = None,
    file_name: Optional[str] = None,
    allow_image_only: bool = False
) -> tuple[bool, str, Optional[int]]:
    """Import and save a character from a file.

    Args:
        db: Database instance
        file_path: Path to the file (optional if file_content provided)
        file_content: File content (optional if file_path provided)
        file_type: File type hint ('json', 'png', 'yaml', etc.)
        file_name: Optional file name hint (used for image-only fallbacks)
        allow_image_only: Whether to allow image-only imports when metadata is missing

    Returns:
        Tuple of (success, message, character_id)
    """
    try:
        parsed_card = None
        import_message = None
        name_hint = file_name or file_path

        # Determine file type
        if file_path:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in ['.png', '.webp', '.jpg', '.jpeg']:
                file_type = 'image'
            elif file_ext in ['.json']:
                file_type = 'json'
            elif file_ext in ['.yaml', '.yml']:
                file_type = 'yaml'

        # Handle different file types
        if file_type == 'image' or (file_path and file_path.lower().endswith(('.png', '.webp'))):
            # Try to extract JSON from image metadata
            if file_path:
                json_str = extract_json_from_image_file(file_path)
                try:
                    with open(file_path, 'rb') as image_file_obj:
                        original_image_bytes = image_file_obj.read()
                except Exception:
                    original_image_bytes = None
            elif file_content and isinstance(file_content, bytes):
                json_str = extract_json_from_image_file(file_content)
                original_image_bytes = file_content
            else:
                return False, "Image file requires bytes content or file path", None

            if json_str:
                parsed_card = import_character_card_from_json_string(json_str)
                if parsed_card is not None and original_image_bytes:
                    parsed_card["image"] = original_image_bytes
                    parsed_card.pop("image_base64", None)
            else:
                if original_image_bytes:
                    if allow_image_only:
                        parsed_card = _build_image_only_character(name_hint, original_image_bytes)
                        import_message = (
                            "No character data found in image metadata; imported image-only character."
                        )
                    else:
                        return False, "missing_character_data", None
                else:
                    return False, "No character data found in image metadata", None

        elif file_type in ['json', 'yaml', 'text'] or file_content:
            # Handle text-based formats
            if file_content:
                if isinstance(file_content, bytes):
                    content_str = file_content.decode('utf-8')
                else:
                    content_str = file_content
            elif file_path:
                with open(file_path, encoding='utf-8') as f:
                    content_str = f.read()
            else:
                return False, "No file content or path provided", None

            parsed_card = load_character_card_from_string_content(content_str)

        else:
            return False, f"Unsupported file type: {file_type}", None

        # Save to database if parsing successful
        if parsed_card:
            character_id = create_new_character_from_data(db, parsed_card)
            if character_id:
                character_name = parsed_card.get('name', 'Unknown')
                return True, import_message or f"Successfully imported character '{character_name}'", character_id
            else:
                return False, "Failed to save character to database", None
        else:
            return False, "Failed to parse character data from file", None

    except FileNotFoundError:
        return False, f"File not found: {file_path}", None
    except UnicodeDecodeError as e:
        return False, f"Failed to decode file content: {e}", None
    except Exception as e:
        logger.error(f"Unexpected error importing character: {e}", exc_info=True)
        return False, f"Unexpected error: {str(e)}", None


def load_chat_history_from_file_and_save_to_db(
    db: CharactersRAGDB,
    character_id: int,
    file_path: Optional[str] = None,
    file_content: Optional[str] = None,
    title: Optional[str] = None,
    user_name_for_placeholders: Optional[str] = None,
) -> tuple[Optional[str], Optional[int]]:
    """Load chat history from a file and persist it for the given character.

    Historically this returned ``(conversation_id, character_id)``; the behaviour
    is preserved for compatibility with existing callers and tests.

    Args:
        db: Database instance.
        character_id: Identifier for the character that owns the chat history.
        file_path: Optional filesystem path to the chat export.
        file_content: Optional in-memory chat export (JSON/YAML/plain text).
        title: Optional title to apply to the created conversation; if omitted a
            timestamped title is generated.
        user_name_for_placeholders: Optional user name used when replacing
            placeholder tokens.

    Returns:
        Tuple of (conversation_id, character_id) on success, otherwise (None, None).

    Raises:
        DatabaseCountError: If the message count lookup fails during import.
    """
    try:
        # Load content from path or provided string
        if file_content is not None:
            content = file_content
        elif file_path:
            with open(file_path, encoding="utf-8") as file_obj:
                content = file_obj.read()
        else:
            logger.error("No chat history source provided (file_path or file_content required).")
            return None, None

        # Parse content - prefer JSON, fall back to YAML, finally treat as plain text
        def _normalise_chat_data(raw_data: Any) -> Optional[dict[str, Any]]:
            if isinstance(raw_data, dict):
                return raw_data
            if isinstance(raw_data, list):
                return {"messages": raw_data}
            if raw_data is None:
                return None
            if isinstance(raw_data, str):
                if not raw_data.strip():
                    return None
                return {"messages": [{"role": "user", "content": raw_data}]}
            # Fallback: coerce to string representation
            coerced = str(raw_data).strip()
            if not coerced:
                return None
            return {"messages": [{"role": "user", "content": coerced}]}

        chat_data_raw: Any = None
        try:
            chat_data_raw = json.loads(content)
        except json.JSONDecodeError:
            try:
                chat_data_raw = yaml.safe_load(content)
            except Exception:
                chat_data_raw = None

        chat_data = _normalise_chat_data(chat_data_raw)
        if not chat_data:
            chat_data = {"messages": [{"role": "user", "content": content}]}

        # Resolve placeholders and conversation metadata
        inferred_user_name = user_name_for_placeholders or chat_data.get("user_name")
        inferred_char_name = chat_data.get("char_name")

        if not title:
            title = f"Imported Chat - {time.strftime('%Y-%m-%d %H:%M:%S')}"

        def _normalize_message_content(raw_content: Any) -> Optional[str]:
            """Flatten structured message content into a plain string when possible."""

            collected_parts: list[str] = []
            appended_via_fallback = False

            def _collect(item: Any) -> None:
                nonlocal appended_via_fallback
                if item is None:
                    return
                if isinstance(item, str):
                    if item:
                        collected_parts.append(item)
                    return
                if isinstance(item, (list, tuple)):
                    for sub_item in item:
                        _collect(sub_item)
                    return
                if isinstance(item, dict):
                    # Common structured keys from OpenAI/Anthropic/Gemini payloads
                    for key in (
                        "text",
                        "content",
                        "value",
                        "message",
                        "data",
                        "input_text",
                        "output_text",
                    ):
                        if key in item:
                            _collect(item[key])

                    if "parts" in item:
                        _collect(item["parts"])
                    if "arguments" in item:
                        try:
                            collected_parts.append(json.dumps(item["arguments"], ensure_ascii=False))
                            appended_via_fallback = True
                        except Exception:
                            pass
                    if "children" in item:
                        _collect(item["children"])

                    # If nothing was gathered, fall back to serialising the dict for traceability.
                    if not collected_parts:
                        try:
                            collected_parts.append(json.dumps(item, ensure_ascii=False))
                            appended_via_fallback = True
                        except Exception:
                            collected_parts.append(str(item))
                    return

                collected_parts.append(str(item))

            _collect(raw_content)
            if not collected_parts:
                return None

            combined = "\n".join(part for part in (segment.strip("\n") for segment in collected_parts) if part)
            combined = combined.strip()
            if combined:
                return combined

            if appended_via_fallback:
                return None
            return None

        user_aliases_for_resolution: set[str] = {"user", "human", "speaker", "speaker1", "speaker 1", "speaker-1"}
        if inferred_user_name:
            user_aliases_for_resolution.add(str(inferred_user_name).strip().lower())

        def _resolve_sender(role_value: Any, entry_data: Any) -> tuple[bool, Optional[str]]:
            """Determine whether a message is from the user and capture explicit role labels."""
            if role_value is None:
                return True, None

            normalized = str(role_value).strip()
            if not normalized:
                return True, None

            lowered = normalized.lower()
            if lowered in user_aliases_for_resolution:
                return True, None

            character_aliases = {
                "assistant",
                "bot",
                "ai",
                "character",
            }
            if inferred_char_name:
                character_aliases.add(str(inferred_char_name).strip().lower())

            if lowered in character_aliases:
                return False, None

            if lowered == "system":
                return False, "system"

            if lowered in {"tool", "function"}:
                tool_name: Optional[str] = None
                if isinstance(entry_data, dict):
                    tool_name = entry_data.get("name") or entry_data.get("tool_name") or entry_data.get("tool", None)
                    if not tool_name:
                        function_details = entry_data.get("function")
                        if isinstance(function_details, dict):
                            tool_name = function_details.get("name") or function_details.get("type")
                    if not tool_name:
                        tool_calls = entry_data.get("tool_calls")
                        if isinstance(tool_calls, list) and tool_calls:
                            first_call = tool_calls[0]
                            if isinstance(first_call, dict):
                                tool_name = first_call.get("name")
                                if not tool_name and isinstance(first_call.get("function"), dict):
                                    tool_name = first_call["function"].get("name")
                sender_label = f"{lowered}:{tool_name}" if tool_name else lowered
                return False, sender_label

            # Preserve unknown roles explicitly so downstream can inspect them.
            return False, normalized

        from .character_chat import post_message_to_conversation, start_new_chat_session
        (
            conversation_id,
            char_data,
            _initial_ui_history,
            _image,
        ) = start_new_chat_session(
            db,
            character_id,
            inferred_user_name,
            custom_title=title,
        )

        if not conversation_id:
            logger.error("Failed to create conversation while importing chat history.")
            return None, None

        character_name = (char_data or {}).get("name") or inferred_char_name or "Character"
        user_name = inferred_user_name or "User"

        def _cleanup_failed_import() -> None:
            try:
                convo_meta = db.get_conversation_by_id(conversation_id)
                if not convo_meta:
                    return
                version = convo_meta.get("version", 1)
                if not isinstance(version, int):
                    version = 1
                db.soft_delete_conversation(conversation_id, version)
            except (CharactersRAGDBError, ConflictError) as cleanup_exc:
                logger.warning(
                    "Non-fatal: failed to clean up conversation %s after import failure: %s",
                    conversation_id,
                    cleanup_exc,
                )
            except Exception as cleanup_exc:
                logger.warning(
                    "Unexpected error while cleaning up conversation %s after import failure: %s",
                    conversation_id,
                    cleanup_exc,
                )

        try:
            # New conversations created via the facade may contain an auto-generated
            # greeting. Remove any pre-seeded messages so the imported history is the
            # sole content.
            try:
                seeded_messages = db.get_messages_for_conversation(conversation_id, limit=50)
            except CharactersRAGDBError as fetch_exc:
                logger.debug(
                    "Unable to inspect seeded messages for conversation %s: %s",
                    conversation_id,
                    fetch_exc,
                )
                seeded_messages = []

            for seeded_msg in seeded_messages:
                try:
                    db.soft_delete_message(seeded_msg["id"], seeded_msg.get("version", 1))
                except (CharactersRAGDBError, ConflictError) as delete_exc:
                    logger.debug(
                        "Non-fatal: failed to remove seeded message %s from conversation %s during import: %s",
                        seeded_msg.get("id"),
                        conversation_id,
                        delete_exc,
                    )

            messages_added = 0
            try:
                current_message_count = db.count_messages_for_conversation(conversation_id)
            except Exception as exc:
                logger.error(
                    "Failed to count messages for conversation {}: {}",
                    conversation_id,
                    exc,
                    exc_info=True,
                )
                raise DatabaseCountError(conversation_id, exc) from exc

            limits = get_character_limits()
            max_messages_per_chat = getattr(limits, "max_messages_per_chat", 0) or 0

            def _add_message_to_conversation(
                message_text: str,
                is_user_message: bool,
                sender_override: Optional[str],
            ) -> None:
                nonlocal messages_added, current_message_count
                if max_messages_per_chat and current_message_count >= max_messages_per_chat:
                    raise InputError(
                        f"Message limit exceeded. Maximum {max_messages_per_chat} messages per chat."
                    )
                post_message_to_conversation(
                    db=db,
                    conversation_id=conversation_id,
                    character_name=character_name,
                    message_content=message_text,
                    is_user_message=is_user_message,
                    sender_override=sender_override,
                )
                messages_added += 1
                current_message_count += 1

            # Helper to process pair-based history entries (legacy export format)
            def _process_pair_history(entries: list[Any]) -> None:
                for idx, entry in enumerate(entries):
                    if not isinstance(entry, (list, tuple)):
                        logger.warning("Skipping malformed message pair at index {}: not a list", idx)
                        continue

                    if len(entry) > 2:
                        logger.warning(
                            "Skipping malformed message pair at index {}: expected at most 2 elements, got {}",
                            idx,
                            len(entry),
                        )
                        continue

                    user_chunk_raw = entry[0] if len(entry) > 0 else None
                    char_chunk_raw = entry[1] if len(entry) > 1 else None

                    user_chunk = _normalize_message_content(user_chunk_raw) if user_chunk_raw is not None else None
                    char_chunk = _normalize_message_content(char_chunk_raw) if char_chunk_raw is not None else None

                    if user_chunk:
                        _add_message_to_conversation(user_chunk, True, None)
                    if char_chunk:
                        _add_message_to_conversation(char_chunk, False, None)
                    if not user_chunk and not char_chunk:
                        logger.warning("Skipping malformed message pair at index {}: empty or non-string values", idx)

            history_node = chat_data.get("history")
            if isinstance(history_node, dict) and isinstance(history_node.get("internal"), list):
                _process_pair_history(history_node["internal"])
            else:
                messages = chat_data.get("messages", [])
                if isinstance(messages, list):
                    for entry in messages:
                        if isinstance(entry, dict):
                            raw_content = entry.get("content")
                            normalized_content = _normalize_message_content(raw_content)
                            if normalized_content is None or not normalized_content.strip():
                                logger.warning("Skipping message with empty or invalid content: {}", entry)
                                continue
                            is_user, sender_override = _resolve_sender(entry.get("role"), entry)
                            if sender_override and sender_override.lower() == "system" and not normalized_content.strip():
                                logger.debug(
                                    "System message with empty content skipped for conversation import: {}",
                                    entry,
                                )
                                continue
                            _add_message_to_conversation(normalized_content, is_user, sender_override)
                        else:
                            logger.warning("Skipping malformed message entry (expected dict): {}", entry)

            if messages_added == 0:
                logger.info("Chat history import completed but contained no valid messages.")

            return conversation_id, character_id
        except Exception:
            _cleanup_failed_import()
            raise

    except DatabaseCountError:
        raise
    except Exception as exc:
        logger.error("Error loading chat history: {}", exc, exc_info=True)
        return None, None
