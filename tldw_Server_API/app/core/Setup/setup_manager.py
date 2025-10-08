"""Utilities for managing the first-time setup flow.

This module centralises reading and writing of the main ``config.txt`` file so the
first-time setup experience can query and update configuration without duplicating
file handling logic across routers or UI layers.
"""

from __future__ import annotations

import re
import shutil
from configparser import ConfigParser
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

SETUP_SECTION = "Setup"
CONFIG_FILENAME = "config.txt"
CONFIG_RELATIVE_PATH = Path("Config_Files") / CONFIG_FILENAME

SENSITIVE_KEY_MARKERS = ("key", "token", "secret", "password", "api_key")
PLACEHOLDER_VALUES = {
    "",
    "your_api_key_here",
    "YOUR_API_KEY_HERE",
    "default-secret-key-for-single-user",
    "CHANGE_ME_TO_SECURE_API_KEY",
    "ChangeMeStrong123!",
    "change-me-in-production",
}

SECTION_LABELS: Dict[str, str] = {
    "API": "API Providers",
    "Processing": "Processing",
    "Media-Processing": "Media Processing",
    "Server": "Server Settings",
    "Chat-Module": "Chat Module",
    "Character-Chat": "Character Chat",
    "Chat-Dictionaries": "Chat Dictionaries",
    "Settings": "General Settings",
    "Auto-Save": "Auto-Save",
    "Database": "Database",
    "AuthNZ": "Authentication",
    "Embeddings": "Embeddings",
    "RAG": "Retrieval Augmented Generation",
    "Chunking": "Chunking",
    "STT-Settings": "Speech-to-Text",
    "TTS-Settings": "Text-to-Speech",
    "Logging": "Logging",
    "Setup": "Setup",
    "Prompts": "Prompts",
    "Search-Engines": "Search Engines",
    "Local-API": "Local API Providers",
    "Claims": "Claims Extraction",
    "MCP": "Model Context Protocol",
    "MCP-Unified": "MCP Unified",
}

SECTION_DESCRIPTIONS: Dict[str, str] = {
    "Setup": "Controls the guided setup flow shown on first launch.",
    "AuthNZ": "Configure authentication mode and credentials.",
    "API": "Add API keys for the providers you plan to use.",
    "Server": "Server-level behaviour toggles.",
    "Database": "Manage database storage locations and options.",
    "Embeddings": "Configure embedding providers and defaults.",
    "RAG": "Tune retrieval and augmentation behaviour.",
    "Logging": "Adjust logging paths and verbosity.",
    "Processing": "Base ingestion defaults such as preferred hardware and general processing strategy.",
    "Media-Processing": "Control file-size limits, conversion timeouts, and media ingestion safeguards.",
    "Settings": "Miscellaneous server toggles, retention policies, and behavioural guards.",
    "Auto-Save": "Persistence defaults for chats, notes, and other artefacts.",
    "Chat-Module": "Primary chat flow defaults including rate limits, streaming, and fallbacks.",
    "Character-Chat": "Persona chat controls, limits, and import behaviour.",
    "Chunking": "Adjust chunking defaults, overlap, and adaptive strategies for ingested documents.",
    "Prompts": "Manage reusable prompt templates for summarisation, chat, and automation.",
    "Search-Engines": "Configure search providers, query budgets, and language preferences.",
    "Local-API": "Point to locally hosted model backends such as Ollama or Kobold.",
    "Claims": "Control ingestion-time claim extraction and rebuild workers.",
    "MCP": "Configure Model Context Protocol hosts, tokens, and available tool sets.",
    "MCP-Unified": "Manage the unified MCP service, registry, and role-based access.",
    "Chat-Dictionaries": "Enable and configure dictionary-based replacements in chat flows.",
    "STT-Settings": "Speech-to-text providers, streaming, and buffering controls.",
    "TTS-Settings": "Voice synthesis providers, defaults, and output configuration.",
}

