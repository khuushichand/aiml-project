# ManuscriptDB.py
# Description: Helper class wrapping CRUD operations for manuscript tables
#   (projects, parts, chapters, scenes) stored in the ChaChaNotes DB.
#
from __future__ import annotations

"""
ManuscriptDB.py
---------------

Thin helper that receives a :class:`CharactersRAGDB` instance and exposes
ergonomic CRUD methods for the four manuscript tables introduced in schema V41:

- ``manuscript_projects``
- ``manuscript_parts``
- ``manuscript_chapters``
- ``manuscript_scenes``

All public methods use the underlying DB's ``transaction()`` context manager
and follow the existing optimistic-locking / soft-delete conventions.
"""

import json  # noqa: E402
import uuid  # noqa: E402
from typing import Any  # noqa: E402

from loguru import logger  # noqa: E402

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (  # noqa: E402
    CharactersRAGDB,
    ConflictError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_PROJECT_STATUSES = frozenset(
    {"draft", "outlining", "writing", "revising", "complete", "archived"}
)
_VALID_CHAPTER_STATUSES = frozenset({"outline", "draft", "revising", "final"})
_VALID_SCENE_STATUSES = frozenset({"outline", "draft", "revising", "final"})

_REORDER_ENTITY_TABLES = {
    "part": "manuscript_parts",
    "chapter": "manuscript_chapters",
    "scene": "manuscript_scenes",
}


def _word_count(text: str | None) -> int:
    """Return the number of whitespace-delimited words in *text*."""
    if text and text.strip():
        return len(text.split())
    return 0


# ---------------------------------------------------------------------------
# ManuscriptDBHelper
# ---------------------------------------------------------------------------


class ManuscriptDBHelper:
    """High-level CRUD facade for manuscript tables.

    Parameters
    ----------
    db:
        A fully-initialised :class:`CharactersRAGDB` whose schema already
        includes the V41 manuscript tables.
    """

    # Column allowlists for update methods (defense-in-depth against injection)
    _UPDATABLE_PROJECT_COLS = frozenset({
        "title", "subtitle", "author", "genre", "status", "synopsis",
        "target_word_count", "settings_json",
    })
    _UPDATABLE_PART_COLS = frozenset({"title", "sort_order", "synopsis"})
    _UPDATABLE_CHAPTER_COLS = frozenset({
        "title", "part_id", "sort_order", "synopsis", "pov_character_id", "status",
    })
    _UPDATABLE_SCENE_COLS = frozenset({
        "title", "chapter_id", "sort_order", "content_json", "content_plain",
        "synopsis", "pov_character_id", "status", "word_count",
    })
    _UPDATABLE_CHARACTER_COLS = frozenset({
        "name", "role", "cast_group", "full_name", "age", "gender",
        "appearance", "personality", "backstory", "motivation", "arc_summary",
        "notes", "custom_fields_json", "sort_order",
    })
    _UPDATABLE_WORLD_INFO_COLS = frozenset({
        "name", "description", "parent_id", "properties_json", "tags_json", "sort_order",
    })
    _UPDATABLE_PLOT_LINE_COLS = frozenset({
        "title", "description", "status", "color", "sort_order",
    })
    _UPDATABLE_PLOT_EVENT_COLS = frozenset({
        "title", "description", "scene_id", "chapter_id", "event_type", "sort_order",
    })
    _UPDATABLE_PLOT_HOLE_COLS = frozenset({
        "title", "description", "severity", "status", "scene_id",
        "chapter_id", "plot_line_id", "resolution", "detected_by",
    })

    def __init__(self, db: CharactersRAGDB) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self.db._get_current_utc_timestamp_iso()

    def _uuid(self) -> str:
        return str(uuid.uuid4())

    @property
    def _client_id(self) -> str:
        return self.db.client_id

    @staticmethod
    def _scene_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw scene DB row into API-friendly dict.

        Deserializes ``content_json`` (string) into ``content`` (dict)
        so the response schema can serve it as structured JSON.
        """
        d = dict(row)
        raw = d.pop("content_json", None) or "{}"
        try:
            d["content"] = json.loads(raw)
        except (ValueError, TypeError):
            d["content"] = {}
        return d

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def create_project(
        self,
        title: str,
        *,
        subtitle: str | None = None,
        author: str | None = None,
        genre: str | None = None,
        status: str = "draft",
        synopsis: str | None = None,
        target_word_count: int | None = None,
        settings: dict[str, Any] | None = None,
        project_id: str | None = None,
    ) -> str:
        """Insert a new manuscript project and return its ID."""
        pid = project_id or self._uuid()
        now = self._now()
        settings_json = json.dumps(settings) if settings else "{}"

        if status not in _VALID_PROJECT_STATUSES:
            raise ValueError(f"Invalid project status: {status!r}")  # noqa: TRY003

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_projects
                    (id, title, subtitle, author, genre, status, synopsis,
                     target_word_count, word_count, settings_json,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 0, ?, 1)
                """,
                (
                    pid, title, subtitle, author, genre, status, synopsis,
                    target_word_count, settings_json,
                    now, now, self._client_id,
                ),
            )
        logger.debug("Created manuscript project {}", pid)
        return pid

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Fetch a single project by ID; returns *None* if missing or deleted."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM manuscript_projects WHERE id = ? AND deleted = 0",
                (project_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_projects(
        self,
        *,
        status_filter: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return ``(projects, total_count)`` with optional status filter."""
        where = "WHERE deleted = 0"
        params: list[Any] = []
        if status_filter:
            where += " AND status = ?"
            params.append(status_filter)

        with self.db.transaction() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM manuscript_projects {where}",  # nosec B608
                params,
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            rows = conn.execute(
                f"SELECT * FROM manuscript_projects {where} "  # nosec B608
                "ORDER BY last_modified DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()

        return [dict(r) for r in rows], int(total)

    def update_project(
        self,
        project_id: str,
        updates: dict[str, Any],
        expected_version: int,
    ) -> None:
        """Update a project with optimistic locking."""
        if not updates:
            return

        now = self._now()
        next_version = expected_version + 1

        set_parts: list[str] = []
        params: list[Any] = []
        for key, value in updates.items():
            if key == "settings":
                col = "settings_json"
            else:
                col = key
            if col not in self._UPDATABLE_PROJECT_COLS:
                raise ValueError(f"Invalid update column for project: {key!r}")  # noqa: TRY003
            if key == "settings":
                set_parts.append("settings_json = ?")
                params.append(json.dumps(value))
            else:
                set_parts.append(f"{col} = ?")
                params.append(value)

        set_parts.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        params.extend([now, next_version, self._client_id])
        params.extend([project_id, expected_version])

        with self.db.transaction() as conn:
            cur = conn.execute(
                f"UPDATE manuscript_projects SET {', '.join(set_parts)} "  # nosec B608
                "WHERE id = ? AND version = ? AND deleted = 0",
                params,
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Project {project_id!r} update failed (version conflict or not found).",
                    entity="manuscript_projects",
                    entity_id=project_id,
                )

    def soft_delete_project(self, project_id: str, expected_version: int) -> None:
        """Soft-delete a project with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_projects "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, project_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Project {project_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_projects",
                    entity_id=project_id,
                )

    # ------------------------------------------------------------------
    # Parts
    # ------------------------------------------------------------------

    def create_part(
        self,
        project_id: str,
        title: str,
        *,
        sort_order: float = 0,
        synopsis: str | None = None,
        part_id: str | None = None,
    ) -> str:
        """Insert a new part within a project; returns the part ID."""
        pid = part_id or self._uuid()
        now = self._now()

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_parts
                    (id, project_id, title, sort_order, synopsis, word_count,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, 0, ?, 1)
                """,
                (pid, project_id, title, sort_order, synopsis, now, now, self._client_id),
            )
        logger.debug("Created manuscript part {} in project {}", pid, project_id)
        return pid

    def get_part(self, part_id: str) -> dict[str, Any] | None:
        """Fetch a part by ID; returns *None* if missing or deleted."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM manuscript_parts WHERE id = ? AND deleted = 0",
                (part_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_parts(self, project_id: str) -> list[dict[str, Any]]:
        """List all non-deleted parts for a project ordered by sort_order."""
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM manuscript_parts "
                "WHERE project_id = ? AND deleted = 0 ORDER BY sort_order",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_part(
        self,
        part_id: str,
        updates: dict[str, Any],
        expected_version: int,
    ) -> None:
        """Update a part with optimistic locking."""
        if not updates:
            return

        invalid_keys = set(updates.keys()) - self._UPDATABLE_PART_COLS
        if invalid_keys:
            raise ValueError(f"Invalid update columns for part: {invalid_keys}")  # noqa: TRY003

        now = self._now()
        next_version = expected_version + 1

        set_parts: list[str] = []
        params: list[Any] = []
        for key, value in updates.items():
            set_parts.append(f"{key} = ?")
            params.append(value)

        set_parts.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        params.extend([now, next_version, self._client_id])
        params.extend([part_id, expected_version])

        with self.db.transaction() as conn:
            cur = conn.execute(
                f"UPDATE manuscript_parts SET {', '.join(set_parts)} "  # nosec B608
                "WHERE id = ? AND version = ? AND deleted = 0",
                params,
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Part {part_id!r} update failed (version conflict or not found).",
                    entity="manuscript_parts",
                    entity_id=part_id,
                )

    def soft_delete_part(self, part_id: str, expected_version: int) -> None:
        """Soft-delete a part with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_parts "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, part_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Part {part_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_parts",
                    entity_id=part_id,
                )

    # ------------------------------------------------------------------
    # Chapters
    # ------------------------------------------------------------------

    def create_chapter(
        self,
        project_id: str,
        title: str,
        *,
        part_id: str | None = None,
        sort_order: float = 0,
        synopsis: str | None = None,
        status: str = "draft",
        chapter_id: str | None = None,
    ) -> str:
        """Insert a new chapter; returns its ID."""
        cid = chapter_id or self._uuid()
        now = self._now()

        if status not in _VALID_CHAPTER_STATUSES:
            raise ValueError(f"Invalid chapter status: {status!r}")  # noqa: TRY003

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_chapters
                    (id, project_id, part_id, title, sort_order, synopsis,
                     pov_character_id, word_count, status,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, ?, NULL, 0, ?, ?, ?, 0, ?, 1)
                """,
                (
                    cid, project_id, part_id, title, sort_order, synopsis,
                    status, now, now, self._client_id,
                ),
            )
        logger.debug("Created manuscript chapter {} in project {}", cid, project_id)
        return cid

    def get_chapter(self, chapter_id: str) -> dict[str, Any] | None:
        """Fetch a chapter by ID; returns *None* if missing or deleted."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM manuscript_chapters WHERE id = ? AND deleted = 0",
                (chapter_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_chapters(
        self,
        project_id: str,
        *,
        part_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List non-deleted chapters, optionally filtered by part_id."""
        if part_id is not None:
            sql = (
                "SELECT * FROM manuscript_chapters "
                "WHERE project_id = ? AND part_id = ? AND deleted = 0 "
                "ORDER BY sort_order"
            )
            params: tuple[Any, ...] = (project_id, part_id)
        else:
            sql = (
                "SELECT * FROM manuscript_chapters "
                "WHERE project_id = ? AND deleted = 0 ORDER BY sort_order"
            )
            params = (project_id,)

        with self.db.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def update_chapter(
        self,
        chapter_id: str,
        updates: dict[str, Any],
        expected_version: int,
    ) -> None:
        """Update a chapter with optimistic locking."""
        if not updates:
            return

        invalid_keys = set(updates.keys()) - self._UPDATABLE_CHAPTER_COLS
        if invalid_keys:
            raise ValueError(f"Invalid update columns for chapter: {invalid_keys}")  # noqa: TRY003

        now = self._now()
        next_version = expected_version + 1

        set_parts: list[str] = []
        params: list[Any] = []
        for key, value in updates.items():
            set_parts.append(f"{key} = ?")
            params.append(value)

        set_parts.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        params.extend([now, next_version, self._client_id])
        params.extend([chapter_id, expected_version])

        with self.db.transaction() as conn:
            cur = conn.execute(
                f"UPDATE manuscript_chapters SET {', '.join(set_parts)} "  # nosec B608
                "WHERE id = ? AND version = ? AND deleted = 0",
                params,
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Chapter {chapter_id!r} update failed (version conflict or not found).",
                    entity="manuscript_chapters",
                    entity_id=chapter_id,
                )

    def soft_delete_chapter(self, chapter_id: str, expected_version: int) -> None:
        """Soft-delete a chapter with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_chapters "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, chapter_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Chapter {chapter_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_chapters",
                    entity_id=chapter_id,
                )

    # ------------------------------------------------------------------
    # Scenes
    # ------------------------------------------------------------------

    def create_scene(
        self,
        chapter_id: str,
        project_id: str,
        *,
        title: str = "Untitled Scene",
        content_json: str = "{}",
        content_plain: str = "",
        synopsis: str | None = None,
        sort_order: float = 0,
        status: str = "draft",
        scene_id: str | None = None,
    ) -> str:
        """Insert a new scene; returns its ID.

        After insertion the word counts for the chapter (and part / project)
        are propagated.
        """
        sid = scene_id or self._uuid()
        now = self._now()
        wc = _word_count(content_plain)

        if status not in _VALID_SCENE_STATUSES:
            raise ValueError(f"Invalid scene status: {status!r}")  # noqa: TRY003

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_scenes
                    (id, chapter_id, project_id, title, sort_order,
                     content_json, content_plain, synopsis, word_count,
                     pov_character_id, status,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, 0, ?, 1)
                """,
                (
                    sid, chapter_id, project_id, title, sort_order,
                    content_json, content_plain, synopsis, wc,
                    status, now, now, self._client_id,
                ),
            )
            self._propagate_word_counts(conn, chapter_id, project_id)

        logger.debug("Created manuscript scene {} in chapter {}", sid, chapter_id)
        return sid

    def get_scene(self, scene_id: str) -> dict[str, Any] | None:
        """Fetch a scene by ID; returns *None* if missing or deleted.

        The returned dict has ``content_json`` deserialized into ``content``.
        """
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM manuscript_scenes WHERE id = ? AND deleted = 0",
                (scene_id,),
            ).fetchone()
        return self._scene_row_to_dict(dict(row)) if row else None

    def list_scenes(self, chapter_id: str) -> list[dict[str, Any]]:
        """List non-deleted scenes for a chapter ordered by sort_order."""
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM manuscript_scenes "
                "WHERE chapter_id = ? AND deleted = 0 ORDER BY sort_order",
                (chapter_id,),
            ).fetchall()
        return [self._scene_row_to_dict(dict(r)) for r in rows]

    def update_scene(
        self,
        scene_id: str,
        updates: dict[str, Any],
        expected_version: int,
    ) -> None:
        """Update a scene with optimistic locking.

        If ``content_plain`` is among the updates the ``word_count`` is
        recomputed automatically and word counts are propagated to parent
        entities.
        """
        if not updates:
            return

        now = self._now()
        next_version = expected_version + 1

        # If content_plain changed, recompute word count
        if "content_plain" in updates:
            updates["word_count"] = _word_count(updates["content_plain"])

        invalid_keys = set(updates.keys()) - self._UPDATABLE_SCENE_COLS
        if invalid_keys:
            raise ValueError(f"Invalid update columns for scene: {invalid_keys}")  # noqa: TRY003

        set_parts: list[str] = []
        params: list[Any] = []
        for key, value in updates.items():
            set_parts.append(f"{key} = ?")
            params.append(value)

        set_parts.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        params.extend([now, next_version, self._client_id])
        params.extend([scene_id, expected_version])

        with self.db.transaction() as conn:
            cur = conn.execute(
                f"UPDATE manuscript_scenes SET {', '.join(set_parts)} "  # nosec B608
                "WHERE id = ? AND version = ? AND deleted = 0",
                params,
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Scene {scene_id!r} update failed (version conflict or not found).",
                    entity="manuscript_scenes",
                    entity_id=scene_id,
                )

            # Propagate if word count might have changed
            if "content_plain" in updates:
                row = conn.execute(
                    "SELECT chapter_id, project_id FROM manuscript_scenes WHERE id = ?",
                    (scene_id,),
                ).fetchone()
                if row:
                    self._propagate_word_counts(conn, row["chapter_id"], row["project_id"])
                self._mark_analyses_stale_in_txn(conn, "scene", scene_id)

    def soft_delete_scene(self, scene_id: str, expected_version: int) -> None:
        """Soft-delete a scene with optimistic locking; propagates word counts."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            # Fetch parent info before delete
            row = conn.execute(
                "SELECT chapter_id, project_id FROM manuscript_scenes "
                "WHERE id = ? AND deleted = 0",
                (scene_id,),
            ).fetchone()

            cur = conn.execute(
                "UPDATE manuscript_scenes "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, scene_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Scene {scene_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_scenes",
                    entity_id=scene_id,
                )

            if row:
                self._propagate_word_counts(conn, row["chapter_id"], row["project_id"])

    def get_all_scene_texts(self, project_id: str) -> list[str]:
        """Get all scene plain texts for a project in narrative order (single query)."""
        with self.db.transaction() as conn:
            cur = conn.execute(
                "SELECT s.content_plain "
                "FROM manuscript_scenes s "
                "JOIN manuscript_chapters c ON c.id = s.chapter_id AND c.deleted = 0 "
                "LEFT JOIN manuscript_parts p ON p.id = c.part_id AND p.deleted = 0 "
                "WHERE s.project_id = ? AND s.deleted = 0 "
                "ORDER BY COALESCE(p.sort_order, -1), c.sort_order, s.sort_order",
                (project_id,),
            )
            return [row["content_plain"] for row in cur.fetchall() if row["content_plain"]]

    # ------------------------------------------------------------------
    # Word-count propagation
    # ------------------------------------------------------------------

    def _propagate_word_counts(self, conn: Any, chapter_id: str, project_id: str) -> None:
        """Cascade word counts: scenes -> chapter -> part (if any) -> project.

        Must be called inside an existing transaction (receives the connection).
        """
        now = self._now()

        # 1. Chapter word count = SUM of its non-deleted scenes
        ch_wc_row = conn.execute(
            "SELECT COALESCE(SUM(word_count), 0) AS wc "
            "FROM manuscript_scenes WHERE chapter_id = ? AND deleted = 0",
            (chapter_id,),
        ).fetchone()
        ch_wc = int(ch_wc_row["wc"]) if ch_wc_row else 0

        conn.execute(
            "UPDATE manuscript_chapters SET word_count = ?, last_modified = ? WHERE id = ?",
            (ch_wc, now, chapter_id),
        )

        # 2. Determine if the chapter belongs to a part
        ch_row = conn.execute(
            "SELECT part_id FROM manuscript_chapters WHERE id = ?",
            (chapter_id,),
        ).fetchone()
        part_id = ch_row["part_id"] if ch_row else None

        if part_id:
            # Part word count = SUM of its non-deleted chapters
            part_wc_row = conn.execute(
                "SELECT COALESCE(SUM(word_count), 0) AS wc "
                "FROM manuscript_chapters WHERE part_id = ? AND deleted = 0",
                (part_id,),
            ).fetchone()
            part_wc = int(part_wc_row["wc"]) if part_wc_row else 0

            conn.execute(
                "UPDATE manuscript_parts SET word_count = ?, last_modified = ? WHERE id = ?",
                (part_wc, now, part_id),
            )

        # 3. Project word count = SUM of its non-deleted scenes
        #    (authoritative count from scenes, not double-counting via chapters/parts)
        proj_wc_row = conn.execute(
            "SELECT COALESCE(SUM(word_count), 0) AS wc "
            "FROM manuscript_scenes WHERE project_id = ? AND deleted = 0",
            (project_id,),
        ).fetchone()
        proj_wc = int(proj_wc_row["wc"]) if proj_wc_row else 0

        conn.execute(
            "UPDATE manuscript_projects SET word_count = ?, last_modified = ? WHERE id = ?",
            (proj_wc, now, project_id),
        )

    # ------------------------------------------------------------------
    # Project structure
    # ------------------------------------------------------------------

    def get_project_structure(self, project_id: str) -> dict[str, Any]:
        """Build a hierarchical view of the project.

        Returns::

            {
                "project_id": "...",
                "parts": [
                    {"id": ..., "title": ..., "chapters": [
                        {"id": ..., "title": ..., "scenes": [...]},
                    ]},
                ],
                "unassigned_chapters": [
                    {"id": ..., "title": ..., "scenes": [...]},
                ],
            }
        """
        with self.db.transaction() as conn:
            parts = conn.execute(
                "SELECT * FROM manuscript_parts "
                "WHERE project_id = ? AND deleted = 0 ORDER BY sort_order",
                (project_id,),
            ).fetchall()

            chapters = conn.execute(
                "SELECT * FROM manuscript_chapters "
                "WHERE project_id = ? AND deleted = 0 ORDER BY sort_order",
                (project_id,),
            ).fetchall()

            scenes = conn.execute(
                "SELECT * FROM manuscript_scenes "
                "WHERE project_id = ? AND deleted = 0 ORDER BY sort_order",
                (project_id,),
            ).fetchall()

        # Index scenes by chapter_id
        scenes_by_chapter: dict[str, list[dict[str, Any]]] = {}
        for s in scenes:
            sd = dict(s)
            scenes_by_chapter.setdefault(sd["chapter_id"], []).append(sd)

        # Index chapters by part_id
        chapters_by_part: dict[str | None, list[dict[str, Any]]] = {}
        for c in chapters:
            cd = dict(c)
            cd["scenes"] = scenes_by_chapter.get(cd["id"], [])
            chapters_by_part.setdefault(cd["part_id"], []).append(cd)

        result_parts = []
        for p in parts:
            pd = dict(p)
            pd["chapters"] = chapters_by_part.get(pd["id"], [])
            result_parts.append(pd)

        return {
            "project_id": project_id,
            "parts": result_parts,
            "unassigned_chapters": chapters_by_part.get(None, []),
        }

    # ------------------------------------------------------------------
    # FTS search
    # ------------------------------------------------------------------

    def search_scenes(
        self,
        project_id: str,
        query: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Full-text search across scene titles, plain content, and synopses.

        Returns matching scenes with FTS5 ``snippet()`` highlights.
        """
        with self.db.transaction() as conn:
            rows = conn.execute(
                """
                SELECT s.*,
                       snippet(manuscript_scenes_fts, 1, '<b>', '</b>', '...', 32) AS snippet
                FROM manuscript_scenes_fts AS fts
                JOIN manuscript_scenes AS s ON s.rowid = fts.rowid
                WHERE manuscript_scenes_fts MATCH ?
                  AND s.project_id = ?
                  AND s.deleted = 0
                ORDER BY rank
                LIMIT ?
                """,
                (query, project_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Reorder
    # ------------------------------------------------------------------

    def reorder_items(
        self,
        entity_type: str,
        items: list[dict[str, Any]],
    ) -> None:
        """Batch-update ``sort_order`` (and optionally ``part_id`` for chapters).

        Parameters
        ----------
        entity_type:
            One of ``"part"``, ``"chapter"``, ``"scene"``.
        items:
            A list of dicts, each containing at minimum ``"id"`` and
            ``"sort_order"``.  For chapters, an optional ``"part_id"`` can
            be included to reparent.
        """
        table = _REORDER_ENTITY_TABLES.get(entity_type)
        if table is None:
            raise ValueError(  # noqa: TRY003
                f"Invalid entity_type {entity_type!r}; "
                f"must be one of {sorted(_REORDER_ENTITY_TABLES)}"
            )

        now = self._now()

        with self.db.transaction() as conn:
            for item in items:
                item_id = item["id"]
                sort_order = item["sort_order"]

                if entity_type == "chapter" and "part_id" in item:
                    conn.execute(
                        f"UPDATE {table} SET sort_order = ?, part_id = ?, "  # nosec B608
                        "last_modified = ? WHERE id = ? AND deleted = 0",
                        (sort_order, item["part_id"], now, item_id),
                    )
                else:
                    conn.execute(
                        f"UPDATE {table} SET sort_order = ?, "  # nosec B608
                        "last_modified = ? WHERE id = ? AND deleted = 0",
                        (sort_order, now, item_id),
                    )

    # ==================================================================
    # Characters
    # ==================================================================

    def create_character(
        self,
        project_id: str,
        name: str,
        *,
        role: str = "supporting",
        cast_group: str | None = None,
        full_name: str | None = None,
        age: str | None = None,
        gender: str | None = None,
        appearance: str | None = None,
        personality: str | None = None,
        backstory: str | None = None,
        motivation: str | None = None,
        arc_summary: str | None = None,
        notes: str | None = None,
        custom_fields: dict[str, Any] | None = None,
        sort_order: float = 0,
        character_id: str | None = None,
    ) -> str:
        """Insert a new character and return its ID."""
        cid = character_id or self._uuid()
        now = self._now()
        cf_json = json.dumps(custom_fields) if custom_fields else "{}"

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_characters
                    (id, project_id, name, role, cast_group, full_name, age, gender,
                     appearance, personality, backstory, motivation, arc_summary,
                     notes, custom_fields_json, sort_order,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1)
                """,
                (
                    cid, project_id, name, role, cast_group, full_name, age, gender,
                    appearance, personality, backstory, motivation, arc_summary,
                    notes, cf_json, sort_order,
                    now, now, self._client_id,
                ),
            )
        logger.debug("Created manuscript character {} in project {}", cid, project_id)
        return cid

    def get_character(self, character_id: str) -> dict[str, Any] | None:
        """Fetch a character by ID; returns *None* if missing or deleted."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM manuscript_characters WHERE id = ? AND deleted = 0",
                (character_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["custom_fields"] = json.loads(d.pop("custom_fields_json", "{}"))
        return d

    def list_characters(
        self,
        project_id: str,
        *,
        role_filter: str | None = None,
        cast_group_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """List non-deleted characters for a project, optionally filtered."""
        where = "project_id = ? AND deleted = 0"
        params: list[Any] = [project_id]
        if role_filter:
            where += " AND role = ?"
            params.append(role_filter)
        if cast_group_filter:
            where += " AND cast_group = ?"
            params.append(cast_group_filter)

        with self.db.transaction() as conn:
            cur = conn.execute(
                f"SELECT * FROM manuscript_characters WHERE {where} ORDER BY sort_order",  # nosec B608
                params,
            )
            rows = cur.fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["custom_fields"] = json.loads(d.pop("custom_fields_json", "{}"))
            results.append(d)
        return results

    def update_character(
        self,
        character_id: str,
        updates: dict[str, Any],
        expected_version: int,
    ) -> None:
        """Update a character with optimistic locking."""
        if not updates:
            return

        now = self._now()
        next_version = expected_version + 1

        if "custom_fields" in updates:
            updates["custom_fields_json"] = json.dumps(updates.pop("custom_fields"))

        invalid_keys = set(updates.keys()) - self._UPDATABLE_CHARACTER_COLS
        if invalid_keys:
            raise ValueError(f"Invalid update columns for character: {invalid_keys}")  # noqa: TRY003

        set_parts: list[str] = []
        params: list[Any] = []
        for key, value in updates.items():
            set_parts.append(f"{key} = ?")
            params.append(value)

        set_parts.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        params.extend([now, next_version, self._client_id])
        params.extend([character_id, expected_version])

        with self.db.transaction() as conn:
            cur = conn.execute(
                f"UPDATE manuscript_characters SET {', '.join(set_parts)} "  # nosec B608
                "WHERE id = ? AND version = ? AND deleted = 0",
                params,
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Character {character_id!r} update failed (version conflict or not found).",
                    entity="manuscript_characters",
                    entity_id=character_id,
                )

    def soft_delete_character(self, character_id: str, expected_version: int) -> None:
        """Soft-delete a character with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_characters "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, character_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Character {character_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_characters",
                    entity_id=character_id,
                )

    # ==================================================================
    # Character Relationships
    # ==================================================================

    def create_relationship(
        self,
        project_id: str,
        from_character_id: str,
        to_character_id: str,
        relationship_type: str,
        *,
        description: str | None = None,
        bidirectional: bool = True,
        relationship_id: str | None = None,
    ) -> str:
        """Insert a character relationship and return its ID."""
        rid = relationship_id or self._uuid()
        now = self._now()

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_character_relationships
                    (id, project_id, from_character_id, to_character_id,
                     relationship_type, description, bidirectional,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1)
                """,
                (
                    rid, project_id, from_character_id, to_character_id,
                    relationship_type, description, int(bidirectional),
                    now, now, self._client_id,
                ),
            )
        logger.debug("Created relationship {} in project {}", rid, project_id)
        return rid

    def list_relationships(self, project_id: str) -> list[dict[str, Any]]:
        """List non-deleted relationships for a project."""
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM manuscript_character_relationships "
                "WHERE project_id = ? AND deleted = 0",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def soft_delete_relationship(self, relationship_id: str, expected_version: int) -> None:
        """Soft-delete a relationship with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_character_relationships "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, relationship_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Relationship {relationship_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_character_relationships",
                    entity_id=relationship_id,
                )

    # ==================================================================
    # Scene-Character Linking
    # ==================================================================

    def link_scene_character(
        self,
        scene_id: str,
        character_id: str,
        *,
        is_pov: bool = False,
    ) -> None:
        """Link a character to a scene (INSERT OR IGNORE)."""
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO manuscript_scene_characters "
                "(scene_id, character_id, is_pov) VALUES (?, ?, ?)",
                (scene_id, character_id, int(is_pov)),
            )

    def unlink_scene_character(self, scene_id: str, character_id: str) -> None:
        """Remove a character-scene link."""
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM manuscript_scene_characters "
                "WHERE scene_id = ? AND character_id = ?",
                (scene_id, character_id),
            )

    def list_scene_characters(self, scene_id: str) -> list[dict[str, Any]]:
        """List characters linked to a scene, including name and role."""
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT sc.scene_id, sc.character_id, sc.is_pov, "
                "       c.name, c.role "
                "FROM manuscript_scene_characters sc "
                "JOIN manuscript_characters c ON c.id = sc.character_id AND c.deleted = 0 "
                "WHERE sc.scene_id = ?",
                (scene_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ==================================================================
    # World Info
    # ==================================================================

    def create_world_info(
        self,
        project_id: str,
        kind: str,
        name: str,
        *,
        description: str | None = None,
        parent_id: str | None = None,
        properties: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        sort_order: float = 0,
        world_info_id: str | None = None,
    ) -> str:
        """Insert a world-info entry and return its ID."""
        wid = world_info_id or self._uuid()
        now = self._now()
        props_json = json.dumps(properties) if properties else "{}"
        tags_json = json.dumps(tags) if tags else "[]"

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_world_info
                    (id, project_id, kind, name, description, parent_id,
                     properties_json, tags_json, sort_order,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1)
                """,
                (
                    wid, project_id, kind, name, description, parent_id,
                    props_json, tags_json, sort_order,
                    now, now, self._client_id,
                ),
            )
        logger.debug("Created world info {} in project {}", wid, project_id)
        return wid

    def get_world_info(self, world_info_id: str) -> dict[str, Any] | None:
        """Fetch a world-info entry by ID; returns *None* if missing or deleted."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM manuscript_world_info WHERE id = ? AND deleted = 0",
                (world_info_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["properties"] = json.loads(d.pop("properties_json", "{}"))
        d["tags"] = json.loads(d.pop("tags_json", "[]"))
        return d

    def list_world_info(
        self,
        project_id: str,
        *,
        kind_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """List non-deleted world-info entries for a project."""
        where = "project_id = ? AND deleted = 0"
        params: list[Any] = [project_id]
        if kind_filter:
            where += " AND kind = ?"
            params.append(kind_filter)

        with self.db.transaction() as conn:
            rows = conn.execute(
                f"SELECT * FROM manuscript_world_info WHERE {where} ORDER BY sort_order",  # nosec B608
                params,
            ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["properties"] = json.loads(d.pop("properties_json", "{}"))
            d["tags"] = json.loads(d.pop("tags_json", "[]"))
            results.append(d)
        return results

    def update_world_info(
        self,
        world_info_id: str,
        updates: dict[str, Any],
        expected_version: int,
    ) -> None:
        """Update a world-info entry with optimistic locking."""
        if not updates:
            return

        now = self._now()
        next_version = expected_version + 1

        if "properties" in updates:
            updates["properties_json"] = json.dumps(updates.pop("properties"))
        if "tags" in updates:
            updates["tags_json"] = json.dumps(updates.pop("tags"))

        invalid_keys = set(updates.keys()) - self._UPDATABLE_WORLD_INFO_COLS
        if invalid_keys:
            raise ValueError(f"Invalid update columns for world info: {invalid_keys}")  # noqa: TRY003

        set_parts: list[str] = []
        params: list[Any] = []
        for key, value in updates.items():
            set_parts.append(f"{key} = ?")
            params.append(value)

        set_parts.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        params.extend([now, next_version, self._client_id])
        params.extend([world_info_id, expected_version])

        with self.db.transaction() as conn:
            cur = conn.execute(
                f"UPDATE manuscript_world_info SET {', '.join(set_parts)} "  # nosec B608
                "WHERE id = ? AND version = ? AND deleted = 0",
                params,
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"WorldInfo {world_info_id!r} update failed (version conflict or not found).",
                    entity="manuscript_world_info",
                    entity_id=world_info_id,
                )

    def soft_delete_world_info(self, world_info_id: str, expected_version: int) -> None:
        """Soft-delete a world-info entry with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_world_info "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, world_info_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"WorldInfo {world_info_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_world_info",
                    entity_id=world_info_id,
                )

    # ==================================================================
    # Scene-World Info Linking
    # ==================================================================

    def link_scene_world_info(self, scene_id: str, world_info_id: str) -> None:
        """Link a world-info entry to a scene (INSERT OR IGNORE)."""
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO manuscript_scene_world_info "
                "(scene_id, world_info_id) VALUES (?, ?)",
                (scene_id, world_info_id),
            )

    def unlink_scene_world_info(self, scene_id: str, world_info_id: str) -> None:
        """Remove a world-info-scene link."""
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM manuscript_scene_world_info "
                "WHERE scene_id = ? AND world_info_id = ?",
                (scene_id, world_info_id),
            )

    def list_scene_world_info(self, scene_id: str) -> list[dict[str, Any]]:
        """List world-info entries linked to a scene, including name and kind."""
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT sw.scene_id, sw.world_info_id, "
                "       w.name, w.kind "
                "FROM manuscript_scene_world_info sw "
                "JOIN manuscript_world_info w ON w.id = sw.world_info_id AND w.deleted = 0 "
                "WHERE sw.scene_id = ?",
                (scene_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ==================================================================
    # Plot Lines
    # ==================================================================

    def create_plot_line(
        self,
        project_id: str,
        title: str,
        *,
        description: str | None = None,
        status: str = "active",
        color: str | None = None,
        sort_order: float = 0,
        plot_line_id: str | None = None,
    ) -> str:
        """Insert a new plot line and return its ID."""
        pid = plot_line_id or self._uuid()
        now = self._now()

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_plot_lines
                    (id, project_id, title, description, status, color, sort_order,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1)
                """,
                (
                    pid, project_id, title, description, status, color, sort_order,
                    now, now, self._client_id,
                ),
            )
        logger.debug("Created plot line {} in project {}", pid, project_id)
        return pid

    def get_plot_line(self, plot_line_id: str) -> dict[str, Any] | None:
        """Fetch a plot line by ID; returns *None* if missing or deleted."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM manuscript_plot_lines WHERE id = ? AND deleted = 0",
                (plot_line_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_plot_lines(self, project_id: str) -> list[dict[str, Any]]:
        """List non-deleted plot lines for a project ordered by sort_order."""
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM manuscript_plot_lines "
                "WHERE project_id = ? AND deleted = 0 ORDER BY sort_order",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_plot_line(
        self,
        plot_line_id: str,
        updates: dict[str, Any],
        expected_version: int,
    ) -> None:
        """Update a plot line with optimistic locking."""
        if not updates:
            return

        invalid_keys = set(updates.keys()) - self._UPDATABLE_PLOT_LINE_COLS
        if invalid_keys:
            raise ValueError(f"Invalid update columns for plot line: {invalid_keys}")  # noqa: TRY003

        now = self._now()
        next_version = expected_version + 1

        set_parts: list[str] = []
        params: list[Any] = []
        for key, value in updates.items():
            set_parts.append(f"{key} = ?")
            params.append(value)

        set_parts.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        params.extend([now, next_version, self._client_id])
        params.extend([plot_line_id, expected_version])

        with self.db.transaction() as conn:
            cur = conn.execute(
                f"UPDATE manuscript_plot_lines SET {', '.join(set_parts)} "  # nosec B608
                "WHERE id = ? AND version = ? AND deleted = 0",
                params,
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"PlotLine {plot_line_id!r} update failed (version conflict or not found).",
                    entity="manuscript_plot_lines",
                    entity_id=plot_line_id,
                )

    def soft_delete_plot_line(self, plot_line_id: str, expected_version: int) -> None:
        """Soft-delete a plot line with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_plot_lines "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, plot_line_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"PlotLine {plot_line_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_plot_lines",
                    entity_id=plot_line_id,
                )

    # ==================================================================
    # Plot Events
    # ==================================================================

    def create_plot_event(
        self,
        project_id: str,
        plot_line_id: str,
        title: str,
        *,
        description: str | None = None,
        scene_id: str | None = None,
        chapter_id: str | None = None,
        event_type: str = "plot",
        sort_order: float = 0,
        event_id: str | None = None,
    ) -> str:
        """Insert a new plot event and return its ID."""
        eid = event_id or self._uuid()
        now = self._now()

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_plot_events
                    (id, project_id, plot_line_id, scene_id, chapter_id,
                     title, description, event_type, sort_order,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1)
                """,
                (
                    eid, project_id, plot_line_id, scene_id, chapter_id,
                    title, description, event_type, sort_order,
                    now, now, self._client_id,
                ),
            )
        logger.debug("Created plot event {} for plot line {}", eid, plot_line_id)
        return eid

    def list_plot_events(self, plot_line_id: str) -> list[dict[str, Any]]:
        """List non-deleted plot events for a plot line ordered by sort_order."""
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM manuscript_plot_events "
                "WHERE plot_line_id = ? AND deleted = 0 ORDER BY sort_order",
                (plot_line_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_plot_event(
        self,
        event_id: str,
        updates: dict[str, Any],
        expected_version: int,
    ) -> None:
        """Update a plot event with optimistic locking."""
        if not updates:
            return

        invalid_keys = set(updates.keys()) - self._UPDATABLE_PLOT_EVENT_COLS
        if invalid_keys:
            raise ValueError(f"Invalid update columns for plot event: {invalid_keys}")  # noqa: TRY003

        now = self._now()
        next_version = expected_version + 1

        set_parts: list[str] = []
        params: list[Any] = []
        for key, value in updates.items():
            set_parts.append(f"{key} = ?")
            params.append(value)

        set_parts.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        params.extend([now, next_version, self._client_id])
        params.extend([event_id, expected_version])

        with self.db.transaction() as conn:
            cur = conn.execute(
                f"UPDATE manuscript_plot_events SET {', '.join(set_parts)} "  # nosec B608
                "WHERE id = ? AND version = ? AND deleted = 0",
                params,
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"PlotEvent {event_id!r} update failed (version conflict or not found).",
                    entity="manuscript_plot_events",
                    entity_id=event_id,
                )

    def soft_delete_plot_event(self, event_id: str, expected_version: int) -> None:
        """Soft-delete a plot event with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_plot_events "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, event_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"PlotEvent {event_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_plot_events",
                    entity_id=event_id,
                )

    # ==================================================================
    # Plot Holes
    # ==================================================================

    def create_plot_hole(
        self,
        project_id: str,
        title: str,
        *,
        description: str | None = None,
        severity: str = "medium",
        scene_id: str | None = None,
        chapter_id: str | None = None,
        plot_line_id: str | None = None,
        detected_by: str = "manual",
        plot_hole_id: str | None = None,
    ) -> str:
        """Insert a new plot hole and return its ID."""
        phid = plot_hole_id or self._uuid()
        now = self._now()

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_plot_holes
                    (id, project_id, title, description, severity, status,
                     scene_id, chapter_id, plot_line_id, resolution, detected_by,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, NULL, ?, ?, ?, 0, ?, 1)
                """,
                (
                    phid, project_id, title, description, severity,
                    scene_id, chapter_id, plot_line_id, detected_by,
                    now, now, self._client_id,
                ),
            )
        logger.debug("Created plot hole {} in project {}", phid, project_id)
        return phid

    def get_plot_hole(self, plot_hole_id: str) -> dict[str, Any] | None:
        """Fetch a plot hole by ID; returns *None* if missing or deleted."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM manuscript_plot_holes WHERE id = ? AND deleted = 0",
                (plot_hole_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_plot_holes(
        self,
        project_id: str,
        *,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """List non-deleted plot holes for a project."""
        where = "project_id = ? AND deleted = 0"
        params: list[Any] = [project_id]
        if status_filter:
            where += " AND status = ?"
            params.append(status_filter)

        with self.db.transaction() as conn:
            rows = conn.execute(
                f"SELECT * FROM manuscript_plot_holes WHERE {where}",  # nosec B608
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def update_plot_hole(
        self,
        plot_hole_id: str,
        updates: dict[str, Any],
        expected_version: int,
    ) -> None:
        """Update a plot hole with optimistic locking."""
        if not updates:
            return

        invalid_keys = set(updates.keys()) - self._UPDATABLE_PLOT_HOLE_COLS
        if invalid_keys:
            raise ValueError(f"Invalid update columns for plot hole: {invalid_keys}")  # noqa: TRY003

        now = self._now()
        next_version = expected_version + 1

        set_parts: list[str] = []
        params: list[Any] = []
        for key, value in updates.items():
            set_parts.append(f"{key} = ?")
            params.append(value)

        set_parts.extend(["last_modified = ?", "version = ?", "client_id = ?"])
        params.extend([now, next_version, self._client_id])
        params.extend([plot_hole_id, expected_version])

        with self.db.transaction() as conn:
            cur = conn.execute(
                f"UPDATE manuscript_plot_holes SET {', '.join(set_parts)} "  # nosec B608
                "WHERE id = ? AND version = ? AND deleted = 0",
                params,
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"PlotHole {plot_hole_id!r} update failed (version conflict or not found).",
                    entity="manuscript_plot_holes",
                    entity_id=plot_hole_id,
                )

    def soft_delete_plot_hole(self, plot_hole_id: str, expected_version: int) -> None:
        """Soft-delete a plot hole with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_plot_holes "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, plot_hole_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"PlotHole {plot_hole_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_plot_holes",
                    entity_id=plot_hole_id,
                )

    # ==================================================================
    # Citations
    # ==================================================================

    def create_citation(
        self,
        project_id: str,
        scene_id: str,
        source_type: str,
        *,
        source_id: str | None = None,
        source_title: str | None = None,
        excerpt: str | None = None,
        query_used: str | None = None,
        anchor_offset: int | None = None,
        citation_id: str | None = None,
    ) -> str:
        """Insert a new citation and return its ID."""
        cid = citation_id or self._uuid()
        now = self._now()

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO manuscript_citations
                    (id, project_id, scene_id, source_type, source_id,
                     source_title, excerpt, query_used, anchor_offset,
                     created_at, last_modified, deleted, client_id, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1)
                """,
                (
                    cid, project_id, scene_id, source_type, source_id,
                    source_title, excerpt, query_used, anchor_offset,
                    now, now, self._client_id,
                ),
            )
        logger.debug("Created citation {} for scene {}", cid, scene_id)
        return cid

    def list_citations(self, scene_id: str) -> list[dict[str, Any]]:
        """List non-deleted citations for a scene."""
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM manuscript_citations "
                "WHERE scene_id = ? AND deleted = 0",
                (scene_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def soft_delete_citation(self, citation_id: str, expected_version: int) -> None:
        """Soft-delete a citation with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_citations "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, citation_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Citation {citation_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_citations",
                    entity_id=citation_id,
                )

    # ------------------------------------------------------------------
    # AI Analyses
    # ------------------------------------------------------------------

    def create_analysis(
        self,
        project_id: str,
        scope_type: str,
        scope_id: str,
        analysis_type: str,
        result: dict,
        *,
        score: float | None = None,
        provider: str | None = None,
        model: str | None = None,
        analysis_id: str | None = None,
    ) -> str:
        """Insert a new AI analysis row and return its ID."""
        aid = analysis_id or self._uuid()
        now = self._now()

        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO manuscript_ai_analyses
                   (id, project_id, scope_type, scope_id, analysis_type, provider, model,
                    result_json, score, created_at, last_modified, client_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (aid, project_id, scope_type, scope_id, analysis_type, provider, model,
                 json.dumps(result), score, now, now, self._client_id),
            )
        logger.debug("Created analysis {} ({}) for {} {}", aid, analysis_type, scope_type, scope_id)
        return aid

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        """Return a single analysis by ID, or None if deleted/missing.

        The ``result_json`` column is deserialized into a ``result`` key.
        """
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM manuscript_ai_analyses WHERE id = ? AND deleted = 0",
                (analysis_id,),
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["result"] = json.loads(d.pop("result_json", "{}"))
        return d

    def list_analyses(
        self,
        project_id: str,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        analysis_type: str | None = None,
        include_stale: bool = False,
    ) -> list[dict[str, Any]]:
        """List non-deleted analyses for a project with optional filters.

        By default stale analyses are excluded unless *include_stale* is True.
        """
        clauses = ["project_id = ?", "deleted = 0"]
        params: list[Any] = [project_id]

        if not include_stale:
            clauses.append("stale = 0")
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if analysis_type is not None:
            clauses.append("analysis_type = ?")
            params.append(analysis_type)

        sql = (
            "SELECT * FROM manuscript_ai_analyses WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at DESC"
        )

        with self.db.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            d["result"] = json.loads(d.pop("result_json", "{}"))
            results.append(d)
        return results

    def mark_analyses_stale(self, scope_type: str, scope_id: str) -> int:
        """Mark all non-deleted analyses for a scope as stale.

        Returns the count of rows updated.
        """
        now = self._now()
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_ai_analyses SET stale = 1, last_modified = ? "
                "WHERE scope_type = ? AND scope_id = ? AND stale = 0 AND deleted = 0",
                (now, scope_type, scope_id),
            )
            return cur.rowcount

    def _mark_analyses_stale_in_txn(self, conn: Any, scope_type: str, scope_id: str) -> int:
        """Mark analyses stale within an existing transaction (no new txn opened)."""
        now = self._now()
        cur = conn.execute(
            "UPDATE manuscript_ai_analyses SET stale = 1, last_modified = ? "
            "WHERE scope_type = ? AND scope_id = ? AND stale = 0 AND deleted = 0",
            (now, scope_type, scope_id),
        )
        return cur.rowcount

    def soft_delete_analysis(self, analysis_id: str, expected_version: int) -> None:
        """Soft-delete an analysis with optimistic locking."""
        now = self._now()
        next_version = expected_version + 1

        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE manuscript_ai_analyses "
                "SET deleted = 1, last_modified = ?, version = ?, client_id = ? "
                "WHERE id = ? AND version = ? AND deleted = 0",
                (now, next_version, self._client_id, analysis_id, expected_version),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    f"Analysis {analysis_id!r} delete failed (version conflict or not found).",
                    entity="manuscript_ai_analyses",
                    entity_id=analysis_id,
                )
