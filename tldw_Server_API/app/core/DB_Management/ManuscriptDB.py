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
        if not row:
            return None
        d = dict(row)
        d["settings"] = json.loads(d.pop("settings_json", "{}"))
        return d

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

        results = []
        for r in rows:
            d = dict(r)
            d["settings"] = json.loads(d.pop("settings_json", "{}"))
            results.append(d)
        return results, int(total)

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
                set_parts.append("settings_json = ?")
                params.append(json.dumps(value))
            else:
                set_parts.append(f"{key} = ?")
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
        """Fetch a scene by ID; returns *None* if missing or deleted."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM manuscript_scenes WHERE id = ? AND deleted = 0",
                (scene_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_scenes(self, chapter_id: str) -> list[dict[str, Any]]:
        """List non-deleted scenes for a chapter ordered by sort_order."""
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM manuscript_scenes "
                "WHERE chapter_id = ? AND deleted = 0 ORDER BY sort_order",
                (chapter_id,),
            ).fetchall()
        return [dict(r) for r in rows]

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