FIELD_HINTS: Dict[Tuple[str, str], str] = {
    ("AuthNZ", "single_user_api_key"): "Strong secret used for X-API-KEY requests in single-user mode.",
    ("AuthNZ", "auth_mode"): "Use 'single_user' for local setups or 'multi_user' for JWT-based auth.",
    ("API", "openai_api_key"): "Personal or organisational OpenAI key.",
    ("API", "anthropic_api_key"): "Anthropic Claude API key.",
    ("API", "google_api_key"): "Google Generative AI key.",
    ("API", "groq_api_key"): "Groq LPU inference key.",
    ("Database", "sqlite_path"): "Path to the main content SQLite database.",
    ("Server", "disable_cors"): "If true, skips CORS middleware entirely (same-origin clients only).",
}


def _read_config_lines() -> List[str]:
    """Read the raw config file preserving comments for contextual hints."""
    config_path = get_config_file_path()
    with config_path.open("r", encoding="utf-8") as stream:
        return stream.readlines()


def _build_comment_index() -> Tuple[Dict[Tuple[str, str], str], Dict[str, str]]:
    """Return mappings of field and section comments gathered from config.txt."""
    lines = _read_config_lines()
    field_comments: Dict[Tuple[str, str], str] = {}
    section_comments: Dict[str, str] = {}

    current_section: Optional[str] = None
    pending_field_comments: List[str] = []
    pending_section_comments: List[str] = []
    seen_field_in_section = False

    for raw in lines:
        stripped = raw.strip()

        if not stripped:
            pending_field_comments.clear()
            if not seen_field_in_section:
                pending_section_comments.clear()
            continue

        if stripped.startswith('#'):
            comment_text = stripped.lstrip('#').strip()
            if comment_text:
                pending_field_comments.append(comment_text)
                if not seen_field_in_section:
                    pending_section_comments.append(comment_text)
            continue

        if stripped.startswith('[') and stripped.endswith(']'):
            # Close previous section comment if we never encountered a field.
            if current_section and pending_section_comments and not seen_field_in_section:
                section_comments[current_section] = ' '.join(pending_section_comments).strip()

            current_section = stripped[1:-1].strip()
            pending_field_comments.clear()
            pending_section_comments = []
            seen_field_in_section = False
            continue

        if '=' in raw and current_section:
            line_without_inline = raw
            inline_comment = ''
            if '#' in raw:
                before, after = raw.split('#', 1)
                line_without_inline = before
                inline_comment = after.strip()

            key = line_without_inline.split('=', 1)[0].strip()
            comment_parts = list(pending_field_comments)
            if inline_comment:
                comment_parts.append(inline_comment)

            if comment_parts:
                field_comments[(current_section, key)] = ' '.join(comment_parts).strip()

            if pending_section_comments and not seen_field_in_section:
                section_comments[current_section] = ' '.join(pending_section_comments).strip()

            pending_field_comments.clear()
            seen_field_in_section = True
            continue

    if current_section and pending_section_comments and not seen_field_in_section:
        section_comments[current_section] = ' '.join(pending_section_comments).strip()

    return field_comments, section_comments


def _humanise(value: str) -> str:
    words = re.split(r'[_\-]+', value)
    return ' '.join(word.capitalize() for word in words if word)


def _humanise_section_name(section: str) -> str:
    return SECTION_LABELS.get(section, section.replace('_', ' ').replace('-', ' ').title())


def _generate_default_hint(section: str, key: str) -> str:
    friendly_key = _humanise(key)
    section_label = _humanise_section_name(section)
    return f"Adjust {friendly_key} in {section_label}."


def _normalise_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value.strip()).lower()


def _tokenise(text: str) -> List[str]:
    return [token for token in re.findall(r'[a-z0-9]+', text.lower()) if len(token) > 2]


def _score_entry(query_lower: str, query_tokens: List[str], *candidates: str) -> float:
    best = 0.0
    for candidate in candidates:
        if not candidate:
            continue
        candidate_lower = _normalise_text(candidate)
        ratio = SequenceMatcher(None, query_lower, candidate_lower).ratio()
        token_hits = 0
        for token in query_tokens:
            if token in candidate_lower:
                token_hits += 1
        token_score = (token_hits / len(query_tokens)) if query_tokens else 0.0
        score = (ratio * 0.7) + (token_score * 0.3)
        if score > best:
            best = score
    return min(best, 1.0)


def get_config_file_path() -> Path:
    """Return the full filesystem path to ``config.txt``."""
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent
    return project_root / CONFIG_RELATIVE_PATH


