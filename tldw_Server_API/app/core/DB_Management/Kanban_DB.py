# Kanban_DB.py
# Description: SQLite database management for Kanban boards, lists, and cards.
#
from __future__ import annotations

"""
Kanban_DB.py
------------

SQLite wrapper for per-user Kanban board data:
 - boards
 - lists
 - cards
 - labels
 - card_labels
 - checklists
 - checklist_items
 - comments
 - activities
 - card_links

This module encapsulates raw SQL per project guidelines.
Implements soft delete, archive, versioning, and FTS5 search.
"""

import json
import os
import sqlite3
import threading
import uuid as uuid_module
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger


# --- Helper Functions ---
def _utcnow_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _generate_uuid() -> str:
    """Generate a lowercase hex UUID."""
    return uuid_module.uuid4().hex.lower()


# --- Custom Exceptions ---
class KanbanDBError(Exception):
    """Base exception for KanbanDB related errors."""
    pass


class InputError(ValueError):
    """Exception for input validation errors."""
    pass


class ConflictError(KanbanDBError):
    """
    Indicates a conflict due to concurrent modification or unique constraint violation.

    This can occur if a record's version doesn't match an expected version during
    an update/delete operation (optimistic locking), or if an insert/update
    violates a unique constraint (e.g., duplicate client_id).
    """
    def __init__(self, message: str = "Conflict detected.", entity: Optional[str] = None, entity_id: Any = None):
        super().__init__(message)
        self.entity = entity
        self.entity_id = entity_id

    def __str__(self):
        base = super().__str__()
        details = []
        if self.entity:
            details.append(f"Entity: {self.entity}")
        if self.entity_id:
            details.append(f"ID: {self.entity_id}")
        return f"{base} ({', '.join(details)})" if details else base


class NotFoundError(KanbanDBError):
    """Exception when a requested resource is not found."""
    def __init__(self, message: str = "Resource not found.", entity: Optional[str] = None, entity_id: Any = None):
        super().__init__(message)
        self.entity = entity
        self.entity_id = entity_id


