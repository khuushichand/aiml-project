"""Canonical source normalization for RAG and Text2SQL source selection."""

from __future__ import annotations


ALIAS_MAP: dict[str, str] = {
    "media": "media_db",
    "media_db": "media_db",
    "media_db_v2": "media_db",
    "notes": "notes",
    "notes_db": "notes",
    "characters": "characters",
    "character_cards_db": "characters",
    "character_cards": "characters",
    "chats": "chats",
    "chat_history": "chats",
    "kanban": "kanban",
    "kanban_db": "kanban",
    "prompts": "prompts",
    "prompts_db": "prompts",
    "claims": "claims",
    "claims_db": "claims",
    "sql": "sql",
}

PUBLIC_SOURCES = frozenset({"media_db", "notes", "characters", "chats", "kanban", "sql"})
INTERNAL_SOURCES = frozenset(set(PUBLIC_SOURCES) | {"prompts", "claims"})
DEFAULT_SOURCE = "media_db"


def normalize_source(value: str, *, allow_internal: bool = False) -> str:
    """Normalize a source token into its canonical source id."""
    key = str(value).strip().lower()
    normalized = ALIAS_MAP.get(key, key)
    allowed = INTERNAL_SOURCES if allow_internal else PUBLIC_SOURCES
    if normalized not in allowed:
        raise ValueError(f"Invalid source '{value}'. Allowed: {sorted(allowed)}")
    return normalized


def normalize_sources(values: list[str] | None, *, allow_internal: bool = False) -> list[str]:
    """Normalize a source list using the selected allowlist."""
    if values is None:
        return [DEFAULT_SOURCE]
    return [normalize_source(value, allow_internal=allow_internal) for value in values]


def normalize_sources_public(values: list[str] | None) -> list[str]:
    """Normalize sources intended for public API use."""
    return normalize_sources(values, allow_internal=False)


def normalize_sources_internal(values: list[str] | None) -> list[str]:
    """Normalize sources intended for trusted/internal callers."""
    return normalize_sources(values, allow_internal=True)