def _load_config_parser() -> ConfigParser:
    """Load the configuration file into a ``ConfigParser`` instance."""
    config_path = get_config_file_path()
    parser = ConfigParser()
    parser.optionxform = str  # preserve key case

    if not config_path.exists():
        raise FileNotFoundError(
            f"Expected configuration file at {config_path}. Run the installer or create config.txt."
        )

    parser.read(config_path, encoding="utf-8")
    return parser


def _coerce_to_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _infer_type(raw_value: str) -> str:
    lowered = raw_value.strip().lower()
    if lowered in {"true", "false", "yes", "no", "on", "off", "1", "0"}:
        return "boolean"
    try:
        int(raw_value)
        return "integer"
    except ValueError:
        pass
    try:
        float(raw_value)
        return "number"
    except ValueError:
        pass
    return "string"


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEY_MARKERS)


def _is_placeholder(value: str) -> bool:
    return value.strip() in PLACEHOLDER_VALUES


def get_setup_flags(config: ConfigParser | None = None) -> Dict[str, bool]:
    """Return the setup enablement and completion flags."""
    parser = config or _load_config_parser()

    enabled = parser.getboolean(SETUP_SECTION, "enable_first_time_setup", fallback=False)
    completed = parser.getboolean(SETUP_SECTION, "setup_completed", fallback=False)

    return {
        "enabled": enabled,
        "completed": completed,
        "needs_setup": enabled and not completed,
    }


def needs_setup() -> bool:
    """Return ``True`` when the setup screen should be displayed."""
    return get_setup_flags()["needs_setup"]


def get_status_snapshot() -> Dict[str, Any]:
    """Return high-level status information for the setup API."""
    parser = _load_config_parser()
    flags = get_setup_flags(parser)

    placeholder_fields: List[Dict[str, str]] = []
    for section in parser.sections():
        for key, value in parser.items(section):
            if _is_placeholder(value):
                placeholder_fields.append({
                    "section": section,
                    "key": key,
                    "value": value,
                })

    return {
        "enabled": flags["enabled"],
        "setup_completed": flags["completed"],
        "needs_setup": flags["needs_setup"],
        "config_path": str(get_config_file_path()),
        "placeholder_fields": placeholder_fields,
    }


def get_config_snapshot() -> Dict[str, Any]:
    """Return the raw configuration structured for the setup UI."""
    parser = _load_config_parser()
    field_comments, section_comments = _build_comment_index()
    sections: List[Dict[str, Any]] = []

    for section in parser.sections():
        entries = []
        for key, value in parser.items(section):
            field_hint = FIELD_HINTS.get((section, key))
            if not field_hint:
                field_hint = field_comments.get((section, key))
            if not field_hint:
                field_hint = section_comments.get(section)
            if not field_hint:
                field_hint = _generate_default_hint(section, key)

            is_secret = _is_sensitive_key(key)
            # Determine placeholder against the real value before masking
            placeholder_flag = _is_placeholder(value)

            # Never return secret values to the client. Indicate if it is set without exposing it.
            presented_value = "" if is_secret else value
            presented_type = "string" if is_secret else _infer_type(value)

            entry: Dict[str, Any] = {
                "key": key,
                "value": presented_value,
                "type": presented_type,
                "is_secret": is_secret,
                "placeholder": placeholder_flag,
                "hint": field_hint,
            }
            # Extra hint for clients if a secret exists but is intentionally masked
            if is_secret:
                entry["is_set"] = bool(str(value).strip()) and not placeholder_flag

            entries.append(entry)

        sections.append({
            "name": section,
            "label": SECTION_LABELS.get(section, section.replace("_", " ").replace("-", " ").title()),
            "description": SECTION_DESCRIPTIONS.get(section) or section_comments.get(section),
            "fields": entries,
        })

    return {
        "config_path": str(get_config_file_path()),
        "sections": sections,
    }


