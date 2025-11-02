# world_book_manager.py
# Description: World Book/Lorebook Manager for character chat with multi-user support
# Adapted from single-user to multi-user architecture with per-user database isolation
#
"""
World Book Manager for Multi-User Environment
---------------------------------------------

This module provides management for world books (lorebooks) that can be used
independently of characters, allowing shared lorebooks across conversations.

Key Adaptations from Single-User:
- Per-user database isolation (each user has their own database)
- Stateless service instances (no global state or singletons)
- Request-scoped processing (instantiated per API request)
- No thread-local storage (incompatible with async API)
- Database-backed persistence with user isolation

Features:
- CRUD operations for world books and entries
- Keyword matching and activation
- Token budget management
- Priority-based entry selection
- Scan depth control
- Recursive scanning support
"""

import json
import re
import sqlite3
from typing import List, Dict, Any, Optional, Set, Union
from datetime import datetime
from pathlib import Path

from loguru import logger
try:
    from tldw_Server_API.app.core.Utils.tokenizer import count_tokens as _count_tokens
except Exception:
    from tldw_Server_API.app.core.utils.tokenizer import count_tokens as _count_tokens

# Local imports
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    InputError,
    ConflictError
)
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


def _is_unique_violation(error: Exception) -> bool:
    """Best-effort detection of unique constraint/duplicate key violations across backends."""
    message = str(error).lower()
    return "unique constraint" in message or "duplicate key" in message


