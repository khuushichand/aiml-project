"""Utilities for managing the first-time setup flow.

This module centralises reading and writing of the main ``config.txt`` file so the
first-time setup experience can query and update configuration without duplicating
file handling logic across routers or UI layers.
"""

from __future__ import annotations

import shutil
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
    "Settings": "General Settings",
    "Auto-Save": "Auto-Save",
    "Database": "Database",
    "AuthNZ": "Authentication",
    "Embeddings": "Embeddings",
    "RAG": "Retrieval Augmented Generation",
    "STT-Settings": "Speech-to-Text",
    "TTS-Settings": "Text-to-Speech",
    "Logging": "Logging",
    "Setup": "Setup",
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
    sections: List[Dict[str, Any]] = []

    for section in parser.sections():
        entries = []
        for key, value in parser.items(section):
            field_hint = FIELD_HINTS.get((section, key))
            entries.append({
                "key": key,
                "value": value,
                "type": _infer_type(value),
                "is_secret": _is_sensitive_key(key),
                "placeholder": _is_placeholder(value),
                "hint": field_hint,
            })

        sections.append({
            "name": section,
            "label": SECTION_LABELS.get(section, section.replace("_", " ").replace("-", " ").title()),
            "description": SECTION_DESCRIPTIONS.get(section),
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