# --- Database Class ---
class KanbanDB:
    """
    Manages SQLite connections and operations for the Kanban database.

    This class provides thread-safe database access with:
    - WAL mode for better concurrency
    - Foreign key enforcement
    - Optimistic locking via version field
    - Soft delete and archive support
    - FTS5 full-text search for cards

    Attributes:
        db_path (str): Path to the SQLite database file.
        user_id (str): The user ID for user-scoped operations.
    """

    # Configuration defaults (can be overridden via environment variables)
    DEFAULT_ACTIVITY_RETENTION_DAYS = 30
    MAX_BOARDS_PER_USER = 100
    MAX_LISTS_PER_BOARD = 50
    MAX_CARDS_PER_LIST = 500
    MAX_LABELS_PER_BOARD = 50
    MAX_CHECKLISTS_PER_CARD = 20
    MAX_CHECKLIST_ITEMS_PER_CHECKLIST = 100
    MAX_COMMENTS_PER_CARD = 500
    MAX_COMMENT_SIZE = 10000  # characters

    def __init__(self, db_path: str, user_id: str) -> None:
        """
        Initialize the KanbanDB instance.

        Args:
            db_path: Path to the SQLite database file.
            user_id: The user ID for this database instance.
        """
        self.db_path = db_path
        self.user_id = str(user_id)
        self._lock = threading.RLock()

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize schema
        self._ensure_schema()
        logger.debug(f"KanbanDB initialized for user {user_id} at {db_path}")

    def _connect(self) -> sqlite3.Connection:
        """Create and configure a database connection."""
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        except Exception as e:
            logger.warning(f"Failed to set PRAGMA options: {e}")
        return conn

    def _ensure_schema(self) -> None:
        """Create all tables, indexes, and triggers if they don't exist."""
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(self._get_schema_sql())
                conn.commit()
                logger.debug("Kanban schema ensured")
            except Exception as e:
                logger.error(f"Failed to ensure schema: {e}")
                raise KanbanDBError(f"Schema creation failed: {e}") from e
            finally:
                conn.close()

    def _get_schema_sql(self) -> str:
        """Return the complete schema SQL."""
        return """
-- Boards
CREATE TABLE IF NOT EXISTS kanban_boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    archived INTEGER DEFAULT 0,
    archived_at TIMESTAMP,
    activity_retention_days INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    version INTEGER DEFAULT 1,
    metadata JSON
);
CREATE INDEX IF NOT EXISTS idx_boards_user_archived ON kanban_boards(user_id, archived);
CREATE INDEX IF NOT EXISTS idx_boards_deleted ON kanban_boards(deleted, deleted_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_boards_client_id ON kanban_boards(user_id, client_id);

-- Lists
CREATE TABLE IF NOT EXISTS kanban_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    board_id INTEGER NOT NULL REFERENCES kanban_boards(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    archived INTEGER DEFAULT 0,
    archived_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    version INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_lists_board_position ON kanban_lists(board_id, position);
CREATE INDEX IF NOT EXISTS idx_lists_board_archived ON kanban_lists(board_id, archived);
CREATE INDEX IF NOT EXISTS idx_lists_deleted ON kanban_lists(deleted, deleted_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_lists_client_id ON kanban_lists(board_id, client_id);

-- Cards
CREATE TABLE IF NOT EXISTS kanban_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    board_id INTEGER NOT NULL REFERENCES kanban_boards(id) ON DELETE CASCADE,
    list_id INTEGER NOT NULL REFERENCES kanban_lists(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    due_date TIMESTAMP,
    due_complete INTEGER DEFAULT 0,
    start_date TIMESTAMP,
    priority TEXT CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    archived INTEGER DEFAULT 0,
    archived_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    version INTEGER DEFAULT 1,
    metadata JSON
);
CREATE INDEX IF NOT EXISTS idx_cards_board ON kanban_cards(board_id);
CREATE INDEX IF NOT EXISTS idx_cards_list_position ON kanban_cards(list_id, position);
CREATE INDEX IF NOT EXISTS idx_cards_list_archived ON kanban_cards(list_id, archived);
CREATE INDEX IF NOT EXISTS idx_cards_due_date ON kanban_cards(due_date);
CREATE INDEX IF NOT EXISTS idx_cards_priority ON kanban_cards(board_id, priority);
CREATE INDEX IF NOT EXISTS idx_cards_deleted ON kanban_cards(deleted, deleted_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_client_id ON kanban_cards(board_id, client_id);

-- Labels
CREATE TABLE IF NOT EXISTS kanban_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    board_id INTEGER NOT NULL REFERENCES kanban_boards(id) ON DELETE CASCADE,
    name TEXT,
    color TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_labels_board ON kanban_labels(board_id);

-- Card-Label join
CREATE TABLE IF NOT EXISTS kanban_card_labels (
    card_id INTEGER NOT NULL REFERENCES kanban_cards(id) ON DELETE CASCADE,
    label_id INTEGER NOT NULL REFERENCES kanban_labels(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (card_id, label_id)
);

-- Checklists
CREATE TABLE IF NOT EXISTS kanban_checklists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    card_id INTEGER NOT NULL REFERENCES kanban_cards(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_checklists_card ON kanban_checklists(card_id);

-- Checklist Items
CREATE TABLE IF NOT EXISTS kanban_checklist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    checklist_id INTEGER NOT NULL REFERENCES kanban_checklists(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    checked INTEGER DEFAULT 0,
    checked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_checklist_items_checklist ON kanban_checklist_items(checklist_id);

-- Comments
CREATE TABLE IF NOT EXISTS kanban_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    card_id INTEGER NOT NULL REFERENCES kanban_cards(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_comments_card ON kanban_comments(card_id);

-- Activity Log
CREATE TABLE IF NOT EXISTS kanban_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    board_id INTEGER NOT NULL REFERENCES kanban_boards(id) ON DELETE CASCADE,
    list_id INTEGER REFERENCES kanban_lists(id) ON DELETE SET NULL,
    card_id INTEGER REFERENCES kanban_cards(id) ON DELETE SET NULL,
    user_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_activities_board ON kanban_activities(board_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activities_list ON kanban_activities(list_id);
CREATE INDEX IF NOT EXISTS idx_activities_card ON kanban_activities(card_id);
CREATE INDEX IF NOT EXISTS idx_activities_created ON kanban_activities(created_at);

-- Card Links
CREATE TABLE IF NOT EXISTS kanban_card_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    card_id INTEGER NOT NULL REFERENCES kanban_cards(id) ON DELETE CASCADE,
    linked_type TEXT NOT NULL CHECK (linked_type IN ('media', 'note')),
    linked_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(card_id, linked_type, linked_id)
);
CREATE INDEX IF NOT EXISTS idx_card_links_card ON kanban_card_links(card_id);
CREATE INDEX IF NOT EXISTS idx_card_links_linked ON kanban_card_links(linked_type, linked_id);

-- FTS5 for card search
CREATE VIRTUAL TABLE IF NOT EXISTS kanban_cards_fts USING fts5(
    title,
    description,
    content='kanban_cards',
    content_rowid='id'
);

-- Triggers for FTS sync (handles archive and soft delete)
-- Only index cards that are neither archived nor deleted
DROP TRIGGER IF EXISTS kanban_cards_ai;
CREATE TRIGGER kanban_cards_ai AFTER INSERT ON kanban_cards
WHEN NEW.deleted = 0 AND NEW.archived = 0 BEGIN
    INSERT INTO kanban_cards_fts(rowid, title, description)
    VALUES (NEW.id, NEW.title, NEW.description);
END;

DROP TRIGGER IF EXISTS kanban_cards_ad;
CREATE TRIGGER kanban_cards_ad AFTER DELETE ON kanban_cards BEGIN
    INSERT INTO kanban_cards_fts(kanban_cards_fts, rowid, title, description)
    VALUES ('delete', OLD.id, OLD.title, OLD.description);
END;

-- Handle content updates, archive, and soft delete/restore
DROP TRIGGER IF EXISTS kanban_cards_au;
CREATE TRIGGER kanban_cards_au AFTER UPDATE ON kanban_cards BEGIN
    -- Only remove old entry if it was previously indexed (not deleted and not archived)
    INSERT INTO kanban_cards_fts(kanban_cards_fts, rowid, title, description)
    SELECT 'delete', OLD.id, OLD.title, OLD.description
    WHERE OLD.deleted = 0 AND OLD.archived = 0;
    -- Only re-add if not deleted AND not archived
    INSERT INTO kanban_cards_fts(rowid, title, description)
    SELECT NEW.id, NEW.title, NEW.description
    WHERE NEW.deleted = 0 AND NEW.archived = 0;
END;
"""

    # =========================================================================
    # BOARD OPERATIONS
    # =========================================================================

    def create_board(
        self,
        name: str,
        client_id: str,
        description: Optional[str] = None,
        activity_retention_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new board.

        Args:
            name: Board name (required).
            client_id: Client-generated unique ID for idempotency.
            description: Optional board description.
            activity_retention_days: Optional override for activity retention.
            metadata: Optional JSON metadata.

        Returns:
            The created board as a dictionary.

        Raises:
            InputError: If name is empty or too long.
            ConflictError: If client_id already exists for this user.
        """
        # Validate inputs
        if not name or not name.strip():
            raise InputError("Board name is required")
        name = name.strip()
        if len(name) > 255:
            raise InputError("Board name must be 255 characters or less")
        if not client_id or not client_id.strip():
            raise InputError("client_id is required")
        client_id = client_id.strip()

        board_uuid = _generate_uuid()
        now = _utcnow_iso()
        metadata_json = json.dumps(metadata) if metadata else None

        with self._lock:
            conn = self._connect()
            try:
                # Check board limit
                cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM kanban_boards WHERE user_id = ? AND deleted = 0",
                    (self.user_id,)
                )
                count = cur.fetchone()["cnt"]
                if count >= self.MAX_BOARDS_PER_USER:
                    raise InputError(f"Maximum boards ({self.MAX_BOARDS_PER_USER}) reached")

                # Insert board
                cur = conn.execute(
                    """
                    INSERT INTO kanban_boards
                    (uuid, user_id, client_id, name, description, activity_retention_days,
                     metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (board_uuid, self.user_id, client_id, name, description,
                     activity_retention_days, metadata_json, now, now)
                )
                board_id = cur.lastrowid

                # Log activity
                self._log_activity_internal(
                    conn, board_id, "board_created", "board",
                    entity_id=board_id, details={"name": name}
                )

                conn.commit()

                # Fetch and return the created board
                return self._get_board_by_id(conn, board_id)

            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint" in str(e) and "client_id" in str(e):
                    raise ConflictError(
                        f"Board with client_id '{client_id}' already exists",
                        entity="board",
                        entity_id=client_id
                    )
                raise KanbanDBError(f"Database error: {e}") from e
            finally:
                conn.close()

    def get_board(
        self,
        board_id: int,
        include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get a board by ID.

        Args:
            board_id: The board ID.
            include_deleted: If True, include soft-deleted boards.

        Returns:
            The board as a dictionary, or None if not found.
        """
        with self._lock:
            conn = self._connect()
            try:
                return self._get_board_by_id(conn, board_id, include_deleted)
            finally:
                conn.close()

    def _get_board_by_id(
        self,
        conn: sqlite3.Connection,
        board_id: int,
        include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Internal method to get a board by ID using an existing connection."""
        sql = """
            SELECT id, uuid, user_id, client_id, name, description, archived,
                   archived_at, activity_retention_days, created_at, updated_at,
                   deleted, deleted_at, version, metadata
            FROM kanban_boards
            WHERE id = ? AND user_id = ?
        """
        params: List[Any] = [board_id, self.user_id]

        if not include_deleted:
            sql += " AND deleted = 0"

        cur = conn.execute(sql, params)
        row = cur.fetchone()

        if not row:
            return None

        return self._row_to_board_dict(row)

    def _row_to_board_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a board row to a dictionary."""
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "user_id": row["user_id"],
            "client_id": row["client_id"],
            "name": row["name"],
            "description": row["description"],
            "archived": bool(row["archived"]),
            "archived_at": row["archived_at"],
            "activity_retention_days": row["activity_retention_days"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "deleted": bool(row["deleted"]),
            "deleted_at": row["deleted_at"],
            "version": row["version"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None
        }

    def list_boards(
        self,
        include_archived: bool = False,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List boards for the user with pagination.

        Args:
            include_archived: If True, include archived boards.
            include_deleted: If True, include soft-deleted boards.
            limit: Maximum number of boards to return.
            offset: Number of boards to skip.

        Returns:
            Tuple of (list of boards, total count).
        """
        with self._lock:
            conn = self._connect()
            try:
                conditions = ["user_id = ?"]
                params: List[Any] = [self.user_id]

                if not include_archived:
                    conditions.append("archived = 0")
                if not include_deleted:
                    conditions.append("deleted = 0")

                where_clause = " AND ".join(conditions)

                # Get total count
                count_sql = f"SELECT COUNT(*) as cnt FROM kanban_boards WHERE {where_clause}"
                cur = conn.execute(count_sql, params)
                total = cur.fetchone()["cnt"]

                # Get boards
                sql = f"""
                    SELECT id, uuid, user_id, client_id, name, description, archived,
                           archived_at, activity_retention_days, created_at, updated_at,
                           deleted, deleted_at, version, metadata
                    FROM kanban_boards
                    WHERE {where_clause}
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])
                cur = conn.execute(sql, params)

                boards = [self._row_to_board_dict(row) for row in cur.fetchall()]

                return boards, total

            finally:
                conn.close()

    def update_board(
        self,
        board_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        activity_retention_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expected_version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update a board.

        Args:
            board_id: The board ID to update.
            name: New name (optional).
            description: New description (optional).
            activity_retention_days: New retention days (optional).
            metadata: New metadata (optional).
            expected_version: If provided, only update if version matches (optimistic locking).

        Returns:
            The updated board.

        Raises:
            NotFoundError: If board not found.
            ConflictError: If expected_version doesn't match.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Get current board
                board = self._get_board_by_id(conn, board_id)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)

                # Check version if provided
                if expected_version is not None and board["version"] != expected_version:
                    raise ConflictError(
                        f"Version mismatch: expected {expected_version}, got {board['version']}",
                        entity="board",
                        entity_id=board_id
                    )

                # Build update
                updates = []
                params: List[Any] = []

                if name is not None:
                    if not name.strip():
                        raise InputError("Board name cannot be empty")
                    name = name.strip()
                    if len(name) > 255:
                        raise InputError("Board name must be 255 characters or less")
                    updates.append("name = ?")
                    params.append(name)

                if description is not None:
                    updates.append("description = ?")
                    params.append(description)

                if activity_retention_days is not None:
                    if activity_retention_days < 7 or activity_retention_days > 365:
                        raise InputError("activity_retention_days must be between 7 and 365")
                    updates.append("activity_retention_days = ?")
                    params.append(activity_retention_days)

                if metadata is not None:
                    updates.append("metadata = ?")
                    params.append(json.dumps(metadata))

                if not updates:
                    return board

                # Always update version and timestamp
                updates.append("version = version + 1")
                updates.append("updated_at = ?")
                params.append(_utcnow_iso())
                params.append(board_id)

                sql = f"UPDATE kanban_boards SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)

                # Log activity
                self._log_activity_internal(
                    conn, board_id, "board_updated", "board",
                    entity_id=board_id, details={"updated_fields": [u.split(" = ")[0] for u in updates if "version" not in u and "updated_at" not in u]}
                )

                conn.commit()

                return self._get_board_by_id(conn, board_id)

            finally:
                conn.close()

    def archive_board(self, board_id: int, archive: bool = True) -> Dict[str, Any]:
        """
        Archive or unarchive a board.

        Args:
            board_id: The board ID.
            archive: True to archive, False to unarchive.

        Returns:
            The updated board.
        """
        with self._lock:
            conn = self._connect()
            try:
                board = self._get_board_by_id(conn, board_id)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)

                now = _utcnow_iso() if archive else None
                conn.execute(
                    """
                    UPDATE kanban_boards
                    SET archived = ?, archived_at = ?, version = version + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (1 if archive else 0, now, _utcnow_iso(), board_id)
                )

                # Log activity
                action = "board_archived" if archive else "board_unarchived"
                self._log_activity_internal(
                    conn, board_id, action, "board", entity_id=board_id
                )

                conn.commit()

                return self._get_board_by_id(conn, board_id)

            finally:
                conn.close()

    def delete_board(self, board_id: int, hard_delete: bool = False) -> bool:
        """
        Delete a board (soft delete by default).

        Args:
            board_id: The board ID.
            hard_delete: If True, permanently delete. If False, soft delete.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            conn = self._connect()
            try:
                board = self._get_board_by_id(conn, board_id, include_deleted=True)
                if not board:
                    return False

                if hard_delete:
                    conn.execute("DELETE FROM kanban_boards WHERE id = ?", (board_id,))
                else:
                    conn.execute(
                        """
                        UPDATE kanban_boards
                        SET deleted = 1, deleted_at = ?, version = version + 1, updated_at = ?
                        WHERE id = ?
                        """,
                        (_utcnow_iso(), _utcnow_iso(), board_id)
                    )
                    # Log activity (only for soft delete, hard delete removes everything)
                    self._log_activity_internal(
                        conn, board_id, "board_deleted", "board", entity_id=board_id
                    )

                conn.commit()
                return True

            finally:
                conn.close()

    def restore_board(self, board_id: int) -> Dict[str, Any]:
        """
        Restore a soft-deleted board.

        Args:
            board_id: The board ID.

        Returns:
            The restored board.

        Raises:
            NotFoundError: If board not found or not deleted.
        """
        with self._lock:
            conn = self._connect()
            try:
                board = self._get_board_by_id(conn, board_id, include_deleted=True)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)
                if not board["deleted"]:
                    raise InputError("Board is not deleted")

                conn.execute(
                    """
                    UPDATE kanban_boards
                    SET deleted = 0, deleted_at = NULL, version = version + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (_utcnow_iso(), board_id)
                )

                # Log activity
                self._log_activity_internal(
                    conn, board_id, "board_restored", "board", entity_id=board_id
                )

                conn.commit()

                return self._get_board_by_id(conn, board_id)

            finally:
                conn.close()

    # =========================================================================
    # LIST OPERATIONS
    # =========================================================================

    def create_list(
        self,
        board_id: int,
        name: str,
        client_id: str,
        position: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new list in a board.

        Args:
            board_id: The board ID.
            name: List name.
            client_id: Client-generated unique ID.
            position: Optional position (defaults to end).

        Returns:
            The created list.
        """
        if not name or not name.strip():
            raise InputError("List name is required")
        name = name.strip()
        if len(name) > 255:
            raise InputError("List name must be 255 characters or less")
        if not client_id or not client_id.strip():
            raise InputError("client_id is required")
        client_id = client_id.strip()

        list_uuid = _generate_uuid()
        now = _utcnow_iso()

        with self._lock:
            conn = self._connect()
            try:
                # Verify board exists and belongs to user
                board = self._get_board_by_id(conn, board_id)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)

                # Check list limit
                cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM kanban_lists WHERE board_id = ? AND deleted = 0",
                    (board_id,)
                )
                count = cur.fetchone()["cnt"]
                if count >= self.MAX_LISTS_PER_BOARD:
                    raise InputError(f"Maximum lists ({self.MAX_LISTS_PER_BOARD}) per board reached")

                # Get next position if not provided
                if position is None:
                    cur = conn.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM kanban_lists WHERE board_id = ? AND deleted = 0",
                        (board_id,)
                    )
                    position = cur.fetchone()["next_pos"]

                # Insert list
                cur = conn.execute(
                    """
                    INSERT INTO kanban_lists
                    (uuid, board_id, client_id, name, position, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (list_uuid, board_id, client_id, name, position, now, now)
                )
                list_id = cur.lastrowid

                # Log activity
                self._log_activity_internal(
                    conn, board_id, "list_created", "list", entity_id=list_id,
                    list_id=list_id, details={"name": name}
                )

                conn.commit()

                return self._get_list_by_id(conn, list_id)

            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint" in str(e) and "client_id" in str(e):
                    raise ConflictError(
                        f"List with client_id '{client_id}' already exists in this board",
                        entity="list",
                        entity_id=client_id
                    )
                raise KanbanDBError(f"Database error: {e}") from e
            finally:
                conn.close()

    def get_list(self, list_id: int, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """Get a list by ID."""
        with self._lock:
            conn = self._connect()
            try:
                return self._get_list_by_id(conn, list_id, include_deleted)
            finally:
                conn.close()

    def _get_list_by_id(
        self,
        conn: sqlite3.Connection,
        list_id: int,
        include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Internal method to get a list by ID."""
        sql = """
            SELECT l.id, l.uuid, l.board_id, l.client_id, l.name, l.position,
                   l.archived, l.archived_at, l.created_at, l.updated_at,
                   l.deleted, l.deleted_at, l.version
            FROM kanban_lists l
            JOIN kanban_boards b ON l.board_id = b.id
            WHERE l.id = ? AND b.user_id = ?
        """
        params: List[Any] = [list_id, self.user_id]

        if not include_deleted:
            sql += " AND l.deleted = 0"

        cur = conn.execute(sql, params)
        row = cur.fetchone()

        if not row:
            return None

        return self._row_to_list_dict(row)

    def _row_to_list_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a list row to a dictionary."""
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "board_id": row["board_id"],
            "client_id": row["client_id"],
            "name": row["name"],
            "position": row["position"],
            "archived": bool(row["archived"]),
            "archived_at": row["archived_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "deleted": bool(row["deleted"]),
            "deleted_at": row["deleted_at"],
            "version": row["version"]
        }

    def list_lists(
        self,
        board_id: int,
        include_archived: bool = False,
        include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all lists for a board, ordered by position.

        Args:
            board_id: The board ID.
            include_archived: If True, include archived lists.
            include_deleted: If True, include soft-deleted lists.

        Returns:
            List of lists ordered by position.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify board exists and belongs to user
                board = self._get_board_by_id(conn, board_id)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)

                conditions = ["l.board_id = ?"]
                params: List[Any] = [board_id]

                if not include_archived:
                    conditions.append("l.archived = 0")
                if not include_deleted:
                    conditions.append("l.deleted = 0")

                where_clause = " AND ".join(conditions)

                sql = f"""
                    SELECT l.id, l.uuid, l.board_id, l.client_id, l.name, l.position,
                           l.archived, l.archived_at, l.created_at, l.updated_at,
                           l.deleted, l.deleted_at, l.version
                    FROM kanban_lists l
                    WHERE {where_clause}
                    ORDER BY l.position ASC
                """
                cur = conn.execute(sql, params)

                return [self._row_to_list_dict(row) for row in cur.fetchall()]

            finally:
                conn.close()

    def update_list(
        self,
        list_id: int,
        name: Optional[str] = None,
        expected_version: Optional[int] = None
    ) -> Dict[str, Any]:
        """Update a list."""
        with self._lock:
            conn = self._connect()
            try:
                lst = self._get_list_by_id(conn, list_id)
                if not lst:
                    raise NotFoundError("List not found", entity="list", entity_id=list_id)

                if expected_version is not None and lst["version"] != expected_version:
                    raise ConflictError(
                        f"Version mismatch: expected {expected_version}, got {lst['version']}",
                        entity="list",
                        entity_id=list_id
                    )

                updates = []
                params: List[Any] = []

                if name is not None:
                    if not name.strip():
                        raise InputError("List name cannot be empty")
                    name = name.strip()
                    if len(name) > 255:
                        raise InputError("List name must be 255 characters or less")
                    updates.append("name = ?")
                    params.append(name)

                if not updates:
                    return lst

                updates.append("version = version + 1")
                updates.append("updated_at = ?")
                params.append(_utcnow_iso())
                params.append(list_id)

                sql = f"UPDATE kanban_lists SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)

                # Log activity with updated fields
                updated_fields = []
                if name is not None:
                    updated_fields.append("name")
                self._log_activity_internal(
                    conn, lst["board_id"], "list_updated", "list", entity_id=list_id,
                    list_id=list_id, details={"updated_fields": updated_fields}
                )

                conn.commit()

                return self._get_list_by_id(conn, list_id)

            finally:
                conn.close()

    def reorder_lists(self, board_id: int, list_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Reorder lists in a board.

        Args:
            board_id: The board ID.
            list_ids: List IDs in the desired order.

        Returns:
            Updated lists in new order.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify board exists
                board = self._get_board_by_id(conn, board_id)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)

                # Verify all lists exist and belong to the board
                cur = conn.execute(
                    f"SELECT id FROM kanban_lists WHERE board_id = ? AND deleted = 0 AND id IN ({','.join('?' * len(list_ids))})",
                    [board_id] + list_ids
                )
                existing_ids = {row["id"] for row in cur.fetchall()}

                if len(existing_ids) != len(list_ids):
                    missing = set(list_ids) - existing_ids
                    raise InputError(f"Lists not found or don't belong to board: {missing}")

                # Update positions
                now = _utcnow_iso()
                for position, list_id in enumerate(list_ids):
                    conn.execute(
                        "UPDATE kanban_lists SET position = ?, updated_at = ?, version = version + 1 WHERE id = ?",
                        (position, now, list_id)
                    )

                # Log activity
                self._log_activity_internal(
                    conn, board_id, "lists_reordered", "board", entity_id=board_id,
                    details={"list_ids": list_ids}
                )

                conn.commit()

                return self.list_lists(board_id)

            finally:
                conn.close()

    def archive_list(self, list_id: int, archive: bool = True) -> Dict[str, Any]:
        """Archive or unarchive a list."""
        with self._lock:
            conn = self._connect()
            try:
                lst = self._get_list_by_id(conn, list_id)
                if not lst:
                    raise NotFoundError("List not found", entity="list", entity_id=list_id)

                now = _utcnow_iso() if archive else None
                conn.execute(
                    """
                    UPDATE kanban_lists
                    SET archived = ?, archived_at = ?, version = version + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (1 if archive else 0, now, _utcnow_iso(), list_id)
                )

                # Log activity
                action = "list_archived" if archive else "list_unarchived"
                self._log_activity_internal(
                    conn, lst["board_id"], action, "list", entity_id=list_id,
                    list_id=list_id, details={"name": lst["name"]}
                )

                conn.commit()

                return self._get_list_by_id(conn, list_id)

            finally:
                conn.close()

    def delete_list(self, list_id: int, hard_delete: bool = False) -> bool:
        """Delete a list (soft delete by default)."""
        with self._lock:
            conn = self._connect()
            try:
                lst = self._get_list_by_id(conn, list_id, include_deleted=True)
                if not lst:
                    return False

                if hard_delete:
                    conn.execute("DELETE FROM kanban_lists WHERE id = ?", (list_id,))
                else:
                    conn.execute(
                        """
                        UPDATE kanban_lists
                        SET deleted = 1, deleted_at = ?, version = version + 1, updated_at = ?
                        WHERE id = ?
                        """,
                        (_utcnow_iso(), _utcnow_iso(), list_id)
                    )
                    # Log activity (only for soft delete)
                    self._log_activity_internal(
                        conn, lst["board_id"], "list_deleted", "list", entity_id=list_id,
                        list_id=list_id, details={"name": lst["name"]}
                    )
                conn.commit()
                return True

            finally:
                conn.close()

    def restore_list(self, list_id: int) -> Dict[str, Any]:
        """Restore a soft-deleted list."""
        with self._lock:
            conn = self._connect()
            try:
                lst = self._get_list_by_id(conn, list_id, include_deleted=True)
                if not lst:
                    raise NotFoundError("List not found", entity="list", entity_id=list_id)
                if not lst["deleted"]:
                    raise InputError("List is not deleted")

                conn.execute(
                    """
                    UPDATE kanban_lists
                    SET deleted = 0, deleted_at = NULL, version = version + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (_utcnow_iso(), list_id)
                )

                # Log activity
                self._log_activity_internal(
                    conn, lst["board_id"], "list_restored", "list", entity_id=list_id,
                    list_id=list_id, details={"name": lst["name"]}
                )

                conn.commit()

                return self._get_list_by_id(conn, list_id)

            finally:
                conn.close()

    # =========================================================================
    # CARD OPERATIONS
    # =========================================================================

    def create_card(
        self,
        list_id: int,
        title: str,
        client_id: str,
        description: Optional[str] = None,
        position: Optional[int] = None,
        due_date: Optional[str] = None,
        start_date: Optional[str] = None,
        priority: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new card in a list.

        Args:
            list_id: The list ID.
            title: Card title.
            client_id: Client-generated unique ID.
            description: Optional description.
            position: Optional position (defaults to end).
            due_date: Optional due date (ISO format).
            start_date: Optional start date (ISO format).
            priority: Optional priority ('low', 'medium', 'high', 'urgent').
            metadata: Optional JSON metadata.

        Returns:
            The created card.
        """
        if not title or not title.strip():
            raise InputError("Card title is required")
        title = title.strip()
        if len(title) > 500:
            raise InputError("Card title must be 500 characters or less")
        if not client_id or not client_id.strip():
            raise InputError("client_id is required")
        client_id = client_id.strip()

        if priority and priority not in ('low', 'medium', 'high', 'urgent'):
            raise InputError("priority must be one of: low, medium, high, urgent")

        card_uuid = _generate_uuid()
        now = _utcnow_iso()
        metadata_json = json.dumps(metadata) if metadata else None

        with self._lock:
            conn = self._connect()
            try:
                # Get list and board_id
                lst = self._get_list_by_id(conn, list_id)
                if not lst:
                    raise NotFoundError("List not found", entity="list", entity_id=list_id)

                board_id = lst["board_id"]

                # Check card limit
                cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM kanban_cards WHERE list_id = ? AND deleted = 0",
                    (list_id,)
                )
                count = cur.fetchone()["cnt"]
                if count >= self.MAX_CARDS_PER_LIST:
                    raise InputError(f"Maximum cards ({self.MAX_CARDS_PER_LIST}) per list reached")

                # Get next position if not provided
                if position is None:
                    cur = conn.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM kanban_cards WHERE list_id = ? AND deleted = 0",
                        (list_id,)
                    )
                    position = cur.fetchone()["next_pos"]

                # Insert card
                cur = conn.execute(
                    """
                    INSERT INTO kanban_cards
                    (uuid, board_id, list_id, client_id, title, description, position,
                     due_date, start_date, priority, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (card_uuid, board_id, list_id, client_id, title, description, position,
                     due_date, start_date, priority, metadata_json, now, now)
                )
                card_id = cur.lastrowid

                # Log activity
                self._log_activity_internal(
                    conn, board_id, "card_created", "card", entity_id=card_id,
                    list_id=list_id, card_id=card_id, details={"title": title}
                )

                conn.commit()

                return self._get_card_by_id(conn, card_id)

            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint" in str(e) and "client_id" in str(e):
                    raise ConflictError(
                        f"Card with client_id '{client_id}' already exists in this board",
                        entity="card",
                        entity_id=client_id
                    )
                raise KanbanDBError(f"Database error: {e}") from e
            finally:
                conn.close()

    def get_card(self, card_id: int, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """Get a card by ID."""
        with self._lock:
            conn = self._connect()
            try:
                return self._get_card_by_id(conn, card_id, include_deleted)
            finally:
                conn.close()

    def get_cards_by_ids(
        self,
        card_ids: List[int],
        include_deleted: bool = False,
        include_archived: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get multiple cards by IDs in a single query (batch fetch).

        This is more efficient than calling get_card() in a loop.

        Args:
            card_ids: List of card IDs to fetch.
            include_deleted: If True, include soft-deleted cards.
            include_archived: If True, include archived cards (default True).

        Returns:
            List of cards (may be fewer than requested if some IDs don't exist).
        """
        if not card_ids:
            return []

        with self._lock:
            conn = self._connect()
            try:
                placeholders = ",".join("?" * len(card_ids))
                sql = f"""
                    SELECT c.id, c.uuid, c.board_id, c.list_id, c.client_id, c.title, c.description,
                           c.position, c.due_date, c.due_complete, c.start_date, c.priority,
                           c.archived, c.archived_at, c.created_at, c.updated_at,
                           c.deleted, c.deleted_at, c.version, c.metadata,
                           b.name as board_name, l.name as list_name
                    FROM kanban_cards c
                    JOIN kanban_boards b ON c.board_id = b.id
                    JOIN kanban_lists l ON c.list_id = l.id
                    WHERE c.id IN ({placeholders}) AND b.user_id = ?
                """
                params: List[Any] = list(card_ids) + [self.user_id]

                if not include_deleted:
                    sql += " AND c.deleted = 0"
                if not include_archived:
                    sql += " AND c.archived = 0"

                cur = conn.execute(sql, params)
                rows = cur.fetchall()

                cards = []
                for row in rows:
                    card = self._row_to_card_dict(row)
                    card["board_name"] = row["board_name"]
                    card["list_name"] = row["list_name"]
                    # Get labels for this card
                    card["labels"] = self.get_card_labels(card["id"])
                    cards.append(card)

                return cards
            finally:
                conn.close()

    def _get_card_by_id(
        self,
        conn: sqlite3.Connection,
        card_id: int,
        include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Internal method to get a card by ID."""
        sql = """
            SELECT c.id, c.uuid, c.board_id, c.list_id, c.client_id, c.title, c.description,
                   c.position, c.due_date, c.due_complete, c.start_date, c.priority,
                   c.archived, c.archived_at, c.created_at, c.updated_at,
                   c.deleted, c.deleted_at, c.version, c.metadata
            FROM kanban_cards c
            JOIN kanban_boards b ON c.board_id = b.id
            WHERE c.id = ? AND b.user_id = ?
        """
        params: List[Any] = [card_id, self.user_id]

        if not include_deleted:
            sql += " AND c.deleted = 0"

        cur = conn.execute(sql, params)
        row = cur.fetchone()

        if not row:
            return None

        return self._row_to_card_dict(row)

    def _row_to_card_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a card row to a dictionary."""
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "board_id": row["board_id"],
            "list_id": row["list_id"],
            "client_id": row["client_id"],
            "title": row["title"],
            "description": row["description"],
            "position": row["position"],
            "due_date": row["due_date"],
            "due_complete": bool(row["due_complete"]),
            "start_date": row["start_date"],
            "priority": row["priority"],
            "archived": bool(row["archived"]),
            "archived_at": row["archived_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "deleted": bool(row["deleted"]),
            "deleted_at": row["deleted_at"],
            "version": row["version"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None
        }

    def list_cards(
        self,
        list_id: int,
        include_archived: bool = False,
        include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all cards in a list, ordered by position.

        Args:
            list_id: The list ID.
            include_archived: If True, include archived cards.
            include_deleted: If True, include soft-deleted cards.

        Returns:
            List of cards ordered by position.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify list exists and belongs to user's board
                lst = self._get_list_by_id(conn, list_id)
                if not lst:
                    raise NotFoundError("List not found", entity="list", entity_id=list_id)

                conditions = ["c.list_id = ?"]
                params: List[Any] = [list_id]

                if not include_archived:
                    conditions.append("c.archived = 0")
                if not include_deleted:
                    conditions.append("c.deleted = 0")

                where_clause = " AND ".join(conditions)

                sql = f"""
                    SELECT c.id, c.uuid, c.board_id, c.list_id, c.client_id, c.title, c.description,
                           c.position, c.due_date, c.due_complete, c.start_date, c.priority,
                           c.archived, c.archived_at, c.created_at, c.updated_at,
                           c.deleted, c.deleted_at, c.version, c.metadata
                    FROM kanban_cards c
                    WHERE {where_clause}
                    ORDER BY c.position ASC
                """
                cur = conn.execute(sql, params)

                return [self._row_to_card_dict(row) for row in cur.fetchall()]

            finally:
                conn.close()

    def update_card(
        self,
        card_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        due_complete: Optional[bool] = None,
        start_date: Optional[str] = None,
        priority: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expected_version: Optional[int] = None
    ) -> Dict[str, Any]:
        """Update a card."""
        with self._lock:
            conn = self._connect()
            try:
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                if expected_version is not None and card["version"] != expected_version:
                    raise ConflictError(
                        f"Version mismatch: expected {expected_version}, got {card['version']}",
                        entity="card",
                        entity_id=card_id
                    )

                updates = []
                params: List[Any] = []

                if title is not None:
                    if not title.strip():
                        raise InputError("Card title cannot be empty")
                    title = title.strip()
                    if len(title) > 500:
                        raise InputError("Card title must be 500 characters or less")
                    updates.append("title = ?")
                    params.append(title)

                if description is not None:
                    updates.append("description = ?")
                    params.append(description)

                if due_date is not None:
                    updates.append("due_date = ?")
                    params.append(due_date if due_date else None)

                if due_complete is not None:
                    updates.append("due_complete = ?")
                    params.append(1 if due_complete else 0)

                if start_date is not None:
                    updates.append("start_date = ?")
                    params.append(start_date if start_date else None)

                if priority is not None:
                    if priority and priority not in ('low', 'medium', 'high', 'urgent'):
                        raise InputError("priority must be one of: low, medium, high, urgent")
                    updates.append("priority = ?")
                    params.append(priority if priority else None)

                if metadata is not None:
                    updates.append("metadata = ?")
                    params.append(json.dumps(metadata))

                if not updates:
                    return card

                # Build list of updated fields for activity log
                updated_fields = []
                if title is not None:
                    updated_fields.append("title")
                if description is not None:
                    updated_fields.append("description")
                if due_date is not None:
                    updated_fields.append("due_date")
                if due_complete is not None:
                    updated_fields.append("due_complete")
                if start_date is not None:
                    updated_fields.append("start_date")
                if priority is not None:
                    updated_fields.append("priority")
                if metadata is not None:
                    updated_fields.append("metadata")

                updates.append("version = version + 1")
                updates.append("updated_at = ?")
                params.append(_utcnow_iso())
                params.append(card_id)

                sql = f"UPDATE kanban_cards SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)

                # Log activity
                self._log_activity_internal(
                    conn, card["board_id"], "card_updated", "card", entity_id=card_id,
                    list_id=card["list_id"], card_id=card_id,
                    details={"updated_fields": updated_fields}
                )

                conn.commit()

                return self._get_card_by_id(conn, card_id)

            finally:
                conn.close()

    def move_card(
        self,
        card_id: int,
        target_list_id: int,
        position: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Move a card to a different list.

        Args:
            card_id: The card ID.
            target_list_id: The destination list ID.
            position: Optional position in the target list (defaults to end).

        Returns:
            The updated card.
        """
        with self._lock:
            conn = self._connect()
            try:
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                target_list = self._get_list_by_id(conn, target_list_id)
                if not target_list:
                    raise NotFoundError("Target list not found", entity="list", entity_id=target_list_id)

                # Verify target list is in the same board
                if target_list["board_id"] != card["board_id"]:
                    raise InputError("Cannot move card to a list in a different board")

                # Get target position
                if position is None:
                    cur = conn.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM kanban_cards WHERE list_id = ? AND deleted = 0",
                        (target_list_id,)
                    )
                    position = cur.fetchone()["next_pos"]

                source_list_id = card["list_id"]
                now = _utcnow_iso()
                conn.execute(
                    """
                    UPDATE kanban_cards
                    SET list_id = ?, position = ?, version = version + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (target_list_id, position, now, card_id)
                )

                # Log activity
                self._log_activity_internal(
                    conn, card["board_id"], "card_moved", "card", entity_id=card_id,
                    list_id=target_list_id, card_id=card_id,
                    details={
                        "title": card["title"],
                        "from_list_id": source_list_id,
                        "to_list_id": target_list_id
                    }
                )

                conn.commit()

                return self._get_card_by_id(conn, card_id)

            finally:
                conn.close()

    def copy_card(
        self,
        card_id: int,
        target_list_id: int,
        new_client_id: str,
        position: Optional[int] = None,
        new_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Copy a card to a list.

        Args:
            card_id: The source card ID.
            target_list_id: The destination list ID.
            new_client_id: Client-generated unique ID for the copy.
            position: Optional position in the target list.
            new_title: Optional new title (defaults to "Copy of {original}").

        Returns:
            The copied card.
        """
        with self._lock:
            conn = self._connect()
            try:
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                target_list = self._get_list_by_id(conn, target_list_id)
                if not target_list:
                    raise NotFoundError("Target list not found", entity="list", entity_id=target_list_id)

                # Verify target list is in the same board
                if target_list["board_id"] != card["board_id"]:
                    raise InputError("Cannot copy card to a list in a different board")

                # Generate title if not provided
                if new_title is None:
                    new_title = f"Copy of {card['title']}"

                # Get target position
                if position is None:
                    cur = conn.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM kanban_cards WHERE list_id = ? AND deleted = 0",
                        (target_list_id,)
                    )
                    position = cur.fetchone()["next_pos"]

                card_uuid = _generate_uuid()
                now = _utcnow_iso()

                # Insert the copy
                cur = conn.execute(
                    """
                    INSERT INTO kanban_cards
                    (uuid, board_id, list_id, client_id, title, description, position,
                     due_date, start_date, priority, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (card_uuid, card["board_id"], target_list_id, new_client_id,
                     new_title, card["description"], position,
                     card["due_date"], card["start_date"], card["priority"],
                     json.dumps(card["metadata"]) if card["metadata"] else None,
                     now, now)
                )
                new_card_id = cur.lastrowid

                # Copy labels
                conn.execute(
                    """
                    INSERT INTO kanban_card_labels (card_id, label_id, created_at)
                    SELECT ?, label_id, ? FROM kanban_card_labels WHERE card_id = ?
                    """,
                    (new_card_id, now, card_id)
                )

                # Log activity
                self._log_activity_internal(
                    conn, card["board_id"], "card_copied", "card", entity_id=new_card_id,
                    list_id=target_list_id, card_id=new_card_id,
                    details={
                        "title": new_title,
                        "source_card_id": card_id,
                        "target_list_id": target_list_id
                    }
                )

                conn.commit()

                return self._get_card_by_id(conn, new_card_id)

            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint" in str(e) and "client_id" in str(e):
                    raise ConflictError(
                        f"Card with client_id '{new_client_id}' already exists",
                        entity="card",
                        entity_id=new_client_id
                    )
                raise KanbanDBError(f"Database error: {e}") from e
            finally:
                conn.close()

    def reorder_cards(self, list_id: int, card_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Reorder cards in a list.

        Args:
            list_id: The list ID.
            card_ids: Card IDs in the desired order.

        Returns:
            Updated cards in new order.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify list exists
                lst = self._get_list_by_id(conn, list_id)
                if not lst:
                    raise NotFoundError("List not found", entity="list", entity_id=list_id)

                # Verify all cards exist and belong to the list
                cur = conn.execute(
                    f"SELECT id FROM kanban_cards WHERE list_id = ? AND deleted = 0 AND id IN ({','.join('?' * len(card_ids))})",
                    [list_id] + card_ids
                )
                existing_ids = {row["id"] for row in cur.fetchall()}

                if len(existing_ids) != len(card_ids):
                    missing = set(card_ids) - existing_ids
                    raise InputError(f"Cards not found or don't belong to list: {missing}")

                # Update positions
                now = _utcnow_iso()
                for position, card_id in enumerate(card_ids):
                    conn.execute(
                        "UPDATE kanban_cards SET position = ?, updated_at = ?, version = version + 1 WHERE id = ?",
                        (position, now, card_id)
                    )

                # Log activity
                self._log_activity_internal(
                    conn, lst["board_id"], "cards_reordered", "list", entity_id=list_id,
                    list_id=list_id, details={"card_ids": card_ids}
                )

                conn.commit()

                return self.list_cards(list_id)

            finally:
                conn.close()

    def archive_card(self, card_id: int, archive: bool = True) -> Dict[str, Any]:
        """Archive or unarchive a card."""
        with self._lock:
            conn = self._connect()
            try:
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                now = _utcnow_iso() if archive else None
                conn.execute(
                    """
                    UPDATE kanban_cards
                    SET archived = ?, archived_at = ?, version = version + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (1 if archive else 0, now, _utcnow_iso(), card_id)
                )

                # Log activity
                action = "card_archived" if archive else "card_unarchived"
                self._log_activity_internal(
                    conn, card["board_id"], action, "card", entity_id=card_id,
                    list_id=card["list_id"], card_id=card_id,
                    details={"title": card["title"]}
                )

                conn.commit()

                return self._get_card_by_id(conn, card_id)

            finally:
                conn.close()

    def delete_card(self, card_id: int, hard_delete: bool = False) -> bool:
        """Delete a card (soft delete by default)."""
        with self._lock:
            conn = self._connect()
            try:
                card = self._get_card_by_id(conn, card_id, include_deleted=True)
                if not card:
                    return False

                if hard_delete:
                    conn.execute("DELETE FROM kanban_cards WHERE id = ?", (card_id,))
                else:
                    conn.execute(
                        """
                        UPDATE kanban_cards
                        SET deleted = 1, deleted_at = ?, version = version + 1, updated_at = ?
                        WHERE id = ?
                        """,
                        (_utcnow_iso(), _utcnow_iso(), card_id)
                    )
                    # Log activity (only for soft delete)
                    self._log_activity_internal(
                        conn, card["board_id"], "card_deleted", "card", entity_id=card_id,
                        list_id=card["list_id"], card_id=card_id,
                        details={"title": card["title"]}
                    )
                conn.commit()
                return True

            finally:
                conn.close()

    def restore_card(self, card_id: int) -> Dict[str, Any]:
        """Restore a soft-deleted card."""
        with self._lock:
            conn = self._connect()
            try:
                card = self._get_card_by_id(conn, card_id, include_deleted=True)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)
                if not card["deleted"]:
                    raise InputError("Card is not deleted")

                conn.execute(
                    """
                    UPDATE kanban_cards
                    SET deleted = 0, deleted_at = NULL, version = version + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (_utcnow_iso(), card_id)
                )

                # Log activity
                self._log_activity_internal(
                    conn, card["board_id"], "card_restored", "card", entity_id=card_id,
                    list_id=card["list_id"], card_id=card_id,
                    details={"title": card["title"]}
                )

                conn.commit()

                return self._get_card_by_id(conn, card_id)

            finally:
                conn.close()

    # =========================================================================
    # SEARCH OPERATIONS
    # =========================================================================

    def search_cards(
        self,
        query: str,
        board_id: Optional[int] = None,
        label_ids: Optional[List[int]] = None,
        priority: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search cards using FTS5.

        Args:
            query: Search query.
            board_id: Optional board ID to filter results.
            label_ids: Optional list of label IDs (cards must have ALL).
            priority: Optional priority filter.
            include_archived: Whether to include archived cards.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            Tuple of (list of search result cards with enriched data, total count).
        """
        if not query or not query.strip():
            raise InputError("Search query is required")

        with self._lock:
            conn = self._connect()
            try:
                # Build the search query
                raw_query = query.strip()

                # Escape FTS5 special characters by wrapping in double quotes
                # FTS5 treats quoted strings as literal phrase matches
                # First escape any internal double quotes
                fts_escaped = raw_query.replace('"', '""')
                fts_query = f'"{fts_escaped}"'

                # Escape LIKE wildcards to prevent unexpected matches
                escaped_query = raw_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                like_pattern = f"%{escaped_query}%"

                # Build label filter subquery if needed
                label_filter_sql = ""
                label_params: List[Any] = []
                if label_ids and len(label_ids) > 0:
                    label_filter_sql = f"""
                        AND c.id IN (
                            SELECT card_id
                            FROM kanban_card_labels
                            WHERE label_id IN ({','.join('?' * len(label_ids))})
                            GROUP BY card_id
                            HAVING COUNT(DISTINCT label_id) = ?
                        )
                    """
                    label_params.extend(label_ids)
                    label_params.append(len(label_ids))

                # Build common filters
                board_filter = "AND c.board_id = ?" if board_id else ""
                priority_filter = "AND c.priority = ?" if priority else ""

                # Strategy: FTS only indexes non-archived, non-deleted cards
                # For include_archived=True, we need to also search archived cards using LIKE
                if include_archived:
                    # Use UNION: FTS for non-archived + LIKE for archived
                    count_sql = f"""
                        SELECT COUNT(*) as cnt FROM (
                            -- Non-archived cards via FTS
                            SELECT c.id
                            FROM kanban_cards c
                            JOIN kanban_boards b ON c.board_id = b.id
                            JOIN kanban_cards_fts fts ON c.id = fts.rowid
                            WHERE b.user_id = ? AND c.deleted = 0 AND c.archived = 0
                            {board_filter} {priority_filter} {label_filter_sql}
                            AND kanban_cards_fts MATCH ?
                            UNION
                            -- Archived cards via LIKE
                            SELECT c.id
                            FROM kanban_cards c
                            JOIN kanban_boards b ON c.board_id = b.id
                            WHERE b.user_id = ? AND c.deleted = 0 AND c.archived = 1
                            {board_filter} {priority_filter} {label_filter_sql}
                            AND (c.title LIKE ? ESCAPE '\\' OR c.description LIKE ? ESCAPE '\\')
                        )
                    """
                    # Build params: FTS part + archived LIKE part
                    count_params: List[Any] = [self.user_id]
                    if board_id:
                        count_params.append(board_id)
                    if priority:
                        count_params.append(priority)
                    count_params.extend(label_params)
                    count_params.append(fts_query)
                    # Archived part
                    count_params.append(self.user_id)
                    if board_id:
                        count_params.append(board_id)
                    if priority:
                        count_params.append(priority)
                    count_params.extend(label_params)
                    count_params.extend([like_pattern, like_pattern])

                    cur = conn.execute(count_sql, count_params)
                    total = cur.fetchone()["cnt"]

                    # Search query with UNION
                    sql = f"""
                        SELECT * FROM (
                            -- Non-archived cards via FTS
                            SELECT c.id, c.uuid, c.board_id, c.list_id, c.client_id, c.title, c.description,
                                   c.position, c.due_date, c.due_complete, c.start_date, c.priority,
                                   c.archived, c.archived_at, c.created_at, c.updated_at,
                                   c.deleted, c.deleted_at, c.version, c.metadata,
                                   b.name as board_name, l.name as list_name,
                                   1 as search_rank
                            FROM kanban_cards c
                            JOIN kanban_boards b ON c.board_id = b.id
                            JOIN kanban_lists l ON c.list_id = l.id
                            JOIN kanban_cards_fts fts ON c.id = fts.rowid
                            WHERE b.user_id = ? AND c.deleted = 0 AND c.archived = 0
                            {board_filter} {priority_filter} {label_filter_sql}
                            AND kanban_cards_fts MATCH ?
                            UNION
                            -- Archived cards via LIKE
                            SELECT c.id, c.uuid, c.board_id, c.list_id, c.client_id, c.title, c.description,
                                   c.position, c.due_date, c.due_complete, c.start_date, c.priority,
                                   c.archived, c.archived_at, c.created_at, c.updated_at,
                                   c.deleted, c.deleted_at, c.version, c.metadata,
                                   b.name as board_name, l.name as list_name,
                                   2 as search_rank
                            FROM kanban_cards c
                            JOIN kanban_boards b ON c.board_id = b.id
                            JOIN kanban_lists l ON c.list_id = l.id
                            WHERE b.user_id = ? AND c.deleted = 0 AND c.archived = 1
                            {board_filter} {priority_filter} {label_filter_sql}
                            AND (c.title LIKE ? ESCAPE '\\' OR c.description LIKE ? ESCAPE '\\')
                        )
                        ORDER BY search_rank, updated_at DESC
                        LIMIT ? OFFSET ?
                    """
                    search_params: List[Any] = [self.user_id]
                    if board_id:
                        search_params.append(board_id)
                    if priority:
                        search_params.append(priority)
                    search_params.extend(label_params)
                    search_params.append(fts_query)
                    # Archived part
                    search_params.append(self.user_id)
                    if board_id:
                        search_params.append(board_id)
                    if priority:
                        search_params.append(priority)
                    search_params.extend(label_params)
                    search_params.extend([like_pattern, like_pattern])
                    search_params.extend([limit, offset])

                    cur = conn.execute(sql, search_params)
                else:
                    # Simple FTS-only search for non-archived cards
                    count_sql = f"""
                        SELECT COUNT(*) as cnt
                        FROM kanban_cards c
                        JOIN kanban_boards b ON c.board_id = b.id
                        JOIN kanban_cards_fts fts ON c.id = fts.rowid
                        WHERE b.user_id = ? AND c.deleted = 0 AND c.archived = 0
                        {board_filter} {priority_filter} {label_filter_sql}
                        AND kanban_cards_fts MATCH ?
                    """
                    count_params = [self.user_id]
                    if board_id:
                        count_params.append(board_id)
                    if priority:
                        count_params.append(priority)
                    count_params.extend(label_params)
                    count_params.append(fts_query)

                    cur = conn.execute(count_sql, count_params)
                    total = cur.fetchone()["cnt"]

                    sql = f"""
                        SELECT c.id, c.uuid, c.board_id, c.list_id, c.client_id, c.title, c.description,
                               c.position, c.due_date, c.due_complete, c.start_date, c.priority,
                               c.archived, c.archived_at, c.created_at, c.updated_at,
                               c.deleted, c.deleted_at, c.version, c.metadata,
                               b.name as board_name, l.name as list_name
                        FROM kanban_cards c
                        JOIN kanban_boards b ON c.board_id = b.id
                        JOIN kanban_lists l ON c.list_id = l.id
                        JOIN kanban_cards_fts fts ON c.id = fts.rowid
                        WHERE b.user_id = ? AND c.deleted = 0 AND c.archived = 0
                        {board_filter} {priority_filter} {label_filter_sql}
                        AND kanban_cards_fts MATCH ?
                        ORDER BY rank
                        LIMIT ? OFFSET ?
                    """
                    search_params = [self.user_id]
                    if board_id:
                        search_params.append(board_id)
                    if priority:
                        search_params.append(priority)
                    search_params.extend(label_params)
                    search_params.extend([fts_query, limit, offset])

                    cur = conn.execute(sql, search_params)

                results = []
                for row in cur.fetchall():
                    card = self._row_to_card_dict(row)
                    card["board_name"] = row["board_name"]
                    card["list_name"] = row["list_name"]
                    # Get labels for this card
                    card["labels"] = self.get_card_labels(card["id"])
                    results.append(card)

                return results, total

            finally:
                conn.close()

    # =========================================================================
    # ACTIVITY OPERATIONS (for Phase 2, but schema is here)
    # =========================================================================

    def log_activity(
        self,
        board_id: int,
        action_type: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        list_id: Optional[int] = None,
        card_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Log an activity event.

        Args:
            board_id: The board ID.
            action_type: Type of action (create, update, delete, move, etc.).
            entity_type: Type of entity (board, list, card, label, etc.).
            entity_id: Optional ID of the entity.
            list_id: Optional list ID for context.
            card_id: Optional card ID for context.
            details: Optional JSON details.

        Returns:
            The created activity record.
        """
        activity_uuid = _generate_uuid()
        now = _utcnow_iso()
        details_json = json.dumps(details) if details else None

        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO kanban_activities
                    (uuid, board_id, list_id, card_id, user_id, action_type, entity_type, entity_id, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (activity_uuid, board_id, list_id, card_id, self.user_id,
                     action_type, entity_type, entity_id, details_json, now)
                )
                activity_id = cur.lastrowid
                conn.commit()

                # Fetch and return
                cur = conn.execute(
                    "SELECT * FROM kanban_activities WHERE id = ?",
                    (activity_id,)
                )
                row = cur.fetchone()

                return {
                    "id": row["id"],
                    "uuid": row["uuid"],
                    "board_id": row["board_id"],
                    "list_id": row["list_id"],
                    "card_id": row["card_id"],
                    "user_id": row["user_id"],
                    "action_type": row["action_type"],
                    "entity_type": row["entity_type"],
                    "entity_id": row["entity_id"],
                    "details": json.loads(row["details"]) if row["details"] else None,
                    "created_at": row["created_at"]
                }

            finally:
                conn.close()

    def _log_activity_internal(
        self,
        conn: sqlite3.Connection,
        board_id: int,
        action_type: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        list_id: Optional[int] = None,
        card_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Internal helper to log activity while already holding a connection.

        This is called from within other operations to avoid nested locks.
        Does not commit - caller is responsible for committing.
        """
        activity_uuid = _generate_uuid()
        now = _utcnow_iso()
        details_json = json.dumps(details) if details else None

        conn.execute(
            """
            INSERT INTO kanban_activities
            (uuid, board_id, list_id, card_id, user_id, action_type, entity_type, entity_id, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (activity_uuid, board_id, list_id, card_id, self.user_id,
             action_type, entity_type, entity_id, details_json, now)
        )

    def get_board_activities(
        self,
        board_id: int,
        list_id: Optional[int] = None,
        card_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get activities for a board.

        Args:
            board_id: The board ID.
            list_id: Optional filter by list.
            card_id: Optional filter by card.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            Tuple of (list of activities, total count).
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify board belongs to user
                board = self._get_board_by_id(conn, board_id)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)

                conditions = ["board_id = ?"]
                params: List[Any] = [board_id]

                if list_id is not None:
                    conditions.append("list_id = ?")
                    params.append(list_id)

                if card_id is not None:
                    conditions.append("card_id = ?")
                    params.append(card_id)

                where_clause = " AND ".join(conditions)

                # Count
                count_sql = f"SELECT COUNT(*) as cnt FROM kanban_activities WHERE {where_clause}"
                cur = conn.execute(count_sql, params)
                total = cur.fetchone()["cnt"]

                # Get activities
                sql = f"""
                    SELECT id, uuid, board_id, list_id, card_id, user_id, action_type,
                           entity_type, entity_id, details, created_at
                    FROM kanban_activities
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                cur = conn.execute(sql, params + [limit, offset])

                activities = []
                for row in cur.fetchall():
                    activities.append({
                        "id": row["id"],
                        "uuid": row["uuid"],
                        "board_id": row["board_id"],
                        "list_id": row["list_id"],
                        "card_id": row["card_id"],
                        "user_id": row["user_id"],
                        "action_type": row["action_type"],
                        "entity_type": row["entity_type"],
                        "entity_id": row["entity_id"],
                        "details": json.loads(row["details"]) if row["details"] else None,
                        "created_at": row["created_at"]
                    })

                return activities, total

            finally:
                conn.close()

    def cleanup_old_activities(self, board_id: Optional[int] = None) -> int:
        """
        Remove activities older than retention period.

        Args:
            board_id: Optional board ID to clean up. If None, cleans all boards.

        Returns:
            Number of activities deleted.
        """
        with self._lock:
            conn = self._connect()
            try:
                if board_id:
                    # Get board-specific retention or use default
                    board = self._get_board_by_id(conn, board_id)
                    if not board:
                        return 0

                    retention_days = board.get("activity_retention_days") or self.DEFAULT_ACTIVITY_RETENTION_DAYS
                    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")

                    cur = conn.execute(
                        "DELETE FROM kanban_activities WHERE board_id = ? AND created_at < ?",
                        (board_id, cutoff)
                    )
                else:
                    # Clean all boards with their respective retention periods
                    # For simplicity, use default retention
                    cutoff = (datetime.now(timezone.utc) - timedelta(days=self.DEFAULT_ACTIVITY_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
                    cur = conn.execute(
                        "DELETE FROM kanban_activities WHERE created_at < ?",
                        (cutoff,)
                    )

                deleted = cur.rowcount
                conn.commit()

                logger.info(f"Cleaned up {deleted} old activities")
                return deleted

            finally:
                conn.close()

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_board_with_lists_and_cards(
        self,
        board_id: int,
        include_archived: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get a board with all its lists and cards nested.

        Args:
            board_id: The board ID.
            include_archived: If True, include archived items.

        Returns:
            Board with nested lists, each containing their cards.
        """
        with self._lock:
            conn = self._connect()
            try:
                board = self._get_board_by_id(conn, board_id)
                if not board:
                    return None

                # Get lists
                lists = self.list_lists(board_id, include_archived=include_archived)

                # Get cards for each list
                for lst in lists:
                    lst["cards"] = self.list_cards(lst["id"], include_archived=include_archived)
                    lst["card_count"] = len(lst["cards"])

                board["lists"] = lists
                board["total_cards"] = sum(lst["card_count"] for lst in lists)

                return board

            finally:
                conn.close()

    def get_card_count_for_list(self, list_id: int) -> int:
        """Get the count of non-deleted, non-archived cards in a list."""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM kanban_cards WHERE list_id = ? AND deleted = 0 AND archived = 0",
                    (list_id,)
                )
                return cur.fetchone()["cnt"]
            finally:
                conn.close()

    def purge_deleted_items(self, days_old: int = 30) -> Dict[str, int]:
        """
        Permanently delete items that have been soft-deleted for more than N days.

        Args:
            days_old: Number of days since deletion.

        Returns:
            Dictionary with counts of items purged per entity type.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_old)).strftime("%Y-%m-%d %H:%M:%S")

        with self._lock:
            conn = self._connect()
            try:
                counts = {}

                # Delete cards first (children)
                cur = conn.execute(
                    "DELETE FROM kanban_cards WHERE deleted = 1 AND deleted_at < ?",
                    (cutoff,)
                )
                counts["cards"] = cur.rowcount

                # Delete lists
                cur = conn.execute(
                    "DELETE FROM kanban_lists WHERE deleted = 1 AND deleted_at < ?",
                    (cutoff,)
                )
                counts["lists"] = cur.rowcount

                # Delete boards
                cur = conn.execute(
                    "DELETE FROM kanban_boards WHERE deleted = 1 AND deleted_at < ? AND user_id = ?",
                    (cutoff, self.user_id)
                )
                counts["boards"] = cur.rowcount

                conn.commit()

                logger.info(f"Purged deleted items: {counts}")
                return counts

            finally:
                conn.close()

    # =========================================================================
    # LABEL OPERATIONS
    # =========================================================================

    # Predefined color palette for labels
    LABEL_COLORS = {"red", "orange", "yellow", "green", "blue", "purple", "pink", "gray"}

    def create_label(
        self,
        board_id: int,
        name: str,
        color: str
    ) -> Dict[str, Any]:
        """
        Create a new label for a board.

        Args:
            board_id: The board ID.
            name: Label name.
            color: Label color (must be from LABEL_COLORS).

        Returns:
            The created label as a dictionary.

        Raises:
            NotFoundError: If board not found.
            InputError: If validation fails.
        """
        # Validate inputs
        if not name or not name.strip():
            raise InputError("Label name is required")
        name = name.strip()
        if len(name) > 50:
            raise InputError("Label name must be 50 characters or less")

        if not color or color.lower() not in self.LABEL_COLORS:
            raise InputError(f"Invalid color. Must be one of: {', '.join(sorted(self.LABEL_COLORS))}")
        color = color.lower()

        label_uuid = _generate_uuid()
        now = _utcnow_iso()

        with self._lock:
            conn = self._connect()
            try:
                # Verify board exists and belongs to user
                board = self._get_board_by_id(conn, board_id)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)

                # Check label limit
                cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM kanban_labels WHERE board_id = ?",
                    (board_id,)
                )
                count = cur.fetchone()["cnt"]
                if count >= self.MAX_LABELS_PER_BOARD:
                    raise InputError(f"Maximum labels ({self.MAX_LABELS_PER_BOARD}) per board reached")

                # Insert label
                cur = conn.execute(
                    """
                    INSERT INTO kanban_labels (uuid, board_id, name, color, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (label_uuid, board_id, name, color, now, now)
                )
                label_id = cur.lastrowid

                # Log activity
                self._log_activity_internal(
                    conn, board_id, "label_created", "label", entity_id=label_id,
                    details={"name": name, "color": color}
                )

                conn.commit()

                return self._get_label_by_id(conn, label_id)

            finally:
                conn.close()

    def get_label(self, label_id: int) -> Optional[Dict[str, Any]]:
        """Get a label by ID."""
        with self._lock:
            conn = self._connect()
            try:
                return self._get_label_by_id(conn, label_id)
            finally:
                conn.close()

    def _get_label_by_id(self, conn: sqlite3.Connection, label_id: int) -> Optional[Dict[str, Any]]:
        """Internal method to get a label by ID."""
        sql = """
            SELECT l.id, l.uuid, l.board_id, l.name, l.color, l.created_at, l.updated_at
            FROM kanban_labels l
            JOIN kanban_boards b ON l.board_id = b.id
            WHERE l.id = ? AND b.user_id = ?
        """
        cur = conn.execute(sql, (label_id, self.user_id))
        row = cur.fetchone()

        if not row:
            return None

        return self._row_to_label_dict(row)

    def _row_to_label_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a label row to a dictionary."""
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "board_id": row["board_id"],
            "name": row["name"],
            "color": row["color"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    def list_labels(self, board_id: int) -> List[Dict[str, Any]]:
        """
        Get all labels for a board.

        Args:
            board_id: The board ID.

        Returns:
            List of labels.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify board exists and belongs to user
                board = self._get_board_by_id(conn, board_id)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)

                sql = """
                    SELECT l.id, l.uuid, l.board_id, l.name, l.color, l.created_at, l.updated_at
                    FROM kanban_labels l
                    WHERE l.board_id = ?
                    ORDER BY l.name ASC
                """
                cur = conn.execute(sql, (board_id,))

                return [self._row_to_label_dict(row) for row in cur.fetchall()]

            finally:
                conn.close()

    def update_label(
        self,
        label_id: int,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a label."""
        with self._lock:
            conn = self._connect()
            try:
                label = self._get_label_by_id(conn, label_id)
                if not label:
                    raise NotFoundError("Label not found", entity="label", entity_id=label_id)

                updates = []
                params: List[Any] = []

                if name is not None:
                    if not name.strip():
                        raise InputError("Label name cannot be empty")
                    name = name.strip()
                    if len(name) > 50:
                        raise InputError("Label name must be 50 characters or less")
                    updates.append("name = ?")
                    params.append(name)

                if color is not None:
                    if color.lower() not in self.LABEL_COLORS:
                        raise InputError(f"Invalid color. Must be one of: {', '.join(sorted(self.LABEL_COLORS))}")
                    updates.append("color = ?")
                    params.append(color.lower())

                if not updates:
                    return label

                # Build list of updated fields
                updated_fields = []
                if name is not None:
                    updated_fields.append("name")
                if color is not None:
                    updated_fields.append("color")

                updates.append("updated_at = ?")
                params.append(_utcnow_iso())
                params.append(label_id)

                sql = f"UPDATE kanban_labels SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)

                # Log activity
                self._log_activity_internal(
                    conn, label["board_id"], "label_updated", "label", entity_id=label_id,
                    details={"updated_fields": updated_fields}
                )

                conn.commit()

                return self._get_label_by_id(conn, label_id)

            finally:
                conn.close()

    def delete_label(self, label_id: int) -> bool:
        """
        Delete a label (hard delete).

        This also removes all card_label associations.
        """
        with self._lock:
            conn = self._connect()
            try:
                label = self._get_label_by_id(conn, label_id)
                if not label:
                    return False

                # Log activity before deleting
                self._log_activity_internal(
                    conn, label["board_id"], "label_deleted", "label", entity_id=label_id,
                    details={"name": label["name"], "color": label["color"]}
                )

                conn.execute("DELETE FROM kanban_labels WHERE id = ?", (label_id,))
                conn.commit()

                return True

            finally:
                conn.close()

    def assign_label_to_card(self, card_id: int, label_id: int) -> bool:
        """
        Assign a label to a card.

        Args:
            card_id: The card ID.
            label_id: The label ID.

        Returns:
            True if assigned successfully.

        Raises:
            NotFoundError: If card or label not found.
            InputError: If label doesn't belong to the card's board.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Get card
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                # Get label
                label = self._get_label_by_id(conn, label_id)
                if not label:
                    raise NotFoundError("Label not found", entity="label", entity_id=label_id)

                # Verify label belongs to the same board as the card
                if label["board_id"] != card["board_id"]:
                    raise InputError("Label does not belong to the card's board")

                # Insert (ignore if already exists)
                now = _utcnow_iso()
                try:
                    conn.execute(
                        "INSERT INTO kanban_card_labels (card_id, label_id, created_at) VALUES (?, ?, ?)",
                        (card_id, label_id, now)
                    )

                    # Log activity
                    self._log_activity_internal(
                        conn, card["board_id"], "label_assigned", "card", entity_id=card_id,
                        list_id=card["list_id"], card_id=card_id,
                        details={"label_id": label_id, "label_name": label["name"]}
                    )

                    conn.commit()
                except sqlite3.IntegrityError:
                    # Already exists, that's fine
                    pass

                return True

            finally:
                conn.close()

    def remove_label_from_card(self, card_id: int, label_id: int) -> bool:
        """
        Remove a label from a card.

        Args:
            card_id: The card ID.
            label_id: The label ID.

        Returns:
            True if removed, False if the association didn't exist.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify card belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                # Get label info for activity log
                label = self._get_label_by_id(conn, label_id)

                cur = conn.execute(
                    "DELETE FROM kanban_card_labels WHERE card_id = ? AND label_id = ?",
                    (card_id, label_id)
                )

                if cur.rowcount > 0 and label:
                    # Log activity
                    self._log_activity_internal(
                        conn, card["board_id"], "label_removed", "card", entity_id=card_id,
                        list_id=card["list_id"], card_id=card_id,
                        details={"label_id": label_id, "label_name": label["name"]}
                    )

                conn.commit()

                return cur.rowcount > 0

            finally:
                conn.close()

    def get_card_labels(self, card_id: int) -> List[Dict[str, Any]]:
        """Get all labels assigned to a card."""
        with self._lock:
            conn = self._connect()
            try:
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                sql = """
                    SELECT l.id, l.uuid, l.board_id, l.name, l.color, l.created_at, l.updated_at
                    FROM kanban_labels l
                    JOIN kanban_card_labels cl ON l.id = cl.label_id
                    WHERE cl.card_id = ?
                    ORDER BY l.name ASC
                """
                cur = conn.execute(sql, (card_id,))

                return [self._row_to_label_dict(row) for row in cur.fetchall()]

            finally:
                conn.close()

    # =========================================================================
    # CHECKLIST OPERATIONS
    # =========================================================================

    def create_checklist(
        self,
        card_id: int,
        name: str,
        position: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new checklist for a card.

        Args:
            card_id: The card ID.
            name: Checklist name.
            position: Optional position (auto-assigned if not provided).

        Returns:
            The created checklist as a dictionary.
        """
        # Validate inputs
        if not name or not name.strip():
            raise InputError("Checklist name is required")
        name = name.strip()
        if len(name) > 255:
            raise InputError("Checklist name must be 255 characters or less")

        checklist_uuid = _generate_uuid()
        now = _utcnow_iso()

        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists and belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                # Check checklist limit
                cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM kanban_checklists WHERE card_id = ?",
                    (card_id,)
                )
                count = cur.fetchone()["cnt"]
                if count >= self.MAX_CHECKLISTS_PER_CARD:
                    raise InputError(f"Maximum checklists ({self.MAX_CHECKLISTS_PER_CARD}) per card reached")

                # Get next position if not provided
                if position is None:
                    cur = conn.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM kanban_checklists WHERE card_id = ?",
                        (card_id,)
                    )
                    position = cur.fetchone()["next_pos"]

                # Insert checklist
                cur = conn.execute(
                    """
                    INSERT INTO kanban_checklists (uuid, card_id, name, position, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (checklist_uuid, card_id, name, position, now, now)
                )
                checklist_id = cur.lastrowid

                # Log activity
                self._log_activity_internal(
                    conn, card["board_id"], "checklist_created", "checklist", entity_id=checklist_id,
                    list_id=card["list_id"], card_id=card_id,
                    details={"name": name}
                )

                conn.commit()

                return self._get_checklist_by_id(conn, checklist_id)

            finally:
                conn.close()

    def get_checklist(self, checklist_id: int) -> Optional[Dict[str, Any]]:
        """Get a checklist by ID."""
        with self._lock:
            conn = self._connect()
            try:
                return self._get_checklist_by_id(conn, checklist_id)
            finally:
                conn.close()

    def _get_checklist_by_id(self, conn: sqlite3.Connection, checklist_id: int) -> Optional[Dict[str, Any]]:
        """Internal method to get a checklist by ID."""
        sql = """
            SELECT ch.id, ch.uuid, ch.card_id, ch.name, ch.position, ch.created_at, ch.updated_at
            FROM kanban_checklists ch
            JOIN kanban_cards c ON ch.card_id = c.id
            JOIN kanban_boards b ON c.board_id = b.id
            WHERE ch.id = ? AND b.user_id = ?
        """
        cur = conn.execute(sql, (checklist_id, self.user_id))
        row = cur.fetchone()

        if not row:
            return None

        return self._row_to_checklist_dict(row)

    def _row_to_checklist_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a checklist row to a dictionary."""
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "card_id": row["card_id"],
            "name": row["name"],
            "position": row["position"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    def list_checklists(self, card_id: int) -> List[Dict[str, Any]]:
        """
        Get all checklists for a card, ordered by position.

        Args:
            card_id: The card ID.

        Returns:
            List of checklists ordered by position.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists and belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                sql = """
                    SELECT ch.id, ch.uuid, ch.card_id, ch.name, ch.position, ch.created_at, ch.updated_at
                    FROM kanban_checklists ch
                    WHERE ch.card_id = ?
                    ORDER BY ch.position ASC
                """
                cur = conn.execute(sql, (card_id,))

                return [self._row_to_checklist_dict(row) for row in cur.fetchall()]

            finally:
                conn.close()

    def update_checklist(
        self,
        checklist_id: int,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a checklist."""
        with self._lock:
            conn = self._connect()
            try:
                checklist = self._get_checklist_by_id(conn, checklist_id)
                if not checklist:
                    raise NotFoundError("Checklist not found", entity="checklist", entity_id=checklist_id)

                # Get the card for activity logging
                card = self._get_card_by_id(conn, checklist["card_id"])

                updates = []
                params: List[Any] = []

                if name is not None:
                    if not name.strip():
                        raise InputError("Checklist name cannot be empty")
                    name = name.strip()
                    if len(name) > 255:
                        raise InputError("Checklist name must be 255 characters or less")
                    updates.append("name = ?")
                    params.append(name)

                if not updates:
                    return checklist

                updates.append("updated_at = ?")
                params.append(_utcnow_iso())
                params.append(checklist_id)

                sql = f"UPDATE kanban_checklists SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)

                # Log activity
                if card:
                    self._log_activity_internal(
                        conn, card["board_id"], "checklist_updated", "checklist", entity_id=checklist_id,
                        list_id=card["list_id"], card_id=card["id"],
                        details={"name": name or checklist["name"]}
                    )

                conn.commit()

                return self._get_checklist_by_id(conn, checklist_id)

            finally:
                conn.close()

    def reorder_checklists(self, card_id: int, checklist_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Reorder checklists on a card.

        Args:
            card_id: The card ID.
            checklist_ids: Checklist IDs in the desired order.

        Returns:
            Updated checklists in new order.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                # Verify all checklists exist and belong to the card
                cur = conn.execute(
                    f"SELECT id FROM kanban_checklists WHERE card_id = ? AND id IN ({','.join('?' * len(checklist_ids))})",
                    [card_id] + checklist_ids
                )
                existing_ids = {row["id"] for row in cur.fetchall()}

                if len(existing_ids) != len(checklist_ids):
                    missing = set(checklist_ids) - existing_ids
                    raise InputError(f"Checklists not found or don't belong to card: {missing}")

                # Update positions
                now = _utcnow_iso()
                for position, checklist_id in enumerate(checklist_ids):
                    conn.execute(
                        "UPDATE kanban_checklists SET position = ?, updated_at = ? WHERE id = ?",
                        (position, now, checklist_id)
                    )

                # Log activity
                self._log_activity_internal(
                    conn, card["board_id"], "checklists_reordered", "card", entity_id=card_id,
                    list_id=card["list_id"], card_id=card_id,
                    details={"checklist_ids": checklist_ids}
                )

                conn.commit()

                return self.list_checklists(card_id)

            finally:
                conn.close()

    def delete_checklist(self, checklist_id: int) -> bool:
        """
        Delete a checklist (hard delete).

        This also cascades to delete all checklist items.
        """
        with self._lock:
            conn = self._connect()
            try:
                checklist = self._get_checklist_by_id(conn, checklist_id)
                if not checklist:
                    return False

                # Get the card for activity logging
                card = self._get_card_by_id(conn, checklist["card_id"])

                # Log activity before deleting
                if card:
                    self._log_activity_internal(
                        conn, card["board_id"], "checklist_deleted", "checklist", entity_id=checklist_id,
                        list_id=card["list_id"], card_id=card["id"],
                        details={"name": checklist["name"]}
                    )

                conn.execute("DELETE FROM kanban_checklists WHERE id = ?", (checklist_id,))
                conn.commit()

                return True

            finally:
                conn.close()

    # =========================================================================
    # CHECKLIST ITEM OPERATIONS
    # =========================================================================

    def create_checklist_item(
        self,
        checklist_id: int,
        name: str,
        position: Optional[int] = None,
        checked: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new checklist item.

        Args:
            checklist_id: The checklist ID.
            name: Item name.
            position: Optional position (auto-assigned if not provided).
            checked: Whether the item starts checked.

        Returns:
            The created checklist item as a dictionary.
        """
        # Validate inputs
        if not name or not name.strip():
            raise InputError("Checklist item name is required")
        name = name.strip()
        if len(name) > 500:
            raise InputError("Checklist item name must be 500 characters or less")

        item_uuid = _generate_uuid()
        now = _utcnow_iso()

        with self._lock:
            conn = self._connect()
            try:
                # Verify checklist exists and belongs to user
                checklist = self._get_checklist_by_id(conn, checklist_id)
                if not checklist:
                    raise NotFoundError("Checklist not found", entity="checklist", entity_id=checklist_id)

                # Check item limit
                cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM kanban_checklist_items WHERE checklist_id = ?",
                    (checklist_id,)
                )
                count = cur.fetchone()["cnt"]
                if count >= self.MAX_CHECKLIST_ITEMS_PER_CHECKLIST:
                    raise InputError(f"Maximum items ({self.MAX_CHECKLIST_ITEMS_PER_CHECKLIST}) per checklist reached")

                # Get next position if not provided
                if position is None:
                    cur = conn.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM kanban_checklist_items WHERE checklist_id = ?",
                        (checklist_id,)
                    )
                    position = cur.fetchone()["next_pos"]

                checked_at = now if checked else None

                # Get the card for activity logging
                card = self._get_card_by_id(conn, checklist["card_id"])

                # Insert item
                cur = conn.execute(
                    """
                    INSERT INTO kanban_checklist_items (uuid, checklist_id, name, position, checked, checked_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (item_uuid, checklist_id, name, position, 1 if checked else 0, checked_at, now, now)
                )
                item_id = cur.lastrowid

                # Log activity
                if card:
                    self._log_activity_internal(
                        conn, card["board_id"], "checklist_item_created", "checklist_item", entity_id=item_id,
                        list_id=card["list_id"], card_id=card["id"],
                        details={"name": name, "checklist_name": checklist["name"]}
                    )

                conn.commit()

                return self._get_checklist_item_by_id(conn, item_id)

            finally:
                conn.close()

    def get_checklist_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get a checklist item by ID."""
        with self._lock:
            conn = self._connect()
            try:
                return self._get_checklist_item_by_id(conn, item_id)
            finally:
                conn.close()

    def _get_checklist_item_by_id(self, conn: sqlite3.Connection, item_id: int) -> Optional[Dict[str, Any]]:
        """Internal method to get a checklist item by ID."""
        sql = """
            SELECT ci.id, ci.uuid, ci.checklist_id, ci.name, ci.position, ci.checked, ci.checked_at, ci.created_at, ci.updated_at
            FROM kanban_checklist_items ci
            JOIN kanban_checklists ch ON ci.checklist_id = ch.id
            JOIN kanban_cards c ON ch.card_id = c.id
            JOIN kanban_boards b ON c.board_id = b.id
            WHERE ci.id = ? AND b.user_id = ?
        """
        cur = conn.execute(sql, (item_id, self.user_id))
        row = cur.fetchone()

        if not row:
            return None

        return self._row_to_checklist_item_dict(row)

    def _row_to_checklist_item_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a checklist item row to a dictionary."""
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "checklist_id": row["checklist_id"],
            "name": row["name"],
            "position": row["position"],
            "checked": bool(row["checked"]),
            "checked_at": row["checked_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    def list_checklist_items(self, checklist_id: int) -> List[Dict[str, Any]]:
        """
        Get all items for a checklist, ordered by position.

        Args:
            checklist_id: The checklist ID.

        Returns:
            List of checklist items ordered by position.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify checklist exists and belongs to user
                checklist = self._get_checklist_by_id(conn, checklist_id)
                if not checklist:
                    raise NotFoundError("Checklist not found", entity="checklist", entity_id=checklist_id)

                sql = """
                    SELECT ci.id, ci.uuid, ci.checklist_id, ci.name, ci.position, ci.checked, ci.checked_at, ci.created_at, ci.updated_at
                    FROM kanban_checklist_items ci
                    WHERE ci.checklist_id = ?
                    ORDER BY ci.position ASC
                """
                cur = conn.execute(sql, (checklist_id,))

                return [self._row_to_checklist_item_dict(row) for row in cur.fetchall()]

            finally:
                conn.close()

    def update_checklist_item(
        self,
        item_id: int,
        name: Optional[str] = None,
        checked: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update a checklist item."""
        with self._lock:
            conn = self._connect()
            try:
                item = self._get_checklist_item_by_id(conn, item_id)
                if not item:
                    raise NotFoundError("Checklist item not found", entity="checklist_item", entity_id=item_id)

                updates = []
                params: List[Any] = []
                now = _utcnow_iso()

                if name is not None:
                    if not name.strip():
                        raise InputError("Checklist item name cannot be empty")
                    name = name.strip()
                    if len(name) > 500:
                        raise InputError("Checklist item name must be 500 characters or less")
                    updates.append("name = ?")
                    params.append(name)

                if checked is not None:
                    updates.append("checked = ?")
                    params.append(1 if checked else 0)
                    # Update checked_at timestamp
                    if checked and not item["checked"]:
                        updates.append("checked_at = ?")
                        params.append(now)
                    elif not checked and item["checked"]:
                        updates.append("checked_at = NULL")

                if not updates:
                    return item

                updates.append("updated_at = ?")
                params.append(now)
                params.append(item_id)

                sql = f"UPDATE kanban_checklist_items SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)

                # Log activity for check/uncheck (important user actions)
                if checked is not None:
                    checklist = self._get_checklist_by_id(conn, item["checklist_id"])
                    if checklist:
                        card = self._get_card_by_id(conn, checklist["card_id"])
                        if card:
                            action = "checklist_item_checked" if checked else "checklist_item_unchecked"
                            self._log_activity_internal(
                                conn, card["board_id"], action, "checklist_item", entity_id=item_id,
                                list_id=card["list_id"], card_id=card["id"],
                                details={"name": item["name"]}
                            )

                conn.commit()

                return self._get_checklist_item_by_id(conn, item_id)

            finally:
                conn.close()

    def reorder_checklist_items(self, checklist_id: int, item_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Reorder items in a checklist.

        Args:
            checklist_id: The checklist ID.
            item_ids: Item IDs in the desired order.

        Returns:
            Updated items in new order.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify checklist exists
                checklist = self._get_checklist_by_id(conn, checklist_id)
                if not checklist:
                    raise NotFoundError("Checklist not found", entity="checklist", entity_id=checklist_id)

                # Verify all items exist and belong to the checklist
                cur = conn.execute(
                    f"SELECT id FROM kanban_checklist_items WHERE checklist_id = ? AND id IN ({','.join('?' * len(item_ids))})",
                    [checklist_id] + item_ids
                )
                existing_ids = {row["id"] for row in cur.fetchall()}

                if len(existing_ids) != len(item_ids):
                    missing = set(item_ids) - existing_ids
                    raise InputError(f"Items not found or don't belong to checklist: {missing}")

                # Update positions
                now = _utcnow_iso()
                for position, item_id in enumerate(item_ids):
                    conn.execute(
                        "UPDATE kanban_checklist_items SET position = ?, updated_at = ? WHERE id = ?",
                        (position, now, item_id)
                    )

                conn.commit()

                return self.list_checklist_items(checklist_id)

            finally:
                conn.close()

    def delete_checklist_item(self, item_id: int) -> bool:
        """Delete a checklist item (hard delete)."""
        with self._lock:
            conn = self._connect()
            try:
                item = self._get_checklist_item_by_id(conn, item_id)
                if not item:
                    return False

                # Get checklist and card for activity logging
                checklist = self._get_checklist_by_id(conn, item["checklist_id"])
                if checklist:
                    card = self._get_card_by_id(conn, checklist["card_id"])
                    if card:
                        self._log_activity_internal(
                            conn, card["board_id"], "checklist_item_deleted", "checklist_item", entity_id=item_id,
                            list_id=card["list_id"], card_id=card["id"],
                            details={"name": item["name"]}
                        )

                conn.execute("DELETE FROM kanban_checklist_items WHERE id = ?", (item_id,))
                conn.commit()

                return True

            finally:
                conn.close()

    def get_checklist_with_items(self, checklist_id: int) -> Optional[Dict[str, Any]]:
        """Get a checklist with all its items included."""
        with self._lock:
            conn = self._connect()
            try:
                checklist = self._get_checklist_by_id(conn, checklist_id)
                if not checklist:
                    return None

                checklist["items"] = self.list_checklist_items(checklist_id)
                # Calculate progress
                total = len(checklist["items"])
                checked = sum(1 for item in checklist["items"] if item["checked"])
                checklist["total_items"] = total
                checklist["checked_items"] = checked
                checklist["progress_percent"] = round(checked / total * 100) if total > 0 else 0

                return checklist

            finally:
                conn.close()

    # =========================================================================
    # COMMENT OPERATIONS
    # =========================================================================

    def create_comment(
        self,
        card_id: int,
        content: str
    ) -> Dict[str, Any]:
        """
        Create a new comment on a card.

        Args:
            card_id: The card ID.
            content: Comment content (markdown supported).

        Returns:
            The created comment as a dictionary.
        """
        # Validate inputs
        if not content or not content.strip():
            raise InputError("Comment content is required")
        content = content.strip()
        if len(content) > self.MAX_COMMENT_SIZE:
            raise InputError(f"Comment must be {self.MAX_COMMENT_SIZE} characters or less")

        comment_uuid = _generate_uuid()
        now = _utcnow_iso()

        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists and belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                # Check comment limit
                cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM kanban_comments WHERE card_id = ? AND deleted = 0",
                    (card_id,)
                )
                count = cur.fetchone()["cnt"]
                if count >= self.MAX_COMMENTS_PER_CARD:
                    raise InputError(f"Maximum comments ({self.MAX_COMMENTS_PER_CARD}) per card reached")

                # Insert comment
                cur = conn.execute(
                    """
                    INSERT INTO kanban_comments (uuid, card_id, user_id, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (comment_uuid, card_id, self.user_id, content, now, now)
                )
                comment_id = cur.lastrowid

                # Log activity
                self._log_activity_internal(
                    conn, card["board_id"], "comment_created", "comment", entity_id=comment_id,
                    list_id=card["list_id"], card_id=card_id,
                    details={"preview": content[:100] if len(content) > 100 else content}
                )

                conn.commit()

                return self._get_comment_by_id(conn, comment_id)

            finally:
                conn.close()

    def get_comment(self, comment_id: int, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """Get a comment by ID."""
        with self._lock:
            conn = self._connect()
            try:
                return self._get_comment_by_id(conn, comment_id, include_deleted)
            finally:
                conn.close()

    def _get_comment_by_id(
        self,
        conn: sqlite3.Connection,
        comment_id: int,
        include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Internal method to get a comment by ID."""
        sql = """
            SELECT cm.id, cm.uuid, cm.card_id, cm.user_id, cm.content, cm.created_at, cm.updated_at, cm.deleted
            FROM kanban_comments cm
            JOIN kanban_cards c ON cm.card_id = c.id
            JOIN kanban_boards b ON c.board_id = b.id
            WHERE cm.id = ? AND b.user_id = ?
        """
        params: List[Any] = [comment_id, self.user_id]

        if not include_deleted:
            sql += " AND cm.deleted = 0"

        cur = conn.execute(sql, params)
        row = cur.fetchone()

        if not row:
            return None

        return self._row_to_comment_dict(row)

    def _row_to_comment_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a comment row to a dictionary."""
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "card_id": row["card_id"],
            "user_id": row["user_id"],
            "content": row["content"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "deleted": bool(row["deleted"])
        }

    def list_comments(
        self,
        card_id: int,
        include_deleted: bool = False,
        page: int = 1,
        per_page: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get comments for a card with pagination.

        Args:
            card_id: The card ID.
            include_deleted: If True, include soft-deleted comments.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (comments list, total count).
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists and belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                conditions = ["cm.card_id = ?"]
                params: List[Any] = [card_id]

                if not include_deleted:
                    conditions.append("cm.deleted = 0")

                where_clause = " AND ".join(conditions)

                # Get total count
                count_sql = f"SELECT COUNT(*) as cnt FROM kanban_comments cm WHERE {where_clause}"
                cur = conn.execute(count_sql, params)
                total = cur.fetchone()["cnt"]

                # Get paginated results
                offset = (page - 1) * per_page
                sql = f"""
                    SELECT cm.id, cm.uuid, cm.card_id, cm.user_id, cm.content, cm.created_at, cm.updated_at, cm.deleted
                    FROM kanban_comments cm
                    WHERE {where_clause}
                    ORDER BY cm.created_at DESC
                    LIMIT ? OFFSET ?
                """
                params.extend([per_page, offset])
                cur = conn.execute(sql, params)

                comments = [self._row_to_comment_dict(row) for row in cur.fetchall()]

                return comments, total

            finally:
                conn.close()

    def update_comment(
        self,
        comment_id: int,
        content: str
    ) -> Dict[str, Any]:
        """Update a comment."""
        # Validate inputs
        if not content or not content.strip():
            raise InputError("Comment content is required")
        content = content.strip()
        if len(content) > self.MAX_COMMENT_SIZE:
            raise InputError(f"Comment must be {self.MAX_COMMENT_SIZE} characters or less")

        with self._lock:
            conn = self._connect()
            try:
                comment = self._get_comment_by_id(conn, comment_id)
                if not comment:
                    raise NotFoundError("Comment not found", entity="comment", entity_id=comment_id)

                # Only the comment author can edit
                if comment["user_id"] != self.user_id:
                    raise InputError("You can only edit your own comments")

                # Get the card for activity logging
                card = self._get_card_by_id(conn, comment["card_id"])

                now = _utcnow_iso()
                conn.execute(
                    "UPDATE kanban_comments SET content = ?, updated_at = ? WHERE id = ?",
                    (content, now, comment_id)
                )

                # Log activity
                if card:
                    self._log_activity_internal(
                        conn, card["board_id"], "comment_updated", "comment", entity_id=comment_id,
                        list_id=card["list_id"], card_id=card["id"],
                        details={"preview": content[:100] if len(content) > 100 else content}
                    )

                conn.commit()

                return self._get_comment_by_id(conn, comment_id)

            finally:
                conn.close()

    def delete_comment(self, comment_id: int, hard_delete: bool = False) -> bool:
        """Delete a comment (soft delete by default)."""
        with self._lock:
            conn = self._connect()
            try:
                comment = self._get_comment_by_id(conn, comment_id, include_deleted=True)
                if not comment:
                    return False

                # Get the card for activity logging
                card = self._get_card_by_id(conn, comment["card_id"])

                if hard_delete:
                    conn.execute("DELETE FROM kanban_comments WHERE id = ?", (comment_id,))
                else:
                    now = _utcnow_iso()
                    conn.execute(
                        "UPDATE kanban_comments SET deleted = 1, updated_at = ? WHERE id = ?",
                        (now, comment_id)
                    )
                    # Log activity (only for soft delete)
                    if card:
                        self._log_activity_internal(
                            conn, card["board_id"], "comment_deleted", "comment", entity_id=comment_id,
                            list_id=card["list_id"], card_id=card["id"],
                            details={}
                        )

                conn.commit()
                return True

            finally:
                conn.close()

    # =========================================================================
    # EXPORT/IMPORT OPERATIONS
    # =========================================================================

    def export_board(
        self,
        board_id: int,
        include_archived: bool = False,
        include_deleted: bool = False
    ) -> Dict[str, Any]:
        """
        Export a board with all its data as a JSON-serializable dictionary.

        Args:
            board_id: The board ID to export.
            include_archived: Include archived items.
            include_deleted: Include soft-deleted items.

        Returns:
            Complete board data including lists, cards, labels, checklists, comments.

        Raises:
            NotFoundError: If board not found.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Get the board
                board = self._get_board_by_id(conn, board_id, include_deleted=include_deleted)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)

                # Build export structure
                export_data = {
                    "format": "tldw_kanban_v1",
                    "exported_at": _utcnow_iso(),
                    "board": {
                        "uuid": board["uuid"],
                        "name": board["name"],
                        "description": board["description"],
                        "metadata": board["metadata"],
                        "archived": board["archived"],
                        "created_at": board["created_at"],
                    },
                    "labels": [],
                    "lists": [],
                }

                # Export labels
                labels = self.list_labels(board_id)
                for label in labels:
                    export_data["labels"].append({
                        "uuid": label["uuid"],
                        "name": label["name"],
                        "color": label["color"],
                        "created_at": label["created_at"],
                    })

                # Build label ID -> UUID mapping for cards
                label_id_to_uuid = {label["id"]: label["uuid"] for label in labels}

                # Export lists
                lists = self.list_lists(board_id, include_archived=include_archived, include_deleted=include_deleted)
                for lst in lists:
                    list_export = {
                        "uuid": lst["uuid"],
                        "client_id": lst["client_id"],
                        "name": lst["name"],
                        "position": lst["position"],
                        "archived": lst["archived"],
                        "created_at": lst["created_at"],
                        "cards": [],
                    }

                    # Export cards in this list
                    cards = self.list_cards(lst["id"], include_archived=include_archived, include_deleted=include_deleted)
                    for card in cards:
                        card_export = {
                            "uuid": card["uuid"],
                            "client_id": card["client_id"],
                            "title": card["title"],
                            "description": card["description"],
                            "position": card["position"],
                            "due_date": card["due_date"],
                            "due_complete": card["due_complete"],
                            "start_date": card["start_date"],
                            "priority": card["priority"],
                            "archived": card["archived"],
                            "metadata": card["metadata"],
                            "created_at": card["created_at"],
                            "label_uuids": [],
                            "checklists": [],
                            "comments": [],
                        }

                        # Get card labels
                        card_labels = self.get_card_labels(card["id"])
                        card_export["label_uuids"] = [
                            label_id_to_uuid.get(lbl["id"], lbl["uuid"])
                            for lbl in card_labels
                        ]

                        # Get checklists with items
                        checklists = self.list_checklists(card["id"])
                        for checklist in checklists:
                            checklist_export = {
                                "uuid": checklist["uuid"],
                                "name": checklist["name"],
                                "position": checklist["position"],
                                "created_at": checklist["created_at"],
                                "items": [],
                            }

                            # Get checklist items
                            items = self.list_checklist_items(checklist["id"])
                            for item in items:
                                checklist_export["items"].append({
                                    "uuid": item["uuid"],
                                    "name": item["name"],
                                    "position": item["position"],
                                    "checked": item["checked"],
                                    "checked_at": item["checked_at"],
                                    "created_at": item["created_at"],
                                })

                            card_export["checklists"].append(checklist_export)

                        # Get comments (exclude deleted by default)
                        comments, _ = self.list_comments(card["id"], include_deleted=include_deleted)
                        for comment in comments:
                            card_export["comments"].append({
                                "uuid": comment["uuid"],
                                "content": comment["content"],
                                "created_at": comment["created_at"],
                                "updated_at": comment["updated_at"],
                            })

                        list_export["cards"].append(card_export)

                    export_data["lists"].append(list_export)

                return export_data

            finally:
                conn.close()

    def import_board(
        self,
        data: Dict[str, Any],
        board_name: Optional[str] = None,
        board_client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Import a board from exported JSON data.

        Supports both tldw_kanban_v1 format and Trello JSON export format.

        Args:
            data: The exported board data.
            board_name: Optional override for the board name.
            board_client_id: Optional client_id for the new board (auto-generated if not provided).

        Returns:
            The created board with summary of imported items.

        Raises:
            InputError: If the format is invalid or import fails.
        """
        # Detect format
        format_type = data.get("format")

        if format_type == "tldw_kanban_v1":
            return self._import_tldw_format(data, board_name, board_client_id)
        elif "cards" in data and "lists" in data and "name" in data:
            # Trello format detection
            return self._import_trello_format(data, board_name, board_client_id)
        else:
            raise InputError("Unrecognized import format. Must be tldw_kanban_v1 or Trello JSON format.")

    def _import_tldw_format(
        self,
        data: Dict[str, Any],
        board_name: Optional[str] = None,
        board_client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import from tldw_kanban_v1 format."""
        board_data = data.get("board", {})
        if not board_data:
            raise InputError("Invalid tldw_kanban_v1 format: missing 'board' data")

        # Create the board
        new_board = self.create_board(
            name=board_name or board_data.get("name", "Imported Board"),
            client_id=board_client_id or _generate_uuid(),
            description=board_data.get("description"),
            metadata=board_data.get("metadata")
        )
        board_id = new_board["id"]

        # Track imported counts
        import_stats = {
            "board_id": board_id,
            "lists_imported": 0,
            "cards_imported": 0,
            "labels_imported": 0,
            "checklists_imported": 0,
            "checklist_items_imported": 0,
            "comments_imported": 0,
        }

        # Import labels and track UUID mapping
        label_uuid_to_id: Dict[str, int] = {}
        for label_data in data.get("labels", []):
            try:
                label = self.create_label(
                    board_id=board_id,
                    name=label_data.get("name", "Unnamed Label"),
                    color=label_data.get("color", "gray")
                )
                label_uuid_to_id[label_data.get("uuid", "")] = label["id"]
                import_stats["labels_imported"] += 1
            except (InputError, KanbanDBError) as e:
                logger.warning(f"Failed to import label: {e}")

        # Import lists
        for list_data in data.get("lists", []):
            try:
                new_list = self.create_list(
                    board_id=board_id,
                    name=list_data.get("name", "Unnamed List"),
                    client_id=list_data.get("client_id") or _generate_uuid(),
                    position=list_data.get("position")
                )
                import_stats["lists_imported"] += 1

                # Import cards in this list
                for card_data in list_data.get("cards", []):
                    try:
                        new_card = self.create_card(
                            list_id=new_list["id"],
                            title=card_data.get("title", "Unnamed Card"),
                            client_id=card_data.get("client_id") or _generate_uuid(),
                            description=card_data.get("description"),
                            position=card_data.get("position"),
                            due_date=card_data.get("due_date"),
                            start_date=card_data.get("start_date"),
                            priority=card_data.get("priority"),
                            metadata=card_data.get("metadata")
                        )
                        import_stats["cards_imported"] += 1

                        # Assign labels
                        for label_uuid in card_data.get("label_uuids", []):
                            if label_uuid in label_uuid_to_id:
                                try:
                                    self.assign_label_to_card(new_card["id"], label_uuid_to_id[label_uuid])
                                except Exception:
                                    pass

                        # Import checklists
                        for checklist_data in card_data.get("checklists", []):
                            try:
                                new_checklist = self.create_checklist(
                                    card_id=new_card["id"],
                                    name=checklist_data.get("name", "Checklist"),
                                    position=checklist_data.get("position")
                                )
                                import_stats["checklists_imported"] += 1

                                # Import checklist items
                                for item_data in checklist_data.get("items", []):
                                    try:
                                        self.create_checklist_item(
                                            checklist_id=new_checklist["id"],
                                            name=item_data.get("name", "Item"),
                                            position=item_data.get("position"),
                                            checked=item_data.get("checked", False)
                                        )
                                        import_stats["checklist_items_imported"] += 1
                                    except Exception as e:
                                        logger.warning(f"Failed to import checklist item: {e}")
                            except Exception as e:
                                logger.warning(f"Failed to import checklist: {e}")

                        # Import comments
                        for comment_data in card_data.get("comments", []):
                            try:
                                self.create_comment(
                                    card_id=new_card["id"],
                                    content=comment_data.get("content", "")
                                )
                                import_stats["comments_imported"] += 1
                            except Exception as e:
                                logger.warning(f"Failed to import comment: {e}")

                    except Exception as e:
                        logger.warning(f"Failed to import card: {e}")

            except Exception as e:
                logger.warning(f"Failed to import list: {e}")

        # Log activity
        self.log_activity(
            board_id=board_id,
            action_type="board_imported",
            entity_type="board",
            entity_id=board_id,
            details=import_stats
        )

        return {
            "board": self.get_board(board_id),
            "import_stats": import_stats
        }

    def _import_trello_format(
        self,
        data: Dict[str, Any],
        board_name: Optional[str] = None,
        board_client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import from Trello JSON export format."""
        # Create the board
        new_board = self.create_board(
            name=board_name or data.get("name", "Imported Trello Board"),
            client_id=board_client_id or _generate_uuid(),
            description=data.get("desc")
        )
        board_id = new_board["id"]

        # Track imported counts
        import_stats = {
            "board_id": board_id,
            "lists_imported": 0,
            "cards_imported": 0,
            "labels_imported": 0,
            "checklists_imported": 0,
            "checklist_items_imported": 0,
            "comments_imported": 0,
        }

        # Map Trello colors to our colors
        color_map = {
            "green": "green",
            "yellow": "yellow",
            "orange": "orange",
            "red": "red",
            "purple": "purple",
            "blue": "blue",
            "sky": "blue",
            "lime": "green",
            "pink": "pink",
            "black": "gray",
            "": "gray",
            None: "gray",
        }

        # Import labels (Trello stores these at board level)
        label_id_map: Dict[str, int] = {}  # Trello ID -> our ID
        for label_data in data.get("labels", []):
            trello_color = label_data.get("color", "")
            our_color = color_map.get(trello_color, "gray")
            label_name = label_data.get("name") or our_color.title()
            try:
                label = self.create_label(
                    board_id=board_id,
                    name=label_name,
                    color=our_color
                )
                label_id_map[label_data.get("id", "")] = label["id"]
                import_stats["labels_imported"] += 1
            except Exception as e:
                logger.warning(f"Failed to import Trello label: {e}")

        # Build list ID map (Trello ID -> our ID)
        list_id_map: Dict[str, int] = {}
        trello_lists = data.get("lists", [])

        # Sort lists by position (Trello uses 'pos' field)
        trello_lists.sort(key=lambda x: x.get("pos", 0))

        for position, list_data in enumerate(trello_lists):
            if list_data.get("closed", False):
                continue  # Skip closed/archived lists

            try:
                new_list = self.create_list(
                    board_id=board_id,
                    name=list_data.get("name", "List"),
                    client_id=list_data.get("id") or _generate_uuid(),
                    position=position
                )
                list_id_map[list_data.get("id", "")] = new_list["id"]
                import_stats["lists_imported"] += 1
            except Exception as e:
                logger.warning(f"Failed to import Trello list: {e}")

        # Build checklist map (Trello ID -> checklist data)
        checklist_map: Dict[str, Dict] = {}
        for checklist in data.get("checklists", []):
            checklist_map[checklist.get("id", "")] = checklist

        # Import cards
        trello_cards = data.get("cards", [])
        # Sort cards by position within their list
        trello_cards.sort(key=lambda x: (x.get("idList", ""), x.get("pos", 0)))

        card_positions: Dict[str, int] = {}  # Track position per list

        for card_data in trello_cards:
            if card_data.get("closed", False):
                continue  # Skip closed/archived cards

            trello_list_id = card_data.get("idList", "")
            if trello_list_id not in list_id_map:
                continue  # Card's list wasn't imported

            our_list_id = list_id_map[trello_list_id]

            # Track card position within list
            if trello_list_id not in card_positions:
                card_positions[trello_list_id] = 0
            position = card_positions[trello_list_id]
            card_positions[trello_list_id] += 1

            try:
                new_card = self.create_card(
                    list_id=our_list_id,
                    title=card_data.get("name", "Card"),
                    client_id=card_data.get("id") or _generate_uuid(),
                    description=card_data.get("desc"),
                    position=position,
                    due_date=card_data.get("due"),
                )
                import_stats["cards_imported"] += 1

                # Assign labels
                for label_id in card_data.get("idLabels", []):
                    if label_id in label_id_map:
                        try:
                            self.assign_label_to_card(new_card["id"], label_id_map[label_id])
                        except Exception:
                            pass

                # Import checklists
                for checklist_id in card_data.get("idChecklists", []):
                    if checklist_id in checklist_map:
                        checklist_data = checklist_map[checklist_id]
                        try:
                            new_checklist = self.create_checklist(
                                card_id=new_card["id"],
                                name=checklist_data.get("name", "Checklist")
                            )
                            import_stats["checklists_imported"] += 1

                            # Import checklist items
                            check_items = checklist_data.get("checkItems", [])
                            check_items.sort(key=lambda x: x.get("pos", 0))

                            for item_pos, item_data in enumerate(check_items):
                                try:
                                    self.create_checklist_item(
                                        checklist_id=new_checklist["id"],
                                        name=item_data.get("name", "Item"),
                                        position=item_pos,
                                        checked=item_data.get("state") == "complete"
                                    )
                                    import_stats["checklist_items_imported"] += 1
                                except Exception as e:
                                    logger.warning(f"Failed to import Trello checklist item: {e}")
                        except Exception as e:
                            logger.warning(f"Failed to import Trello checklist: {e}")

            except Exception as e:
                logger.warning(f"Failed to import Trello card: {e}")

        # Log activity
        self.log_activity(
            board_id=board_id,
            action_type="board_imported_trello",
            entity_type="board",
            entity_id=board_id,
            details=import_stats
        )

        return {
            "board": self.get_board(board_id),
            "import_stats": import_stats
        }

    # =========================================================================
    # Phase 3: Bulk Operations
    # =========================================================================

    def bulk_move_cards(
        self,
        card_ids: List[int],
        target_list_id: int,
        start_position: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Move multiple cards to a target list.

        Args:
            card_ids: List of card IDs to move.
            target_list_id: The destination list ID.
            start_position: Optional starting position (cards placed sequentially from here).

        Returns:
            Dict with success status, moved count, and updated cards.
        """
        if not card_ids:
            return {"success": True, "moved_count": 0, "cards": []}

        with self._lock:
            conn = self._connect()
            try:
                # Verify target list exists
                target_list = self._get_list_by_id(conn, target_list_id)
                if not target_list:
                    raise NotFoundError("Target list not found", entity="list", entity_id=target_list_id)

                board_id = target_list["board_id"]

                # Get all cards and verify they exist and belong to the same board
                placeholders = ",".join("?" * len(card_ids))
                cur = conn.execute(
                    f"""
                    SELECT id, board_id, list_id, title FROM kanban_cards
                    WHERE id IN ({placeholders}) AND deleted = 0
                    """,
                    card_ids
                )
                cards = cur.fetchall()

                if len(cards) != len(card_ids):
                    found_ids = {c["id"] for c in cards}
                    missing = set(card_ids) - found_ids
                    raise NotFoundError(f"Cards not found: {missing}", entity="card")

                # Verify all cards are from the same board as target list
                for card in cards:
                    if card["board_id"] != board_id:
                        raise InputError(f"Card {card['id']} is not in the same board as the target list")

                # Determine starting position
                if start_position is None:
                    cur = conn.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM kanban_cards WHERE list_id = ? AND deleted = 0",
                        (target_list_id,)
                    )
                    start_position = cur.fetchone()["next_pos"]

                # Move cards
                now = _utcnow_iso()
                moved_cards = []
                for i, card_id in enumerate(card_ids):
                    old_list_id = next(c["list_id"] for c in cards if c["id"] == card_id)
                    new_position = start_position + i

                    conn.execute(
                        """
                        UPDATE kanban_cards
                        SET list_id = ?, position = ?, updated_at = ?, version = version + 1
                        WHERE id = ?
                        """,
                        (target_list_id, new_position, now, card_id)
                    )

                    # Log activity for each card
                    card_title = next(c["title"] for c in cards if c["id"] == card_id)
                    self._log_activity_internal(
                        conn, board_id, "card_moved", "card", entity_id=card_id,
                        list_id=target_list_id, card_id=card_id,
                        details={"from_list_id": old_list_id, "to_list_id": target_list_id, "title": card_title}
                    )

                conn.commit()

                # Fetch updated cards
                for card_id in card_ids:
                    moved_cards.append(self._get_card_by_id(conn, card_id))

                return {
                    "success": True,
                    "moved_count": len(moved_cards),
                    "cards": moved_cards
                }

            finally:
                conn.close()

    def bulk_archive_cards(self, card_ids: List[int], archive: bool = True) -> Dict[str, Any]:
        """
        Archive or unarchive multiple cards.

        Args:
            card_ids: List of card IDs.
            archive: True to archive, False to unarchive.

        Returns:
            Dict with success status and archived/unarchived count.
        """
        if not card_ids:
            return {"success": True, "archived_count" if archive else "unarchived_count": 0}

        with self._lock:
            conn = self._connect()
            try:
                # Get all cards and verify they exist
                placeholders = ",".join("?" * len(card_ids))
                cur = conn.execute(
                    f"""
                    SELECT id, board_id, list_id, title FROM kanban_cards
                    WHERE id IN ({placeholders}) AND deleted = 0
                    """,
                    card_ids
                )
                cards = cur.fetchall()

                if len(cards) != len(card_ids):
                    found_ids = {c["id"] for c in cards}
                    missing = set(card_ids) - found_ids
                    raise NotFoundError(f"Cards not found: {missing}", entity="card")

                # Verify all cards belong to the same user (same board check)
                board_ids = {c["board_id"] for c in cards}
                for bid in board_ids:
                    board = self._get_board_by_id(conn, bid)
                    if not board or board["user_id"] != self.user_id:
                        raise NotFoundError("Board not found or access denied", entity="board")

                # Archive/unarchive cards
                now = _utcnow_iso()
                action_type = "card_archived" if archive else "card_unarchived"

                for card in cards:
                    conn.execute(
                        """
                        UPDATE kanban_cards
                        SET archived = ?, archived_at = ?, updated_at = ?, version = version + 1
                        WHERE id = ?
                        """,
                        (1 if archive else 0, now if archive else None, now, card["id"])
                    )

                    self._log_activity_internal(
                        conn, card["board_id"], action_type, "card", entity_id=card["id"],
                        list_id=card["list_id"], card_id=card["id"],
                        details={"title": card["title"]}
                    )

                conn.commit()

                result_key = "archived_count" if archive else "unarchived_count"
                return {"success": True, result_key: len(cards)}

            finally:
                conn.close()

    def bulk_delete_cards(self, card_ids: List[int], hard_delete: bool = False) -> Dict[str, Any]:
        """
        Soft or hard delete multiple cards.

        Args:
            card_ids: List of card IDs.
            hard_delete: If True, permanently delete. If False, soft delete.

        Returns:
            Dict with success status and deleted count.
        """
        if not card_ids:
            return {"success": True, "deleted_count": 0}

        with self._lock:
            conn = self._connect()
            try:
                # Get all cards and verify they exist
                placeholders = ",".join("?" * len(card_ids))
                cur = conn.execute(
                    f"""
                    SELECT id, board_id, list_id, title FROM kanban_cards
                    WHERE id IN ({placeholders}) {"" if hard_delete else "AND deleted = 0"}
                    """,
                    card_ids
                )
                cards = cur.fetchall()

                if len(cards) != len(card_ids):
                    found_ids = {c["id"] for c in cards}
                    missing = set(card_ids) - found_ids
                    raise NotFoundError(f"Cards not found: {missing}", entity="card")

                # Verify all cards belong to the same user
                board_ids = {c["board_id"] for c in cards}
                for bid in board_ids:
                    board = self._get_board_by_id(conn, bid)
                    if not board or board["user_id"] != self.user_id:
                        raise NotFoundError("Board not found or access denied", entity="board")

                now = _utcnow_iso()

                if hard_delete:
                    # Permanently delete
                    conn.execute(
                        f"DELETE FROM kanban_cards WHERE id IN ({placeholders})",
                        card_ids
                    )
                else:
                    # Soft delete
                    for card in cards:
                        conn.execute(
                            """
                            UPDATE kanban_cards
                            SET deleted = 1, deleted_at = ?, updated_at = ?, version = version + 1
                            WHERE id = ?
                            """,
                            (now, now, card["id"])
                        )

                        self._log_activity_internal(
                            conn, card["board_id"], "card_deleted", "card", entity_id=card["id"],
                            list_id=card["list_id"], card_id=card["id"],
                            details={"title": card["title"]}
                        )

                conn.commit()

                return {"success": True, "deleted_count": len(cards)}

            finally:
                conn.close()

    def bulk_label_cards(
        self,
        card_ids: List[int],
        add_label_ids: Optional[List[int]] = None,
        remove_label_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Add and/or remove labels from multiple cards.

        Args:
            card_ids: List of card IDs.
            add_label_ids: Label IDs to add to all cards.
            remove_label_ids: Label IDs to remove from all cards.

        Returns:
            Dict with success status and updated count.
        """
        if not card_ids:
            return {"success": True, "updated_count": 0}

        add_label_ids = add_label_ids or []
        remove_label_ids = remove_label_ids or []

        if not add_label_ids and not remove_label_ids:
            return {"success": True, "updated_count": 0}

        with self._lock:
            conn = self._connect()
            try:
                # Get all cards and verify they exist
                placeholders = ",".join("?" * len(card_ids))
                cur = conn.execute(
                    f"""
                    SELECT id, board_id, title FROM kanban_cards
                    WHERE id IN ({placeholders}) AND deleted = 0
                    """,
                    card_ids
                )
                cards = cur.fetchall()

                if len(cards) != len(card_ids):
                    found_ids = {c["id"] for c in cards}
                    missing = set(card_ids) - found_ids
                    raise NotFoundError(f"Cards not found: {missing}", entity="card")

                # Get unique board IDs
                board_ids = {c["board_id"] for c in cards}

                # Verify labels belong to the same boards as the cards
                all_label_ids = set(add_label_ids) | set(remove_label_ids)
                if all_label_ids:
                    label_placeholders = ",".join("?" * len(all_label_ids))
                    cur = conn.execute(
                        f"SELECT id, board_id, name FROM kanban_labels WHERE id IN ({label_placeholders})",
                        list(all_label_ids)
                    )
                    labels = {row["id"]: row for row in cur.fetchall()}

                    for label_id in all_label_ids:
                        if label_id not in labels:
                            raise NotFoundError(f"Label {label_id} not found", entity="label", entity_id=label_id)
                        if labels[label_id]["board_id"] not in board_ids:
                            raise InputError(f"Label {label_id} does not belong to the same board as the cards")

                now = _utcnow_iso()
                updated_count = 0

                for card in cards:
                    card_updated = False

                    # Remove labels
                    if remove_label_ids:
                        remove_placeholders = ",".join("?" * len(remove_label_ids))
                        cur = conn.execute(
                            f"DELETE FROM kanban_card_labels WHERE card_id = ? AND label_id IN ({remove_placeholders})",
                            [card["id"]] + remove_label_ids
                        )
                        if cur.rowcount > 0:
                            card_updated = True
                            for label_id in remove_label_ids:
                                if label_id in labels:
                                    self._log_activity_internal(
                                        conn, card["board_id"], "label_removed", "card",
                                        entity_id=card["id"], card_id=card["id"],
                                        details={"label_name": labels[label_id]["name"], "card_title": card["title"]}
                                    )

                    # Add labels
                    if add_label_ids:
                        for label_id in add_label_ids:
                            try:
                                conn.execute(
                                    "INSERT INTO kanban_card_labels (card_id, label_id, created_at) VALUES (?, ?, ?)",
                                    (card["id"], label_id, now)
                                )
                                card_updated = True
                                self._log_activity_internal(
                                    conn, card["board_id"], "label_assigned", "card",
                                    entity_id=card["id"], card_id=card["id"],
                                    details={"label_name": labels[label_id]["name"], "card_title": card["title"]}
                                )
                            except sqlite3.IntegrityError:
                                # Label already assigned, skip
                                pass

                    if card_updated:
                        # Update card's updated_at
                        conn.execute(
                            "UPDATE kanban_cards SET updated_at = ?, version = version + 1 WHERE id = ?",
                            (now, card["id"])
                        )
                        updated_count += 1

                conn.commit()

                return {"success": True, "updated_count": updated_count}

            finally:
                conn.close()

    # =========================================================================
    # Phase 3: Card Filtering
    # =========================================================================

    def get_board_cards_filtered(
        self,
        board_id: int,
        label_ids: Optional[List[int]] = None,
        priority: Optional[str] = None,
        due_before: Optional[str] = None,
        due_after: Optional[str] = None,
        overdue: Optional[bool] = None,
        has_due_date: Optional[bool] = None,
        has_checklist: Optional[bool] = None,
        is_complete: Optional[bool] = None,
        include_archived: bool = False,
        include_deleted: bool = False,
        page: int = 1,
        per_page: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get filtered cards for a board.

        Args:
            board_id: The board ID.
            label_ids: Filter by label IDs (cards must have ALL specified labels).
            priority: Filter by priority (low, medium, high, urgent).
            due_before: Filter by due date before this timestamp.
            due_after: Filter by due date after this timestamp.
            overdue: If True, only cards with due_date < now AND due_complete = 0.
            has_due_date: If True, only cards with due_date set. If False, only cards without.
            has_checklist: If True, only cards with at least one checklist.
            is_complete: If True, only cards where all checklist items are checked.
            include_archived: Include archived cards.
            include_deleted: Include soft-deleted cards.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (cards list, total count).
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify board exists and belongs to user
                board = self._get_board_by_id(conn, board_id)
                if not board:
                    raise NotFoundError("Board not found", entity="board", entity_id=board_id)

                # Build query
                conditions = ["c.board_id = ?"]
                params: List[Any] = [board_id]

                if not include_deleted:
                    conditions.append("c.deleted = 0")
                if not include_archived:
                    conditions.append("c.archived = 0")

                if priority:
                    conditions.append("c.priority = ?")
                    params.append(priority)

                if due_before:
                    conditions.append("c.due_date < ?")
                    params.append(due_before)

                if due_after:
                    conditions.append("c.due_date > ?")
                    params.append(due_after)

                if overdue is True:
                    now = _utcnow_iso()
                    conditions.append("c.due_date IS NOT NULL AND c.due_date < ? AND c.due_complete = 0")
                    params.append(now)

                if has_due_date is True:
                    conditions.append("c.due_date IS NOT NULL")
                elif has_due_date is False:
                    conditions.append("c.due_date IS NULL")

                # Label filtering - cards must have ALL specified labels
                if label_ids:
                    for label_id in label_ids:
                        conditions.append(
                            "EXISTS (SELECT 1 FROM kanban_card_labels cl WHERE cl.card_id = c.id AND cl.label_id = ?)"
                        )
                        params.append(label_id)

                # Checklist filtering
                if has_checklist is True:
                    conditions.append(
                        "EXISTS (SELECT 1 FROM kanban_checklists ch WHERE ch.card_id = c.id)"
                    )
                elif has_checklist is False:
                    conditions.append(
                        "NOT EXISTS (SELECT 1 FROM kanban_checklists ch WHERE ch.card_id = c.id)"
                    )

                # Complete filtering (all checklist items checked)
                if is_complete is True:
                    conditions.append("""
                        EXISTS (SELECT 1 FROM kanban_checklists ch WHERE ch.card_id = c.id)
                        AND NOT EXISTS (
                            SELECT 1 FROM kanban_checklists ch
                            JOIN kanban_checklist_items ci ON ci.checklist_id = ch.id
                            WHERE ch.card_id = c.id AND ci.checked = 0
                        )
                    """)
                elif is_complete is False:
                    conditions.append("""
                        EXISTS (
                            SELECT 1 FROM kanban_checklists ch
                            JOIN kanban_checklist_items ci ON ci.checklist_id = ch.id
                            WHERE ch.card_id = c.id AND ci.checked = 0
                        )
                    """)

                where_clause = " AND ".join(conditions)

                # Count total
                count_sql = f"SELECT COUNT(*) as cnt FROM kanban_cards c WHERE {where_clause}"
                cur = conn.execute(count_sql, params)
                total = cur.fetchone()["cnt"]

                # Get paginated results
                offset = (page - 1) * per_page
                query_sql = f"""
                    SELECT c.* FROM kanban_cards c
                    WHERE {where_clause}
                    ORDER BY c.list_id, c.position
                    LIMIT ? OFFSET ?
                """
                cur = conn.execute(query_sql, params + [per_page, offset])
                rows = cur.fetchall()

                cards = [self._row_to_card_dict(row) for row in rows]

                return cards, total

            finally:
                conn.close()

    # =========================================================================
    # Phase 3: Toggle All Checklist Items
    # =========================================================================

    def toggle_all_checklist_items(self, checklist_id: int, checked: bool) -> Dict[str, Any]:
        """
        Check or uncheck all items in a checklist.

        Args:
            checklist_id: The checklist ID.
            checked: True to check all, False to uncheck all.

        Returns:
            Updated checklist with items.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Get the checklist
                checklist = self.get_checklist(checklist_id)
                if not checklist:
                    raise NotFoundError("Checklist not found", entity="checklist", entity_id=checklist_id)

                # Get the card to verify ownership and get board_id
                card = self._get_card_by_id(conn, checklist["card_id"])
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=checklist["card_id"])

                now = _utcnow_iso()

                # Update all items
                if checked:
                    conn.execute(
                        """
                        UPDATE kanban_checklist_items
                        SET checked = 1, checked_at = ?, updated_at = ?
                        WHERE checklist_id = ? AND checked = 0
                        """,
                        (now, now, checklist_id)
                    )
                else:
                    conn.execute(
                        """
                        UPDATE kanban_checklist_items
                        SET checked = 0, checked_at = NULL, updated_at = ?
                        WHERE checklist_id = ? AND checked = 1
                        """,
                        (now, checklist_id)
                    )

                # Log activity
                action_type = "checklist_items_all_checked" if checked else "checklist_items_all_unchecked"
                self._log_activity_internal(
                    conn, card["board_id"], action_type, "checklist",
                    entity_id=checklist_id, card_id=card["id"],
                    details={"checklist_name": checklist["name"], "checked": checked}
                )

                conn.commit()

                # Return updated checklist with items
                return self.get_checklist_with_items(checklist_id)

            finally:
                conn.close()

    # =========================================================================
    # Phase 3: Enhanced Card Copy (with checklists)
    # =========================================================================

    def copy_card_with_checklists(
        self,
        card_id: int,
        target_list_id: int,
        new_client_id: str,
        position: Optional[int] = None,
        new_title: Optional[str] = None,
        copy_checklists: bool = True,
        copy_labels: bool = True
    ) -> Dict[str, Any]:
        """
        Copy a card to a list, optionally including checklists.

        Args:
            card_id: The source card ID.
            target_list_id: The destination list ID.
            new_client_id: Client-generated unique ID for the copy.
            position: Optional position in the target list.
            new_title: Optional new title (defaults to "Copy of {original}").
            copy_checklists: Whether to copy checklists (default True).
            copy_labels: Whether to copy labels (default True).

        Returns:
            The copied card with checklists if copied.
        """
        with self._lock:
            conn = self._connect()
            try:
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError("Card not found", entity="card", entity_id=card_id)

                target_list = self._get_list_by_id(conn, target_list_id)
                if not target_list:
                    raise NotFoundError("Target list not found", entity="list", entity_id=target_list_id)

                # Verify target list is in the same board
                if target_list["board_id"] != card["board_id"]:
                    raise InputError("Cannot copy card to a list in a different board")

                # Generate title if not provided
                if new_title is None:
                    new_title = f"Copy of {card['title']}"

                # Get target position
                if position is None:
                    cur = conn.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM kanban_cards WHERE list_id = ? AND deleted = 0",
                        (target_list_id,)
                    )
                    position = cur.fetchone()["next_pos"]

                card_uuid = _generate_uuid()
                now = _utcnow_iso()

                # Insert the copy
                cur = conn.execute(
                    """
                    INSERT INTO kanban_cards
                    (uuid, board_id, list_id, client_id, title, description, position,
                     due_date, start_date, priority, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (card_uuid, card["board_id"], target_list_id, new_client_id,
                     new_title, card["description"], position,
                     card["due_date"], card["start_date"], card["priority"],
                     json.dumps(card["metadata"]) if card["metadata"] else None,
                     now, now)
                )
                new_card_id = cur.lastrowid

                # Copy labels
                if copy_labels:
                    conn.execute(
                        """
                        INSERT INTO kanban_card_labels (card_id, label_id, created_at)
                        SELECT ?, label_id, ? FROM kanban_card_labels WHERE card_id = ?
                        """,
                        (new_card_id, now, card_id)
                    )

                # Copy checklists
                checklists_copied = 0
                items_copied = 0
                if copy_checklists:
                    # Get source checklists
                    cur = conn.execute(
                        "SELECT * FROM kanban_checklists WHERE card_id = ? ORDER BY position",
                        (card_id,)
                    )
                    source_checklists = cur.fetchall()

                    for checklist in source_checklists:
                        checklist_uuid = _generate_uuid()
                        cur = conn.execute(
                            """
                            INSERT INTO kanban_checklists (uuid, card_id, name, position, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (checklist_uuid, new_card_id, checklist["name"], checklist["position"], now, now)
                        )
                        new_checklist_id = cur.lastrowid
                        checklists_copied += 1

                        # Copy checklist items
                        cur = conn.execute(
                            "SELECT * FROM kanban_checklist_items WHERE checklist_id = ? ORDER BY position",
                            (checklist["id"],)
                        )
                        source_items = cur.fetchall()

                        for item in source_items:
                            item_uuid = _generate_uuid()
                            conn.execute(
                                """
                                INSERT INTO kanban_checklist_items
                                (uuid, checklist_id, name, position, checked, checked_at, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (item_uuid, new_checklist_id, item["name"], item["position"],
                                 item["checked"], item["checked_at"], now, now)
                            )
                            items_copied += 1

                # Log activity
                self._log_activity_internal(
                    conn, card["board_id"], "card_copied", "card", entity_id=new_card_id,
                    list_id=target_list_id, card_id=new_card_id,
                    details={
                        "title": new_title,
                        "source_card_id": card_id,
                        "target_list_id": target_list_id,
                        "checklists_copied": checklists_copied,
                        "checklist_items_copied": items_copied
                    }
                )

                conn.commit()

                return self._get_card_by_id(conn, new_card_id)

            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint" in str(e) and "client_id" in str(e):
                    raise ConflictError(
                        f"Card with client_id '{new_client_id}' already exists",
                        entity="card",
                        entity_id=new_client_id
                    )
                raise KanbanDBError(f"Database error: {e}") from e
            finally:
                conn.close()

    # ==========================================================================
    # Card Links Methods (Phase 5: Content Integration)
    # ==========================================================================

    def add_card_link(
        self,
        card_id: int,
        linked_type: str,
        linked_id: str
    ) -> Dict[str, Any]:
        """
        Add a link from a card to a media item or note.

        Args:
            card_id: The card to add the link to.
            linked_type: Type of linked content ('media' or 'note').
            linked_id: ID of the linked content.

        Returns:
            The created link.

        Raises:
            NotFoundError: If the card doesn't exist.
            InputError: If linked_type is invalid.
            ConflictError: If the link already exists.
        """
        if linked_type not in ("media", "note"):
            raise InputError(f"Invalid linked_type: {linked_type}. Must be 'media' or 'note'.")

        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists and belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError(f"Card {card_id} not found", entity="card", entity_id=card_id)

                link_uuid = _generate_uuid()
                now = _utcnow_iso()

                cur = conn.execute(
                    """
                    INSERT INTO kanban_card_links (uuid, card_id, linked_type, linked_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (link_uuid, card_id, linked_type, linked_id, now)
                )
                link_id = cur.lastrowid

                # Log activity
                self._log_activity_internal(
                    conn, card["board_id"], "link_added", "card_link", entity_id=link_id,
                    card_id=card_id, list_id=card["list_id"],
                    details={"linked_type": linked_type, "linked_id": linked_id}
                )

                conn.commit()

                return {
                    "id": link_id,
                    "card_id": card_id,
                    "linked_type": linked_type,
                    "linked_id": linked_id,
                    "created_at": now
                }

            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint" in str(e):
                    raise ConflictError(
                        f"Link already exists from card {card_id} to {linked_type}:{linked_id}",
                        entity="card_link"
                    )
                raise KanbanDBError(f"Database error: {e}") from e
            finally:
                conn.close()

    def get_card_links(
        self,
        card_id: int,
        linked_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all links for a card.

        Args:
            card_id: The card to get links for.
            linked_type: Optional filter by type ('media' or 'note').

        Returns:
            List of card links.

        Raises:
            NotFoundError: If the card doesn't exist.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists and belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError(f"Card {card_id} not found", entity="card", entity_id=card_id)

                if linked_type:
                    cur = conn.execute(
                        """
                        SELECT id, card_id, linked_type, linked_id, created_at
                        FROM kanban_card_links
                        WHERE card_id = ? AND linked_type = ?
                        ORDER BY created_at DESC
                        """,
                        (card_id, linked_type)
                    )
                else:
                    cur = conn.execute(
                        """
                        SELECT id, card_id, linked_type, linked_id, created_at
                        FROM kanban_card_links
                        WHERE card_id = ?
                        ORDER BY created_at DESC
                        """,
                        (card_id,)
                    )

                return [dict(row) for row in cur.fetchall()]

            finally:
                conn.close()

    def get_linked_content_counts(self, card_id: int) -> Dict[str, int]:
        """
        Get counts of linked content by type for a card.

        Args:
            card_id: The card to get link counts for.

        Returns:
            Dict with counts by type: {"media": N, "note": M}

        Raises:
            NotFoundError: If the card doesn't exist.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists and belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError(f"Card {card_id} not found", entity="card", entity_id=card_id)

                cur = conn.execute(
                    """
                    SELECT linked_type, COUNT(*) as count
                    FROM kanban_card_links
                    WHERE card_id = ?
                    GROUP BY linked_type
                    """,
                    (card_id,)
                )

                counts = {"media": 0, "note": 0}
                for row in cur.fetchall():
                    counts[row["linked_type"]] = row["count"]

                return counts

            finally:
                conn.close()

    def remove_card_link(
        self,
        card_id: int,
        linked_type: str,
        linked_id: str
    ) -> bool:
        """
        Remove a link from a card.

        Args:
            card_id: The card to remove the link from.
            linked_type: Type of linked content.
            linked_id: ID of the linked content.

        Returns:
            True if the link was removed, False if it didn't exist.

        Raises:
            NotFoundError: If the card doesn't exist.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists and belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError(f"Card {card_id} not found", entity="card", entity_id=card_id)

                cur = conn.execute(
                    """
                    DELETE FROM kanban_card_links
                    WHERE card_id = ? AND linked_type = ? AND linked_id = ?
                    """,
                    (card_id, linked_type, linked_id)
                )

                if cur.rowcount > 0:
                    # Log activity
                    self._log_activity_internal(
                        conn, card["board_id"], "link_removed", "card_link",
                        card_id=card_id, list_id=card["list_id"],
                        details={"linked_type": linked_type, "linked_id": linked_id}
                    )
                    conn.commit()
                    return True

                return False

            finally:
                conn.close()

    def remove_card_link_by_id(self, link_id: int) -> bool:
        """
        Remove a card link by its ID.

        Args:
            link_id: The link ID to remove.

        Returns:
            True if the link was removed, False if it didn't exist.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Get link details first for activity logging
                cur = conn.execute(
                    """
                    SELECT cl.*, c.board_id, c.list_id
                    FROM kanban_card_links cl
                    JOIN kanban_cards c ON cl.card_id = c.id
                    JOIN kanban_boards b ON c.board_id = b.id
                    WHERE cl.id = ? AND b.user_id = ?
                    """,
                    (link_id, self.user_id)
                )
                link = cur.fetchone()

                if not link:
                    return False

                conn.execute("DELETE FROM kanban_card_links WHERE id = ?", (link_id,))

                # Log activity
                self._log_activity_internal(
                    conn, link["board_id"], "link_removed", "card_link",
                    card_id=link["card_id"], list_id=link["list_id"],
                    details={"linked_type": link["linked_type"], "linked_id": link["linked_id"]}
                )
                conn.commit()
                return True

            finally:
                conn.close()

    def bulk_add_card_links(
        self,
        card_id: int,
        links: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Add multiple links to a card at once.

        Args:
            card_id: The card to add links to.
            links: List of dicts with "linked_type" and "linked_id".

        Returns:
            Dict with added_count, skipped_count, and links list.

        Raises:
            NotFoundError: If the card doesn't exist.
            InputError: If any linked_type is invalid.
        """
        # Validate all linked_types first
        for link in links:
            if link.get("linked_type") not in ("media", "note"):
                raise InputError(
                    f"Invalid linked_type: {link.get('linked_type')}. Must be 'media' or 'note'."
                )

        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists and belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError(f"Card {card_id} not found", entity="card", entity_id=card_id)

                added_links = []
                skipped_count = 0
                now = _utcnow_iso()

                for link in links:
                    link_uuid = _generate_uuid()
                    linked_type = link["linked_type"]
                    linked_id = link["linked_id"]

                    try:
                        cur = conn.execute(
                            """
                            INSERT INTO kanban_card_links (uuid, card_id, linked_type, linked_id, created_at)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (link_uuid, card_id, linked_type, linked_id, now)
                        )
                        link_id = cur.lastrowid
                        added_links.append({
                            "id": link_id,
                            "card_id": card_id,
                            "linked_type": linked_type,
                            "linked_id": linked_id,
                            "created_at": now
                        })
                    except sqlite3.IntegrityError:
                        # Duplicate link, skip
                        skipped_count += 1

                if added_links:
                    # Log activity
                    self._log_activity_internal(
                        conn, card["board_id"], "links_bulk_added", "card",
                        card_id=card_id, list_id=card["list_id"],
                        details={"added_count": len(added_links), "skipped_count": skipped_count}
                    )

                conn.commit()

                return {
                    "added_count": len(added_links),
                    "skipped_count": skipped_count,
                    "links": added_links
                }

            finally:
                conn.close()

    def bulk_remove_card_links(
        self,
        card_id: int,
        links: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Remove multiple links from a card at once.

        Args:
            card_id: The card to remove links from.
            links: List of dicts with "linked_type" and "linked_id".

        Returns:
            Dict with removed_count.

        Raises:
            NotFoundError: If the card doesn't exist.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Verify card exists and belongs to user
                card = self._get_card_by_id(conn, card_id)
                if not card:
                    raise NotFoundError(f"Card {card_id} not found", entity="card", entity_id=card_id)

                removed_count = 0

                for link in links:
                    linked_type = link.get("linked_type")
                    linked_id = link.get("linked_id")

                    cur = conn.execute(
                        """
                        DELETE FROM kanban_card_links
                        WHERE card_id = ? AND linked_type = ? AND linked_id = ?
                        """,
                        (card_id, linked_type, linked_id)
                    )
                    removed_count += cur.rowcount

                if removed_count > 0:
                    # Log activity
                    self._log_activity_internal(
                        conn, card["board_id"], "links_bulk_removed", "card",
                        card_id=card_id, list_id=card["list_id"],
                        details={"removed_count": removed_count}
                    )
                    conn.commit()

                return {"removed_count": removed_count}

            finally:
                conn.close()

    def get_cards_by_linked_content(
        self,
        linked_type: str,
        linked_id: str,
        include_archived: bool = False,
        include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find all cards that link to a specific media item or note.

        This is the bidirectional lookup - given a media item or note ID,
        find all Kanban cards that reference it.

        Args:
            linked_type: Type of content ('media' or 'note').
            linked_id: ID of the content.
            include_archived: Include archived cards.
            include_deleted: Include soft-deleted cards.

        Returns:
            List of cards with board/list context and link info.
        """
        with self._lock:
            conn = self._connect()
            try:
                query = """
                    SELECT
                        c.id,
                        c.title,
                        c.description,
                        c.board_id,
                        b.name as board_name,
                        c.list_id,
                        l.name as list_name,
                        c.position,
                        c.archived as is_archived,
                        c.deleted as is_deleted,
                        cl.id as link_id,
                        cl.created_at as linked_at
                    FROM kanban_card_links cl
                    JOIN kanban_cards c ON cl.card_id = c.id
                    JOIN kanban_boards b ON c.board_id = b.id
                    JOIN kanban_lists l ON c.list_id = l.id
                    WHERE cl.linked_type = ?
                      AND cl.linked_id = ?
                      AND b.user_id = ?
                """

                params: List[Any] = [linked_type, linked_id, self.user_id]

                if not include_archived:
                    query += " AND c.archived = 0"

                if not include_deleted:
                    query += " AND c.deleted = 0"

                query += " ORDER BY cl.created_at DESC"

                cur = conn.execute(query, params)
                return [dict(row) for row in cur.fetchall()]

            finally:
                conn.close()

    def get_card_counts_for_lists(self, list_ids: List[int]) -> Dict[int, int]:
        """
        Get card counts for multiple lists in a single query.

        Args:
            list_ids: List of list IDs to get card counts for.

        Returns:
            Dict mapping list_id -> card count.
        """
        if not list_ids:
            return {}

        with self._lock:
            conn = self._connect()
            try:
                placeholders = ",".join("?" * len(list_ids))
                cur = conn.execute(
                    f"""
                    SELECT list_id, COUNT(*) as count
                    FROM kanban_cards
                    WHERE list_id IN ({placeholders}) AND deleted = 0
                    GROUP BY list_id
                    """,
                    list_ids
                )

                return {row["list_id"]: row["count"] for row in cur.fetchall()}

            finally:
                conn.close()