def update_config(updates: Dict[str, Dict[str, Any]], *, create_backup: bool = True) -> Path | None:
    """Apply updates to the configuration file.

    Args:
        updates: Mapping of section -> key/value pairs to persist.
        create_backup: When True, write a timestamped ``.bak`` file alongside the config.

    Returns:
        The backup path if created, otherwise ``None``.
    """
    if not updates:
        raise ValueError("No updates provided for configuration")

    parser = _load_config_parser()
    config_path = get_config_file_path()

    for section, items in updates.items():
        if not parser.has_section(section):
            parser.add_section(section)
        for key, value in items.items():
            parser.set(section, key, _coerce_to_string(value))

    backup_path = None
    if create_backup:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = config_path.with_suffix(config_path.suffix + f".pre-setup-{timestamp}.bak")
        shutil.copy2(config_path, backup_path)
        logger.info(f"Created backup of config.txt at {backup_path}")

    with config_path.open("w", encoding="utf-8") as stream:
        parser.write(stream, space_around_delimiters=True)

    logger.info("Configuration file updated via setup manager")
    return backup_path


def mark_setup_completed(completed: bool = True) -> None:
    """Set the ``setup_completed`` flag in ``config.txt``."""
    update_config({SETUP_SECTION: {"setup_completed": completed}}, create_backup=False)


def reset_setup_flags() -> None:
    """Reset setup flags to their default values."""
    update_config({SETUP_SECTION: {
        "enable_first_time_setup": True,
        "setup_completed": False,
    }})
    logger.info("Setup flags reset to defaults")


def answer_setup_question(question: str, *, limit: int = 4) -> Dict[str, Any]:
    """Return contextual guidance for setup questions without requiring an external LLM."""
    query = (question or '').strip()
    if not query:
        raise ValueError("Question must not be empty")

    snapshot = get_config_snapshot()
    sections = snapshot.get("sections", [])
    query_lower = _normalise_text(query)
    query_tokens = _tokenise(query)

    catalogue: List[Dict[str, Any]] = []
    for section in sections:
        section_name = section.get("name", "")
        section_label = section.get("label", section_name)
        section_description = section.get("description") or ''

        catalogue.append({
            "type": "section",
            "section": section_name,
            "section_label": section_label,
            "label": section_label,
            "description": section_description,
            "hint": section_description,
        })

        for field in section.get("fields", []):
            catalogue.append({
                "type": "field",
                "section": section_name,
                "section_label": section_label,
                "key": field.get("key"),
                "label": _humanise(field.get("key", "")) or field.get("key", ""),
                "description": section_description,
                "hint": field.get("hint", ""),
            })

    scored_entries: List[Dict[str, Any]] = []
    for entry in catalogue:
        label = entry.get("label", "")
        hint = entry.get("hint", "")
        description = entry.get("description", "")
        extras = ' '.join(filter(None, [entry.get("key"), entry.get("section"), hint]))
        score = _score_entry(query_lower, query_tokens, label, hint, description, extras)

        if entry.get("key") and entry["key"].lower() in query_lower:
            score = min(score + 0.2, 1.0)
        if entry.get("section") and entry["section"].lower() in query_lower:
            score = min(score + 0.1, 1.0)

        if score >= 0.15:
            entry_with_score = dict(entry)
            entry_with_score["score"] = round(score, 3)
            scored_entries.append(entry_with_score)

    scored_entries.sort(key=lambda item: item["score"], reverse=True)
    top_matches = scored_entries[:limit] if scored_entries else []

    if top_matches:
        primary = top_matches[0]
        section_label = primary.get("section_label", "the configuration")
        if primary.get("type") == "field":
            field_label = primary.get("label", "This setting")
            hint = primary.get("hint", "")
            answer_lines = [
                f"{field_label} lives in the {section_label} section.",
                hint or "Update this value from the setup page to tailor the behaviour.",
            ]
        else:
            hint = primary.get("hint", "") or primary.get("description", "")
            answer_lines = [
                f"The {section_label} section groups related configuration options.",
            ]
            if hint:
                answer_lines.append(hint)

        if len(top_matches) > 1:
            answer_lines.append("\nOther related entries:")
            for sibling in top_matches[1:]:
                sibling_label = sibling.get("label") or sibling.get("key") or sibling.get("section_label")
                sibling_section = sibling.get("section_label")
                answer_lines.append(f"- {sibling_label} ({sibling_section})")

        answer_text = '\n'.join(answer_lines).strip()
    else:
        answer_text = (
            "I couldn't link that question to a specific setting yet. Try mentioning the section or exact "
            "setting name (for example, 'AuthNZ single_user_api_key')."
        )

    return {
        "answer": answer_text,
        "matches": top_matches,
    }