class WorldBookEntry:
    """
    Individual world book entry with keyword matching capabilities.

    This is a stateless data class that handles keyword matching and content.
    No global state or thread-local storage is used.
    """

    def __init__(
        self,
        entry_id: Optional[int] = None,
        world_book_id: int = None,
        keywords: List[str] = None,
        content: str = "",
        priority: int = 0,
        enabled: bool = True,
        case_sensitive: bool = False,
        regex_match: bool = False,
        whole_word_match: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a world book entry.

        Args:
            entry_id: Database ID
            world_book_id: Parent world book ID
            keywords: List of keywords to match
            content: Content to inject when matched
            priority: Priority for ordering (higher = more important)
            enabled: Whether entry is active
            case_sensitive: Whether keyword matching is case-sensitive
            regex_match: Whether keywords are regex patterns
            whole_word_match: Whether to match whole words only
            metadata: Additional metadata
        """
        self.entry_id = entry_id
        self.world_book_id = world_book_id
        self.keywords = keywords or []
        self.content = content
        self.priority = priority
        self.enabled = enabled
        self.case_sensitive = case_sensitive
        self.regex_match = regex_match
        self.whole_word_match = whole_word_match
        self.metadata = metadata or {}

        # Compile patterns for efficient matching
        self._patterns = self._compile_patterns()

    def _compile_patterns(self) -> List[re.Pattern]:
        """Compile keyword patterns for matching."""
        patterns = []

        for keyword in self.keywords:
            if self.regex_match:
                # Use keyword as regex directly
                try:
                    flags = 0 if self.case_sensitive else re.IGNORECASE
                    pattern = re.compile(keyword, flags)
                    patterns.append(pattern)
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{keyword}': {e}")
            else:
                # Build pattern for literal matching
                escaped = re.escape(keyword)
                if self.whole_word_match:
                    pattern_str = r'\b' + escaped + r'\b'
                else:
                    pattern_str = escaped

                flags = 0 if self.case_sensitive else re.IGNORECASE
                patterns.append(re.compile(pattern_str, flags))

        return patterns

    def matches(self, text: str) -> bool:
        """
        Check if any keyword matches the given text.

        Args:
            text: Text to search for keywords

        Returns:
            True if any keyword matches
        """
        if not self.enabled or not self._patterns:
            return False

        for pattern in self._patterns:
            if pattern.search(text):
                return True

        return False

    def get_match_count(self, text: str) -> int:
        """
        Count how many keywords match in the text.

        Args:
            text: Text to search

        Returns:
            Number of matching keywords
        """
        if not self.enabled or not self._patterns:
            return 0

        count = 0
        for pattern in self._patterns:
            if pattern.search(text):
                count += 1

        return count

    def to_storage_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage (normalized types)."""
        return {
            'id': self.entry_id,
            'world_book_id': self.world_book_id,
            'keywords': json.dumps(self.keywords),
            'content': self.content,
            'priority': int(self.priority),
            'enabled': int(self.enabled),
            'case_sensitive': int(self.case_sensitive),
            'regex_match': int(self.regex_match),
            'whole_word_match': int(self.whole_word_match),
            'metadata': json.dumps(self.metadata)
        }

    def to_api_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/tests (readable types)."""
        return {
            'id': self.entry_id,
            'world_book_id': self.world_book_id,
            'keywords': list(self.keywords),
            'content': self.content,
            'priority': int(self.priority),
            'enabled': bool(self.enabled),
            'case_sensitive': bool(self.case_sensitive),
            'regex_match': bool(self.regex_match),
            'whole_word_match': bool(self.whole_word_match),
            'recursive_scanning': bool(self.metadata.get('recursive_scanning', False)),
            'metadata': dict(self.metadata or {}),
        }


    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorldBookEntry':
        """Create WorldBookEntry instance from database dictionary."""
        keywords = data.get('keywords')
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except Exception:
                keywords = []
        metadata = data.get('metadata')
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        return cls(
            entry_id=data.get('id'),
            world_book_id=data.get('world_book_id'),
            keywords=keywords or [],
            content=data.get('content', ''),
            priority=int(data.get('priority', 0)),
            enabled=bool(data.get('enabled', True)),
            case_sensitive=bool(data.get('case_sensitive', False)),
            regex_match=bool(data.get('regex_match', False)),
            whole_word_match=bool(data.get('whole_word_match', True)),
            metadata=metadata or {}
        )

class WorldBookEntryView:
    """A hybrid view that behaves like both an object and a dict for tests."""
    def __init__(self, data: Dict[str, Any]):
        self._d = dict(data)
    # Attribute access
    def __getattr__(self, name: str):
        if name in self._d:
            return self._d[name]
        raise AttributeError(name)
    # Dict-like access
    def __getitem__(self, key):
        return self._d[key]
    def get(self, key, default=None):
        return self._d.get(key, default)
    def __repr__(self):
        return f"WorldBookEntryView({self._d!r})"


class OpResult:
    """Bool-like + dict-like operation result with 'success' key."""
    def __init__(self, success: bool):
        self.success = bool(success)
    def __getitem__(self, key):
        if key == 'success':
            return self.success
        raise KeyError(key)
    def get(self, key, default=None):
        return self.success if key == 'success' else default
    def __bool__(self):
        return self.success
    def __eq__(self, other):
        if isinstance(other, bool):
            return self.success == other
        if isinstance(other, dict):
            return other.get('success') == self.success
        return False
    def __repr__(self):
        return f"OpResult(success={self.success})"

## removed stray helper; functionality provided by WorldBookEntry.from_dict


class WorldBookService:
    """
    Service class for managing world books in a multi-user environment.

    This is a request-scoped service that is instantiated per API request.
    It works with the per-user database model where each user has their own
    separate database instance.
    """

    def __init__(self, db: CharactersRAGDB):
        """
        Initialize the service with a user-specific database connection.

        Args:
            db: User-specific database instance from dependency injection
        """
        self.db = db
        self._init_tables()

        # Request-scoped cache
        self._entry_cache: Optional[Dict[int, List[WorldBookEntry]]] = {}
        self._book_cache: Optional[Dict[int, Dict[str, Any]]] = {}
        self._activation_counts: Dict[int, int] = {}
        self._last_activated_at: Dict[int, datetime] = {}

    def _init_tables(self):
        """Initialize world book tables in the user's database if they don't exist."""
        backend_type = getattr(self.db, "backend_type", BackendType.SQLITE)
        try:
            with self.db.get_connection() as conn:
                if backend_type == BackendType.POSTGRESQL:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS world_books (
                            id SERIAL PRIMARY KEY,
                            name TEXT NOT NULL UNIQUE,
                            description TEXT,
                            scan_depth INTEGER DEFAULT 3,
                            token_budget INTEGER DEFAULT 500,
                            recursive_scanning BOOLEAN DEFAULT FALSE,
                            enabled BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            version INTEGER DEFAULT 1,
                            deleted BOOLEAN DEFAULT FALSE
                        )
                    """)

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS world_book_entries (
                            id SERIAL PRIMARY KEY,
                            world_book_id INTEGER NOT NULL,
                            keywords TEXT NOT NULL,
                            content TEXT NOT NULL,
                            priority INTEGER DEFAULT 0,
                            enabled BOOLEAN DEFAULT TRUE,
                            case_sensitive BOOLEAN DEFAULT FALSE,
                            regex_match BOOLEAN DEFAULT FALSE,
                            whole_word_match BOOLEAN DEFAULT TRUE,
                            metadata TEXT DEFAULT '{}',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (world_book_id) REFERENCES world_books(id) ON DELETE CASCADE
                        )
                    """)

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS character_world_books (
                            id SERIAL PRIMARY KEY,
                            character_id INTEGER NOT NULL,
                            world_book_id INTEGER NOT NULL,
                            enabled BOOLEAN DEFAULT TRUE,
                            priority INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(character_id, world_book_id),
                            FOREIGN KEY (character_id) REFERENCES character_cards(id) ON DELETE CASCADE,
                            FOREIGN KEY (world_book_id) REFERENCES world_books(id) ON DELETE CASCADE
                        )
                    """)
                else:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS world_books (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL UNIQUE,
                            description TEXT,
                            scan_depth INTEGER DEFAULT 3,
                            token_budget INTEGER DEFAULT 500,
                            recursive_scanning BOOLEAN DEFAULT 0,
                            enabled BOOLEAN DEFAULT 1,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            version INTEGER DEFAULT 1,
                            deleted BOOLEAN DEFAULT 0
                        )
                    """)

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS world_book_entries (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            world_book_id INTEGER NOT NULL,
                            keywords TEXT NOT NULL,
                            content TEXT NOT NULL,
                            priority INTEGER DEFAULT 0,
                            enabled BOOLEAN DEFAULT 1,
                            case_sensitive BOOLEAN DEFAULT 0,
                            regex_match BOOLEAN DEFAULT 0,
                            whole_word_match BOOLEAN DEFAULT 1,
                            metadata TEXT DEFAULT '{}',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (world_book_id) REFERENCES world_books(id) ON DELETE CASCADE
                        )
                    """)

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS character_world_books (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            character_id INTEGER NOT NULL,
                            world_book_id INTEGER NOT NULL,
                            enabled BOOLEAN DEFAULT 1,
                            priority INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(character_id, world_book_id),
                            FOREIGN KEY (character_id) REFERENCES character_cards(id) ON DELETE CASCADE,
                            FOREIGN KEY (world_book_id) REFERENCES world_books(id) ON DELETE CASCADE
                        )
                    """)

                # Create indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_wb_entries_book_id ON world_book_entries(world_book_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_wb_entries_priority ON world_book_entries(priority DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_char_wb_char_id ON character_world_books(character_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_char_wb_book_id ON character_world_books(world_book_id)")

                conn.commit()
                logger.info("World book tables initialized")
        except Exception as e:
            logger.error(f"Failed to initialize world book tables: {e}")
            raise CharactersRAGDBError(f"Failed to initialize world book tables: {e}")

    # --- World Book CRUD Operations ---

    def create_world_book(
        self,
        name: str,
        description: Optional[str] = None,
        scan_depth: int = 3,
        token_budget: int = 500,
        recursive_scanning: bool = False,
        enabled: bool = True
    ) -> int:
        """
        Create a new world book.

        Args:
            name: Unique name for the world book
            description: Optional description
            scan_depth: How many messages to scan for keywords
            token_budget: Maximum tokens to use for world info
            recursive_scanning: Whether to scan matched entries for more keywords
            enabled: Whether the world book is active

        Returns:
            The ID of the created world book

        Raises:
            InputError: If name is empty or invalid
            ConflictError: If a world book with this name already exists
        """
        if not name or not name.strip():
            raise InputError("World book name cannot be empty")

        try:
            with self.db.get_connection() as conn:
                insert_sql = """
                    INSERT INTO world_books
                    (name, description, scan_depth, token_budget, recursive_scanning, enabled)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (
                    name.strip(),
                    description,
                    scan_depth,
                    token_budget,
                    bool(recursive_scanning),
                    bool(enabled),
                )
                if self.db.backend_type == BackendType.POSTGRESQL:
                    insert_sql += " RETURNING id"

                cursor = conn.execute(insert_sql, params)

                if self.db.backend_type == BackendType.POSTGRESQL:
                    row = cursor.fetchone()
                    world_book_id = (row or {}).get("id") if row else None
                else:
                    world_book_id = cursor.lastrowid

                if world_book_id is None:
                    raise CharactersRAGDBError("Database did not return a world book id.")

                conn.commit()

                logger.info(f"Created world book '{name}' with ID {world_book_id}")
                self._invalidate_cache()
                return int(world_book_id)

        except sqlite3.IntegrityError as e:
            if _is_unique_violation(e):
                raise ConflictError(f"World book with name '{name}' already exists", "world_books", name)
            raise CharactersRAGDBError(f"Database error creating world book: {e}")
        except CharactersRAGDBError as e:
            if _is_unique_violation(e):
                raise ConflictError(f"World book with name '{name}' already exists", "world_books", name)
            raise
        except Exception as e:
            logger.error(f"Database error creating world book: {e}")
            raise CharactersRAGDBError(f"Database error creating world book: {e}") from e

    def get_world_book(self, world_book_id: Optional[int] = None, name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a world book by ID or name.

        Args:
            world_book_id: Optional world book ID
            name: Optional world book name

        Returns:
            Dictionary with world book data or None if not found
        """
        # Check cache first
        if world_book_id and world_book_id in self._book_cache:
            return self._book_cache[world_book_id]

        try:
            with self.db.get_connection() as conn:
                if world_book_id:
                    cursor = conn.execute(
                        """
                        SELECT * FROM world_books
                        WHERE id = ? AND deleted = ?
                        """,
                        (world_book_id, False)
                    )
                elif name:
                    cursor = conn.execute(
                        """
                        SELECT * FROM world_books
                        WHERE name = ? AND deleted = ?
                        """,
                        (name, False)
                    )
                else:
                    return None

                row = cursor.fetchone()
                if row:
                    book_data = dict(row)
                    if world_book_id:
                        self._book_cache[world_book_id] = book_data
                    return book_data
                return None

        except Exception as e:
            logger.error(f"Error fetching world book: {e}")
            raise CharactersRAGDBError(f"Error fetching world book: {e}")

    def list_world_books(self, include_disabled: bool = False) -> List[Dict[str, Any]]:
        """
        List all world books for the user.

        Args:
            include_disabled: Whether to include disabled world books

        Returns:
            List of world book data dictionaries
        """
        try:
            with self.db.get_connection() as conn:
                query = "SELECT * FROM world_books WHERE deleted = ?"
                params: List[Any] = [False]
                if not include_disabled:
                    query += " AND enabled = ?"
                    params.append(True)
                query += " ORDER BY name"

                cursor = conn.execute(query, tuple(params))
                books = [dict(row) for row in cursor.fetchall()]

                # Cache the books
                for book in books:
                    self._book_cache[book['id']] = book

                return books

        except Exception as e:
            logger.error(f"Error listing world books: {e}")
            raise CharactersRAGDBError(f"Error listing world books: {e}")

    def update_world_book(
        self,
        world_book_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        scan_depth: Optional[int] = None,
        token_budget: Optional[int] = None,
        recursive_scanning: Optional[bool] = None,
        enabled: Optional[bool] = None
    ) -> bool:
        """
        Update a world book's settings.

        Args:
            world_book_id: World book ID
            Various optional fields to update

        Returns:
            True if updated successfully

        Raises:
            ConflictError: If the new name conflicts with an existing world book
        """
        try:
            updates = []
            params = []

            if name is not None:
                updates.append("name = ?")
                params.append(name.strip())
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if scan_depth is not None:
                updates.append("scan_depth = ?")
                params.append(scan_depth)
            if token_budget is not None:
                updates.append("token_budget = ?")
                params.append(token_budget)
            if recursive_scanning is not None:
                updates.append("recursive_scanning = ?")
                params.append(bool(recursive_scanning))
            if enabled is not None:
                updates.append("enabled = ?")
                params.append(bool(enabled))

            if not updates:
                return True

            updates.append("last_modified = CURRENT_TIMESTAMP")
            updates.append("version = version + 1")
            params.extend([world_book_id, False])

            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    f"UPDATE world_books SET {', '.join(updates)} WHERE id = ? AND deleted = ?",
                    tuple(params)
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Updated world book {world_book_id}")
                    self._invalidate_cache()
                    return True
                return False

        except sqlite3.IntegrityError as e:
            if _is_unique_violation(e):
                raise ConflictError(f"World book name '{name}' already exists", "world_books", name)
            raise CharactersRAGDBError(f"Database error updating world book: {e}")
        except CharactersRAGDBError as e:
            if _is_unique_violation(e):
                raise ConflictError(f"World book name '{name}' already exists", "world_books", name)
            raise

    def delete_world_book(self, world_book_id: int, hard_delete: bool = False, **kwargs) -> bool:
        """
        Delete a world book (soft delete by default).

        Args:
            world_book_id: World book ID
            hard_delete: If True, permanently delete; otherwise soft delete

        Returns:
            True if deleted successfully
        """
        # Alias: support cascade=True from tests
        if kwargs.get('cascade') is True:
            hard_delete = True
        try:
            with self.db.get_connection() as conn:
                if hard_delete:
                    cursor = conn.execute(
                        "DELETE FROM world_books WHERE id = ?",
                        (world_book_id,)
                    )
                else:
                    cursor = conn.execute(
                        "UPDATE world_books SET deleted = ?, last_modified = CURRENT_TIMESTAMP WHERE id = ?",
                        (True, world_book_id)
                    )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"{'Hard' if hard_delete else 'Soft'} deleted world book {world_book_id}")
                    self._invalidate_cache()
                    return True
                return False

        except Exception as e:
            logger.error(f"Error deleting world book: {e}")
            raise CharactersRAGDBError(f"Error deleting world book: {e}")

    # --- Entry CRUD Operations ---

    def add_entry(
        self,
        world_book_id: int,
        keywords: List[str],
        content: str,
        priority: int = 0,
        enabled: bool = True,
        case_sensitive: bool = False,
        regex_match: bool = False,
        whole_word_match: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> int:
        """
        Add an entry to a world book.

        Args:
            world_book_id: World book ID
            keywords: List of keywords to match
            content: Content to inject when matched
            priority: Priority for ordering (higher = more important)
            enabled: Whether entry is active
            case_sensitive: Whether keyword matching is case-sensitive
            regex_match: Whether keywords are regex patterns
            whole_word_match: Whether to match whole words only
            metadata: Additional metadata

        Returns:
            The ID of the created entry
        """
        if not keywords:
            # Tests expect ValueError for empty keywords
            raise ValueError("Entry must have at least one keyword")
        # Empty content is allowed (store empty string)
        if content is None:
            content = ""
        # Clamp priority to [0, 100]
        try:
            priority = int(priority)
        except Exception:
            priority = 0
        priority = max(0, min(100, priority))

        # Support per-entry recursive scanning via metadata
        if 'recursive_scanning' in kwargs and isinstance(kwargs['recursive_scanning'], bool):
            md = dict(metadata or {})
            md['recursive_scanning'] = kwargs['recursive_scanning']
            metadata = md

        # Validate regex patterns if regex_match is True
        if regex_match:
            for keyword in keywords:
                try:
                    re.compile(keyword)
                except re.error as e:
                    raise InputError(f"Invalid regex pattern '{keyword}': {e}")

        keywords_json = json.dumps(keywords)
        metadata_json = json.dumps(metadata or {})

        try:
            with self.db.get_connection() as conn:
                insert_sql = """
                    INSERT INTO world_book_entries
                    (world_book_id, keywords, content, priority, enabled,
                     case_sensitive, regex_match, whole_word_match, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    world_book_id,
                    keywords_json,
                    content,
                    priority,
                    bool(enabled),
                    bool(case_sensitive),
                    bool(regex_match),
                    bool(whole_word_match),
                    metadata_json,
                )
                if self.db.backend_type == BackendType.POSTGRESQL:
                    insert_sql += " RETURNING id"

                cursor = conn.execute(insert_sql, params)

                if self.db.backend_type == BackendType.POSTGRESQL:
                    row = cursor.fetchone()
                    entry_id = (row or {}).get("id") if row else None
                else:
                    entry_id = cursor.lastrowid

                if entry_id is None:
                    raise CharactersRAGDBError("Database did not return a world book entry id.")

                conn.commit()

                logger.info(f"Added entry {entry_id} to world book {world_book_id}")
                self._invalidate_cache()
                return int(entry_id)

        except Exception as e:
            logger.error(f"Error adding world book entry: {e}")
            raise CharactersRAGDBError(f"Error adding world book entry: {e}")

    def add_world_book_entry(
        self,
        world_book_id: int,
        keywords: List[str],
        content: str,
        priority: int = 0,
        enabled: bool = True,
        case_sensitive: bool = False,
        regex_match: bool = False,
        whole_word_match: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> int:
        """
        Legacy alias maintained for backwards compatibility.
        """
        return self.add_entry(
            world_book_id=world_book_id,
            keywords=keywords,
            content=content,
            priority=priority,
            enabled=enabled,
            case_sensitive=case_sensitive,
            regex_match=regex_match,
            whole_word_match=whole_word_match,
            metadata=metadata,
            **kwargs,
        )

    def get_entries(
        self,
        world_book_id: Optional[int] = None,
        enabled_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get world book entries.

        Args:
            world_book_id: Optional specific world book ID
            enabled_only: Only return enabled entries

        Returns:
            List of WorldBookEntry instances
        """
        # Check cache first
        if world_book_id and world_book_id in self._entry_cache:
            entries = self._entry_cache[world_book_id]
            if enabled_only:
                entries = [e for e in entries if e.enabled]
            return [e.to_api_dict() for e in entries]

        try:
            with self.db.get_connection() as conn:
                query = """
                    SELECT e.*, wb.enabled as book_enabled
                    FROM world_book_entries e
                    JOIN world_books wb ON e.world_book_id = wb.id
                    WHERE wb.deleted = ?
                """
                params: List[Any] = [False]

                if world_book_id:
                    query += " AND e.world_book_id = ?"
                    params.append(world_book_id)
                if enabled_only:
                    query += " AND e.enabled = ? AND wb.enabled = ?"
                    params.extend([True, True])

                query += " ORDER BY e.priority DESC, e.id"

                cursor = conn.execute(query, tuple(params))
                entries: List[WorldBookEntry] = []

                for row in cursor.fetchall():
                    entry_data = dict(row)
                    entry = WorldBookEntry.from_dict(entry_data)
                    entries.append(entry)

                # Cache if fetching for specific book
                if world_book_id:
                    self._entry_cache[world_book_id] = entries

                # Return hybrid views for legacy/new compatibility
                return [WorldBookEntryView(e.to_api_dict()) for e in entries]

        except Exception as e:
            logger.error(f"Error fetching world book entries: {e}")
            raise CharactersRAGDBError(f"Error fetching world book entries: {e}")

    def update_entry(
        self,
        entry_id: int,
        keywords: Optional[List[str]] = None,
        content: Optional[str] = None,
        priority: Optional[int] = None,
        enabled: Optional[bool] = None,
        case_sensitive: Optional[bool] = None,
        regex_match: Optional[bool] = None,
        whole_word_match: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update a world book entry.

        Args:
            entry_id: Entry ID
            Various optional fields to update

        Returns:
            True if updated successfully
        """
        try:
            updates = []
            params = []

            if keywords is not None:
                if not keywords:
                    raise InputError("Entry must have at least one keyword")
                if regex_match:
                    for keyword in keywords:
                        try:
                            re.compile(keyword)
                        except re.error as e:
                            raise InputError(f"Invalid regex pattern '{keyword}': {e}")
                updates.append("keywords = ?")
                params.append(json.dumps(keywords))

            if content is not None:
                if not content:
                    raise InputError("Entry content cannot be empty")
                updates.append("content = ?")
                params.append(content)

            if priority is not None:
                try:
                    p = int(priority)
                except Exception:
                    p = 0
                p = max(0, min(100, p))
                updates.append("priority = ?")
                params.append(p)

            if enabled is not None:
                updates.append("enabled = ?")
                params.append(bool(enabled))

            if case_sensitive is not None:
                updates.append("case_sensitive = ?")
                params.append(bool(case_sensitive))

            if regex_match is not None:
                updates.append("regex_match = ?")
                params.append(bool(regex_match))

            if whole_word_match is not None:
                updates.append("whole_word_match = ?")
                params.append(bool(whole_word_match))

            if metadata is not None:
                updates.append("metadata = ?")
                params.append(json.dumps(metadata))

            if not updates:
                return True

            updates.append("last_modified = CURRENT_TIMESTAMP")
            params.append(entry_id)

            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    f"UPDATE world_book_entries SET {', '.join(updates)} WHERE id = ?",
                    tuple(params)
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Updated world book entry {entry_id}")
                    self._invalidate_cache()
                    return True
                return False

        except InputError:
            raise
        except Exception as e:
            logger.error(f"Error updating world book entry: {e}")
            raise CharactersRAGDBError(f"Error updating world book entry: {e}")

    def delete_entry(self, entry_id: int) -> bool:
        """
        Delete a world book entry.

        Args:
            entry_id: Entry ID

        Returns:
            True if deleted successfully
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM world_book_entries WHERE id = ?",
                    (entry_id,)
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Deleted world book entry {entry_id}")
                    self._invalidate_cache()
                    return True
                return False

        except Exception as e:
            logger.error(f"Error deleting world book entry: {e}")
            raise CharactersRAGDBError(f"Error deleting world book entry: {e}")

    # --- Character Association ---

    def attach_to_character(
        self,
        world_book_id: int,
        character_id: int,
        enabled: bool = True,
        priority: int = 0
    ) -> Dict[str, Any]:
        """
        Attach a world book to a character.

        Args:
            world_book_id: World book ID
            character_id: Character ID
            enabled: Whether the attachment is active
            priority: Priority for this character (higher = more important)

        Returns:
            OpResult with 'success' indicating attachment status
        """
        try:
            with self.db.get_connection() as conn:
                params = (character_id, world_book_id, bool(enabled), int(priority))
                try:
                    if self.db.backend_type == BackendType.POSTGRESQL:
                        conn.execute(
                            """
                            INSERT INTO character_world_books (character_id, world_book_id, enabled, priority)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (character_id, world_book_id)
                            DO UPDATE SET enabled = EXCLUDED.enabled,
                                          priority = EXCLUDED.priority
                            """,
                            params,
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO character_world_books (character_id, world_book_id, enabled, priority)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(character_id, world_book_id)
                            DO UPDATE SET enabled = excluded.enabled,
                                          priority = excluded.priority
                            """,
                            params,
                        )
                    conn.commit()
                    logger.info(f"Attached world book {world_book_id} to character {character_id}")
                    return OpResult(True)
                except sqlite3.IntegrityError as e:
                    if 'FOREIGN KEY constraint failed' in str(e):
                        logger.warning(
                            f"Attach failed due to missing character_id {character_id} for world_book {world_book_id}"
                        )
                        return OpResult(False)
                    raise
                except Exception as e:
                    # psycopg raises different exceptions; detect FK violation generically
                    msg = str(e).lower()
                    if "foreign key" in msg and "constraint" in msg:
                        logger.warning(
                            f"Attach failed due to missing character_id {character_id} for world_book {world_book_id}"
                        )
                        return OpResult(False)
                    raise

        except Exception as e:
            logger.error(f"Error attaching world book to character: {e}")
            raise CharactersRAGDBError(f"Error attaching world book to character: {e}")

    def detach_from_character(self, world_book_id: int, character_id: int) -> Dict[str, Any]:
        """
        Detach a world book from a character.

        Args:
            character_id: Character ID
            world_book_id: World book ID

        Returns:
            True if detached successfully
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM character_world_books
                    WHERE character_id = ? AND world_book_id = ?
                    """,
                    (character_id, world_book_id)
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Detached world book {world_book_id} from character {character_id}")
                    return OpResult(True)
                return OpResult(False)

        except Exception as e:
            logger.error(f"Error detaching world book from character: {e}")
            raise CharactersRAGDBError(f"Error detaching world book from character: {e}")

    def get_character_world_books(self, character_id: int, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all world books attached to a character.

        Args:
            character_id: Character ID
            enabled_only: Only return enabled attachments

        Returns:
            List of world book data with attachment info
        """
        try:
            with self.db.get_connection() as conn:
                query = """
                    SELECT wb.*, cwb.enabled as attachment_enabled, cwb.priority as attachment_priority
                    FROM world_books wb
                    JOIN character_world_books cwb ON wb.id = cwb.world_book_id
                    WHERE cwb.character_id = ? AND wb.deleted = ?
                """
                params: List[Any] = [character_id, False]

                if enabled_only:
                    query += " AND cwb.enabled = ? AND wb.enabled = ?"
                    params.extend([True, True])

                query += " ORDER BY cwb.priority DESC, wb.name"

                cursor = conn.execute(query, tuple(params))
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error fetching character world books: {e}")
            raise CharactersRAGDBError(f"Error fetching character world books: {e}")

    # --- Content Processing ---

    def process_context(
        self,
        text: str,
        world_book_ids: Optional[Union[List[int], int]] = None,
        character_id: Optional[int] = None,
        scan_depth: int = 3,
        token_budget: int = 500,
        recursive_scanning: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Process text to find and inject relevant world info.

        Args:
            text: Text to scan for keywords (usually recent messages)
            world_book_ids: Specific world books to use (optional)
            character_id: Character whose world books to use (optional)
            scan_depth: Override for scan depth
            token_budget: Maximum tokens to inject
            recursive_scanning: Whether to scan matched entries for more keywords

        Returns:
            Dictionary with processed_context and statistics
        """
        # Aliases
        if 'max_tokens' in kwargs and kwargs.get('max_tokens') is not None:
            token_budget = int(kwargs['max_tokens'])
        recursive_depth = int(kwargs.get('recursive_depth', 0) or 0)
        if recursive_depth > 0:
            recursive_scanning = True

        # Gather applicable world books
        books_to_use = []
        compact_return = False
        if isinstance(world_book_ids, int):
            world_book_ids = [world_book_ids]
            compact_return = True

        if world_book_ids:
            for book_id in world_book_ids:
                book = self.get_world_book(book_id)
                if book and book.get('enabled', True):
                    books_to_use.append(book)

        if character_id:
            char_books = self.get_character_world_books(character_id, enabled_only=True)
            books_to_use.extend(char_books)

        if books_to_use:
            unique_books: Dict[int, Dict[str, Any]] = {}
            for book in books_to_use:
                book_id = book.get('id')
                if book_id is None or book_id in unique_books:
                    continue
                unique_books[book_id] = book
            books_to_use = list(unique_books.values())

        if not books_to_use:
            empty = {
                "processed_context": "",
                "entries_matched": 0,
                "tokens_used": 0,
                "books_used": 0
            }
            return [] if compact_return else empty

        def _normalize_depth(value: Any) -> Optional[int]:
            try:
                depth_val = int(value)
            except (TypeError, ValueError):
                return None
            return depth_val if depth_val > 0 else None

        request_depth = _normalize_depth(scan_depth)

        # Gather all entries from applicable books
        all_entries: List[WorldBookEntry] = []
        book_entry_limits: Dict[int, Optional[int]] = {}
        for book in books_to_use:
            # Ensure we have object entries for matching
            if book['id'] in self._entry_cache:
                book_entries = [e for e in self._entry_cache[book['id']] if e.enabled]
            else:
                # Populate cache via DB
                _ = self.get_entries(book['id'], enabled_only=True)
                book_entries = self._entry_cache.get(book['id'], [])
            all_entries.extend(book_entries)
            book_depth = _normalize_depth(book.get('scan_depth'))
            book_id = book.get('id')
            if book_id is None:
                continue
            if request_depth is not None:
                limit = request_depth if book_depth is None else min(request_depth, book_depth)
            else:
                limit = book_depth
            book_entry_limits[book_id] = limit

        # Sort by priority (highest first)
        all_entries.sort(key=lambda e: e.priority, reverse=True)

        # Find matching entries
        matched_entries = []
        tokens_used = 0
        per_book_match_count: Dict[int, int] = {}

        for entry in all_entries:
            if not entry.matches(text):
                continue
            book_id = getattr(entry, 'world_book_id', None)
            limit = book_entry_limits.get(book_id)
            if limit is not None and per_book_match_count.get(book_id, 0) >= limit:
                continue
            # Estimate tokens (simple approximation)
            entry_tokens = self.count_tokens(entry.content)
            if tokens_used + entry_tokens <= token_budget:
                matched_entries.append(entry)
                tokens_used += entry_tokens
                if limit is not None:
                    per_book_match_count[book_id] = per_book_match_count.get(book_id, 0) + 1
            else:
                continue  # Skip oversized entry but continue scanning

        # Handle recursive scanning
        if recursive_scanning and matched_entries:
            current_depth = max(1, recursive_depth)
            seen = set(matched_entries)
            combined_content = " ".join(e.content for e in matched_entries)
            while current_depth > 0:
                additional_entries = []
                for entry in all_entries:
                    if entry in seen:
                        continue
                    book_id = getattr(entry, 'world_book_id', None)
                    limit = book_entry_limits.get(book_id)
                    if limit is not None and per_book_match_count.get(book_id, 0) >= limit:
                        continue
                    if entry.matches(combined_content):
                        entry_tokens = self.count_tokens(entry.content)
                        if tokens_used + entry_tokens <= token_budget:
                            additional_entries.append(entry)
                            tokens_used += entry_tokens
                            if limit is not None:
                                per_book_match_count[book_id] = per_book_match_count.get(book_id, 0) + 1
                if not additional_entries:
                    break
                for e in additional_entries:
                    seen.add(e)
                matched_entries.extend(additional_entries)
                combined_content = " ".join(e.content for e in matched_entries)
                current_depth -= 1

        # Build injected content
        if matched_entries:
            # Sort by priority for final output
            matched_entries.sort(key=lambda e: e.priority, reverse=True)
            injected_content = "\n\n".join(e.content for e in matched_entries)
        else:
            injected_content = ""

        # Track activation counts
        try:
            if matched_entries:
                per_book_counts: Dict[int, int] = {}
                for entry in matched_entries:
                    if entry.world_book_id is None:
                        continue
                    per_book_counts[entry.world_book_id] = per_book_counts.get(entry.world_book_id, 0) + 1
                now = datetime.now()
                for wb, count in per_book_counts.items():
                    self._activation_counts[wb] = self._activation_counts.get(wb, 0) + count
                    self._last_activated_at[wb] = now
        except Exception:
            pass

        if compact_return:
            return [e.to_api_dict() for e in matched_entries]
        return {
            "processed_context": injected_content,
            "entries_matched": len(matched_entries),
            "tokens_used": tokens_used,
            "books_used": len(set(e.world_book_id for e in matched_entries)) if matched_entries else 0,
            "entry_ids": [e.entry_id for e in matched_entries]
        }

    # --- Import/Export ---

    def export_world_book(self, world_book_id: int) -> Dict[str, Any]:
        """
        Export a world book to a dictionary format.

        Args:
            world_book_id: World book ID

        Returns:
            Dictionary with world book data and entries
        """
        book = self.get_world_book(world_book_id)
        if not book:
            raise InputError(f"World book {world_book_id} not found")

        entries = self.get_entries(world_book_id, enabled_only=False)
        top = {
            "name": book.get('name'),
            "description": book.get('description'),
            "scan_depth": book.get('scan_depth'),
            "token_budget": book.get('token_budget'),
            "recursive_scanning": bool(book.get('recursive_scanning', 0)),
            "enabled": bool(book.get('enabled', 1)),
            "entries": [ev._d for ev in entries],
        }
        # Legacy nested shape
        top["world_book"] = {
            "id": book.get('id'),
            "name": book.get('name'),
            "description": book.get('description'),
            "scan_depth": book.get('scan_depth'),
            "token_budget": book.get('token_budget'),
            "recursive_scanning": bool(book.get('recursive_scanning', 0)),
            "enabled": bool(book.get('enabled', 1)),
        }
        return top

    def import_world_book(self, data: Dict[str, Any], merge_on_conflict: bool = False) -> int:
        """
        Import a world book from dictionary format.

        Args:
            data: Dictionary with world book data and entries
            merge_on_conflict: If True, merge with existing book of same name

        Returns:
            ID of the imported/merged world book
        """
        # Support both nested and flattened formats
        if 'world_book' in data and isinstance(data['world_book'], dict):
            book_data = data['world_book']
            entries_data = data.get('entries', [])
        else:
            book_data = {k: v for k, v in data.items() if k != 'entries'}
            entries_data = data.get('entries', [])

        if not book_data.get("name"):
            raise InputError("World book must have a name")

        # Check for existing book
        existing = self.get_world_book(name=book_data["name"])

        if existing:
            if not merge_on_conflict:
                raise ConflictError(f"World book '{book_data['name']}' already exists")
            world_book_id = existing["id"]
            logger.info(f"Merging into existing world book {world_book_id}")
        else:
            # Create new world book
            world_book_id = self.create_world_book(
                name=book_data["name"],
                description=book_data.get("description"),
                scan_depth=book_data.get("scan_depth", 3),
                token_budget=book_data.get("token_budget", 500),
                recursive_scanning=book_data.get("recursive_scanning", False),
                enabled=book_data.get("enabled", True)
            )

        # Import entries
        for entry_data in entries_data:
            self.add_entry(
                world_book_id=world_book_id,
                keywords=entry_data.get("keywords", []),
                content=entry_data.get("content", ""),
                priority=entry_data.get("priority", 0),
                enabled=entry_data.get("enabled", True),
                case_sensitive=entry_data.get("case_sensitive", False),
                regex_match=entry_data.get("regex_match", False),
                whole_word_match=entry_data.get("whole_word_match", True),
                metadata=entry_data.get("metadata", {}),
                recursive_scanning=bool(entry_data.get('recursive_scanning', False)),
            )

        logger.info(f"Imported world book with {len(entries_data)} entries")
        return world_book_id

    # --- Helper Methods ---

    def _invalidate_cache(self):
        """Invalidate the request-scoped cache."""
        self._entry_cache = {}
        self._book_cache = {}

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Simple approximation: 1 token ≈ 4 characters or 0.75 words
        """
        return max(len(text) // 4, len(text.split()) * 3 // 4)

    def get_statistics(self, world_book_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get world book usage statistics.

        Returns:
            Dictionary containing statistics
        """
        try:
            if world_book_id is not None:
                with self.db.get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT COUNT(*) as total_entries, AVG(priority) as avg_priority FROM world_book_entries WHERE world_book_id = ?",
                        (world_book_id,)
                    )
                    row = dict(cursor.fetchone())
                    cursor = conn.execute(
                        "SELECT keywords, metadata FROM world_book_entries WHERE world_book_id = ?",
                        (world_book_id,)
                    )
                    total_keywords = 0
                    recursive_entries = 0
                    for r in cursor.fetchall():
                        # keywords
                        try:
                            kws = json.loads(r['keywords']) if isinstance(r['keywords'], str) else (r['keywords'] or [])
                        except Exception:
                            kws = []
                        total_keywords += len(kws)
                        # metadata
                        try:
                            md = json.loads(r['metadata']) if isinstance(r['metadata'], str) else (r['metadata'] or {})
                        except Exception:
                            md = {}
                        if md.get('recursive_scanning'):
                            recursive_entries += 1
                    return {
                        'total_entries': int(row.get('total_entries', 0) or 0),
                        'total_keywords': int(total_keywords),
                        'avg_priority': float(row.get('avg_priority', 0) or 0),
                        'recursive_entries': int(recursive_entries),
                    }
            with self.db.get_connection() as conn:
                # Get world book counts
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_world_books,
                        SUM(CASE WHEN enabled THEN 1 ELSE 0 END) as enabled_world_books
                    FROM world_books
                    WHERE deleted = ?
                    """,
                    (False,),
                )
                book_stats = dict(cursor.fetchone())

                # Get entry counts
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as total_entries
                    FROM world_book_entries e
                    JOIN world_books w ON e.world_book_id = w.id
                    WHERE w.deleted = ?
                    """,
                    (False,),
                )
                entry_stats = dict(cursor.fetchone())

                # Get character attachment counts
                cursor = conn.execute(
                    """
                    SELECT COUNT(DISTINCT character_id) as total_attachments
                    FROM character_world_books c
                    JOIN world_books w ON c.world_book_id = w.id
                    WHERE w.deleted = ?
                    """,
                    (False,),
                )
                attachment_stats = dict(cursor.fetchone())

                # Calculate average entries per world book
                avg_entries = 0
                if book_stats['total_world_books'] > 0:
                    avg_entries = entry_stats['total_entries'] / book_stats['total_world_books']

                return {
                    "total_world_books": book_stats['total_world_books'],
                    "enabled_world_books": book_stats['enabled_world_books'],
                    "total_entries": entry_stats['total_entries'],
                    "total_character_attachments": attachment_stats['total_attachments'],
                    "average_entries_per_world_book": avg_entries
                }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise CharactersRAGDBError(f"Error getting statistics: {e}")

    def search_entries(self, world_book_id: Optional[int] = None, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for entries by keyword or content.

        Args:
            search_term: Search term to look for

        Returns:
            List of matching entries with world book info
        """
        try:
            with self.db.get_connection() as conn:
                q = [
                    "SELECT e.*, w.name as world_book_name FROM world_book_entries e JOIN world_books w ON e.world_book_id = w.id",
                    "WHERE w.deleted = ?"
                ]
                params: List[Any] = [False]
                if world_book_id is not None:
                    q.append("AND e.world_book_id = ?")
                    params.append(world_book_id)
                if query:
                    q.append("AND (e.keywords LIKE ? OR e.content LIKE ?)")
                    params.extend([f"%{query}%", f"%{query}%"])
                q.append("ORDER BY w.name, e.priority DESC")
                cursor = conn.execute(" ".join(q), tuple(params))
                results: List[Dict[str, Any]] = []
                for row in cursor.fetchall():
                    rd = dict(row)
                    try:
                        if isinstance(rd.get('keywords'), str):
                            try:
                                rd['keywords'] = json.loads(rd['keywords'])
                            except Exception:
                                rd['keywords'] = [s.strip() for s in rd['keywords'].split(',') if s.strip()]
                        else:
                            rd['keywords'] = rd.get('keywords') or []
                    except Exception:
                        rd['keywords'] = []
                    try:
                        md = json.loads(rd.get('metadata', '{}')) if isinstance(rd.get('metadata'), str) else (rd.get('metadata') or {})
                    except Exception:
                        md = {}
                    rd['recursive_scanning'] = bool(md.get('recursive_scanning', False))
                    results.append(rd)
                return results

        except Exception as e:
            logger.error(f"Error searching entries: {e}")
            raise CharactersRAGDBError(f"Error searching entries: {e}")

    def bulk_update_entries(
        self,
        world_book_id: int,
        entry_ids: List[int],
        enabled: Optional[bool] = None,
        priority: Optional[int] = None
    ) -> int:
        """
        Bulk update entries.

        Args:
            world_book_id: World book ID
            entry_ids: List of entry IDs to update
            enabled: New enabled status (optional)
            priority: New priority (optional)

        Returns:
            Number of entries updated
        """
        try:
            if not entry_ids:
                return 0

            updates = []
            params = []

            if enabled is not None:
                updates.append("enabled = ?")
                params.append(int(enabled))

            if priority is not None:
                updates.append("priority = ?")
                params.append(priority)

            if not updates:
                return 0

            updates.append("updated_at = CURRENT_TIMESTAMP")

            with self.db.get_connection() as conn:
                # Build the IN clause for entry IDs
                placeholders = ','.join('?' * len(entry_ids))
                params.extend(entry_ids)
                params.append(world_book_id)

                cursor = conn.execute(
                    f"""
                    UPDATE world_book_entries
                    SET {', '.join(updates)}
                    WHERE id IN ({placeholders})
                    AND world_book_id = ?
                    """,
                    params
                )
                conn.commit()

                updated_count = cursor.rowcount
                logger.info(f"Updated {updated_count} entries in world book {world_book_id}")
                self._invalidate_cache()
                return updated_count

        except Exception as e:
            logger.error(f"Error bulk updating entries: {e}")
            raise CharactersRAGDBError(f"Error bulk updating entries: {e}")

    def clone_world_book(self, source_wb_id: int, new_name: str) -> int:
        """
        Create a copy of a world book with all its entries.

        Args:
            source_wb_id: Source world book ID
            new_name: Name for the cloned world book

        Returns:
            ID of the new world book
        """
        try:
            # Get source world book
            source_wb = self.get_world_book(source_wb_id)
            if not source_wb:
                raise InputError(f"Source world book {source_wb_id} not found")

            # Create new world book
            new_wb_id = self.create_world_book(
                name=new_name,
                description=f"Cloned from {source_wb['name']}",
                scan_depth=source_wb.get('scan_depth', 3),
                token_budget=source_wb.get('token_budget', 500),
                recursive_scanning=source_wb.get('recursive_scanning', False),
                enabled=source_wb.get('enabled', True)
            )

            # Get all entries from source world book
            entries = self.get_entries(source_wb_id, enabled_only=False)

            # Add entries to new world book
            if entries:
                with self.db.get_connection() as conn:
                    for entry in entries:
                        metadata_json = json.dumps(entry.get('metadata') or {})

                        conn.execute(
                            """
                            INSERT INTO world_book_entries
                            (world_book_id, keywords, content, priority, enabled,
                             case_sensitive, regex_match, whole_word_match, metadata)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                new_wb_id,
                                json.dumps(entry.get('keywords') or []),
                                entry.get('content', ''),
                                int(entry.get('priority', 0)),
                                bool(entry.get('enabled', True)),
                                bool(entry.get('case_sensitive', False)),
                                bool(entry.get('regex_match', False)),
                                bool(entry.get('whole_word_match', True)),
                                metadata_json,
                            ),
                        )
                    conn.commit()

            logger.info(f"Cloned world book {source_wb_id} to new world book {new_wb_id} with {len(entries)} entries")
            self._invalidate_cache()
            return new_wb_id

        except ConflictError:
            raise
        except Exception as e:
            logger.error(f"Error cloning world book: {e}")
            raise CharactersRAGDBError(f"Error cloning world book: {e}")

    def close(self):
        """
        Close the service and clean up resources.

        This method is provided for compatibility with test fixtures
        that expect a close method. Since the database connection is
        managed by CharactersRAGDB, this is a no-op.
        """
        # Database connections are managed by CharactersRAGDB
        # Nothing to close here
        pass

    # --- Additional test-facing APIs ---

    def toggle_entry_enabled(self, entry_id: int) -> bool:
        try:
            with self.db.get_connection() as conn:
                cur = conn.execute("SELECT enabled FROM world_book_entries WHERE id = ?", (entry_id,))
                row = cur.fetchone()
                current = bool(row[0]) if row else True
                cur = conn.execute(
                    "UPDATE world_book_entries SET enabled = ?, last_modified = CURRENT_TIMESTAMP WHERE id = ?",
                    (not current, entry_id)
                )
                conn.commit()
                if cur.rowcount > 0:
                    self._invalidate_cache()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error toggling entry enabled: {e}")
            raise CharactersRAGDBError(f"Error toggling entry enabled: {e}")

    def bulk_add_entries(self, world_book_id: int, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        added = 0
        for e in entries:
            self.add_entry(
                world_book_id=world_book_id,
                keywords=e.get('keywords', []),
                content=e.get('content', ''),
                priority=e.get('priority', 0),
                enabled=e.get('enabled', True),
                case_sensitive=e.get('case_sensitive', False),
                regex_match=e.get('regex_match', False),
                whole_word_match=e.get('whole_word_match', True),
                metadata=e.get('metadata', {}),
                recursive_scanning=bool(e.get('recursive_scanning', False)),
            )
            added += 1
        return {'added': added}

    def filter_entries(self, world_book_id: int, min_priority: Optional[int] = None, recursive_only: bool = False) -> List[Dict[str, Any]]:
        entries = self.get_entries(world_book_id, enabled_only=True)
        res: List[Dict[str, Any]] = []
        for e in entries:
            if min_priority is not None and int(e.get('priority', 0)) < int(min_priority):
                continue
            if recursive_only and not e.get('recursive_scanning', False):
                continue
            res.append(e)
        return res

    def export_to_lorebook_format(self, world_book_id: int) -> Dict[str, Any]:
        entries = self.get_entries(world_book_id, enabled_only=False)
        lore_entries = []
        for e in entries:
            key = e.get('keywords')[0] if e.get('keywords') else ''
            lore_entries.append({'key': key, 'content': e.get('content', '')})
        return {'entries': lore_entries}

    def get_activation_statistics(self, world_book_id: int) -> Dict[str, Any]:
        return {
            'total_activations': int(self._activation_counts.get(world_book_id, 0)),
            'last_activated_at': self._last_activated_at.get(world_book_id).isoformat() if self._last_activated_at.get(world_book_id) else None,
        }

    def normalize_keyword(self, kw: str) -> str:
        return (kw or '').strip().lower()

    def count_tokens(self, text: str) -> int:
        return _count_tokens(text)


# Export main classes
__all__ = [
    'WorldBookEntry',
    'WorldBookService'
]
