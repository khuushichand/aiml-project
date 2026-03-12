"""
User-scoped llama.cpp grammar-library service.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)

_CHAT_GRAMMAR_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
    sqlite3.Error,
)


class ChatGrammarService:
    """Request-scoped CRUD service for saved GBNF grammars."""

    def __init__(self, db: CharactersRAGDB):
        self.db = db
        self.db.ensure_chat_grammars_table()

    def create_grammar(
        self,
        *,
        name: str,
        description: str | None = None,
        grammar_text: str,
    ) -> str:
        """Create a saved grammar and return its identifier."""
        try:
            return self.db.insert_chat_grammar(
                {
                    "name": name,
                    "description": description,
                    "grammar_text": grammar_text,
                }
            )
        except ConflictError:
            raise
        except _CHAT_GRAMMAR_NONCRITICAL_EXCEPTIONS as exc:
            logger.error(f"Error creating chat grammar: {exc}")
            raise CharactersRAGDBError(f"Error creating chat grammar: {exc}") from exc

    def list_grammars(
        self,
        *,
        include_archived: bool = False,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List saved grammars for the current user."""
        return self.db.list_chat_grammars(
            include_archived=include_archived,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
        )

    def count_grammars(
        self,
        *,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> int:
        """Count saved grammars for the current user."""
        return self.db.count_chat_grammars(
            include_archived=include_archived,
            include_deleted=include_deleted,
        )

    def get_grammar(
        self,
        grammar_id: str,
        *,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None:
        """Fetch a saved grammar by identifier."""
        return self.db.get_chat_grammar(
            grammar_id,
            include_archived=include_archived,
            include_deleted=include_deleted,
        )

    def update_grammar(
        self,
        grammar_id: str,
        updates: dict[str, Any],
        *,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        """Update a saved grammar and return the refreshed record."""
        if not updates:
            raise InputError("No grammar updates were provided")
        current = self.db.get_chat_grammar(grammar_id, include_archived=True, include_deleted=True)
        if current is None or bool(current.get("deleted")):
            raise InputError(f"Grammar {grammar_id} not found")
        version = int(expected_version if expected_version is not None else current["version"])
        self.db.update_chat_grammar(grammar_id, updates, expected_version=version)
        updated = self.db.get_chat_grammar(grammar_id, include_archived=True, include_deleted=True)
        if updated is None:
            raise CharactersRAGDBError(f"Updated grammar {grammar_id} could not be reloaded")
        return updated

    def archive_grammar(
        self,
        grammar_id: str,
        *,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        """Archive a grammar without deleting its stored text."""
        current = self.db.get_chat_grammar(grammar_id, include_archived=True, include_deleted=True)
        if current is None or bool(current.get("deleted")):
            raise InputError(f"Grammar {grammar_id} not found")
        version = int(expected_version if expected_version is not None else current["version"])
        self.db.archive_chat_grammar(grammar_id, expected_version=version)
        archived = self.db.get_chat_grammar(grammar_id, include_archived=True, include_deleted=True)
        if archived is None:
            raise CharactersRAGDBError(f"Archived grammar {grammar_id} could not be reloaded")
        return archived

    def delete_grammar(
        self,
        grammar_id: str,
        *,
        expected_version: int | None = None,
        hard_delete: bool = False,
    ) -> bool:
        """Delete a grammar, soft-delete by default."""
        current = self.db.get_chat_grammar(grammar_id, include_archived=True, include_deleted=True)
        if current is None:
            raise InputError(f"Grammar {grammar_id} not found")
        version = int(expected_version if expected_version is not None else current["version"])
        return self.db.delete_chat_grammar(
            grammar_id,
            expected_version=version,
            hard_delete=hard_delete,
        )

    def close(self) -> None:
        """Compatibility no-op for test fixtures."""
        return None
