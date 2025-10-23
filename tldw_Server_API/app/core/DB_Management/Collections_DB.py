"""
Collections_DB - Persistence for Content Collections feature slices.

Scope:
- Output Templates (CRUD + lookup for preview)
- Reading Highlights (CRUD + maintenance helpers)

Notes:
- Uses DatabaseBackendFactory to support SQLite (default) and future PG.
- Stores data in the per-user Media database by default to colocate content artifacts.
- All methods are idempotent and should avoid raising on existing schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from loguru import logger

from .backends.base import DatabaseBackend, DatabaseConfig, BackendType, DatabaseError
from .backends.factory import DatabaseBackendFactory
from .db_path_utils import DatabasePaths


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


@dataclass
class OutputTemplateRow:
    id: int
    user_id: str
    name: str
    type: str
    format: str
    body: str
    description: Optional[str]
    is_default: bool
    created_at: str
    updated_at: str
    metadata_json: Optional[str] = None


@dataclass
class HighlightRow:
    id: int
    user_id: str
    item_id: int
    quote: str
    start_offset: Optional[int]
    end_offset: Optional[int]
    color: Optional[str]
    note: Optional[str]
    created_at: str
    anchor_strategy: str
    content_hash_ref: Optional[str]
    context_before: Optional[str]
    context_after: Optional[str]
    state: str


@dataclass
class CollectionTagRow:
    id: int
    user_id: str
    name: str


@dataclass
class ContentItemRow:
    id: int
    user_id: str
    origin: str
    origin_type: Optional[str]
    origin_id: Optional[int]
    url: Optional[str]
    canonical_url: Optional[str]
    domain: Optional[str]
    title: Optional[str]
    summary: Optional[str]
    content_hash: Optional[str]
    word_count: Optional[int]
    published_at: Optional[str]
    status: Optional[str]
    favorite: bool
    metadata_json: Optional[str]
    media_id: Optional[int]
    job_id: Optional[int]
    run_id: Optional[int]
    source_id: Optional[int]
    read_at: Optional[str]
    created_at: str
    updated_at: str
    tags: List[str]
    is_new: bool = False
    content_changed: bool = False


class CollectionsDatabase:
    """Adapter for Collections tables stored in the per-user Media DB."""

    def __init__(self, user_id: int | str, backend: Optional[DatabaseBackend] = None):
        self.user_id = str(user_id)
        if backend is None:
            db_path = str(DatabasePaths.get_media_db_path(int(user_id)))
            cfg = DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=db_path)
            backend = DatabaseBackendFactory.create_backend(cfg)
        self.backend = backend
        self._fts_available = True
        self.ensure_schema()

    @classmethod
    def for_user(cls, user_id: int | str) -> "CollectionsDatabase":
        return cls(user_id=user_id)

    @classmethod
    def from_backend(cls, user_id: int | str, backend: DatabaseBackend) -> "CollectionsDatabase":
        """Construct using an existing backend (avoids path resolution and int casting)."""
        return cls(user_id=user_id, backend=backend)

    def ensure_schema(self) -> None:
        """Create tables if they do not already exist."""
        # SQLite-compatible DDL; also acceptable on Postgres for basic types
        ddl = """
        CREATE TABLE IF NOT EXISTS output_templates (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            format TEXT NOT NULL,
            body TEXT NOT NULL,
            description TEXT,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_output_templates_user ON output_templates(user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_output_templates_user_name ON output_templates(user_id, name);

        CREATE TABLE IF NOT EXISTS reading_highlights (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            quote TEXT NOT NULL,
            start_offset INTEGER,
            end_offset INTEGER,
            color TEXT,
            note TEXT,
            created_at TEXT NOT NULL,
            anchor_strategy TEXT NOT NULL DEFAULT 'fuzzy_quote',
            content_hash_ref TEXT,
            context_before TEXT,
            context_after TEXT,
            state TEXT NOT NULL DEFAULT 'active'
        );
        CREATE INDEX IF NOT EXISTS idx_highlights_user_item ON reading_highlights(user_id, item_id);

        CREATE TABLE IF NOT EXISTS outputs (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            job_id INTEGER,
            run_id INTEGER,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            format TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            media_item_id INTEGER,
            chatbook_path TEXT,
            deleted INTEGER NOT NULL DEFAULT 0,
            deleted_at TEXT,
            retention_until TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_outputs_user ON outputs(user_id);
        CREATE INDEX IF NOT EXISTS idx_outputs_run ON outputs(run_id);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_outputs_user_title_format ON outputs(user_id, title, format) WHERE deleted = 0;
        """
        try:
            self.backend.create_tables(ddl)
        except Exception as e:
            logger.error(f"Collections schema init failed: {e}")
            raise
        # Backfill columns for existing tables
        try:
            # Attempt to add metadata_json if missing
            self.backend.execute("ALTER TABLE output_templates ADD COLUMN metadata_json TEXT", tuple())
        except Exception:
            pass
        # Outputs table backfills
        try:
            self.backend.execute("ALTER TABLE outputs ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0", tuple())
        except Exception:
            pass
        try:
            self.backend.execute("ALTER TABLE outputs ADD COLUMN deleted_at TEXT", tuple())
        except Exception:
            pass
        try:
            self.backend.execute("ALTER TABLE outputs ADD COLUMN retention_until TEXT", tuple())
        except Exception:
            pass
        try:
            self.backend.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_outputs_user_title_format ON outputs(user_id, title, format) WHERE deleted = 0", tuple())
        except Exception:
            pass
        # Collections layer tables
        fts_available = True
        try:
            self.backend.create_tables(
                """
                CREATE TABLE IF NOT EXISTS collection_tags (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    UNIQUE (user_id, name)
                );

                CREATE TABLE IF NOT EXISTS content_items (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    origin_type TEXT,
                    origin_id INTEGER,
                    url TEXT,
                    canonical_url TEXT,
                    domain TEXT,
                    title TEXT,
                    summary TEXT,
                    content_hash TEXT,
                    word_count INTEGER,
                    published_at TEXT,
                    status TEXT,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT,
                    media_id INTEGER,
                    job_id INTEGER,
                    run_id INTEGER,
                    source_id INTEGER,
                    read_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_canonical ON content_items(user_id, canonical_url) WHERE canonical_url IS NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS ux_content_items_user_hash ON content_items(user_id, content_hash) WHERE content_hash IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_content_items_user_updated ON content_items(user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_content_items_user_domain ON content_items(user_id, domain);
                CREATE INDEX IF NOT EXISTS idx_content_items_job ON content_items(job_id);
                CREATE INDEX IF NOT EXISTS idx_content_items_run ON content_items(run_id);

                CREATE TABLE IF NOT EXISTS content_item_tags (
                    item_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    UNIQUE (item_id, tag_id)
                );
                """
            )
        except Exception as e:
            logger.error(f"Collections content_items schema init failed: {e}")
            raise
        try:
            self.backend.create_tables(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS content_items_fts USING fts5(
                    title,
                    summary,
                    metadata,
                    content=''
                );
                """
            )
        except Exception as e:
            logger.debug(f"Collections FTS unavailable: {e}")
            fts_available = False
        # Backfill columns for prior installs if table existed
        _backfill_columns: Dict[str, str] = {
            "origin_type": "TEXT",
            "origin_id": "INTEGER",
            "job_id": "INTEGER",
            "run_id": "INTEGER",
            "source_id": "INTEGER",
            "read_at": "TEXT",
        }
        for column, col_type in _backfill_columns.items():
            try:
                self.backend.execute(f"ALTER TABLE content_items ADD COLUMN {column} {col_type}", tuple())
            except Exception:
                pass
        self._fts_available = fts_available

    # ------------------------
    # Collections Tags helpers
    # ------------------------
    @staticmethod
    def _normalize_collection_tag(name: str) -> str:
        return name.strip().lower()

    @staticmethod
    def _domain_from_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        try:
            parsed = urlparse(url)
            return parsed.hostname
        except Exception:
            return None

    @staticmethod
    def _fts_query_string(query: str) -> str:
        tokens = [tok.strip() for tok in query.replace('"', " ").split() if tok.strip()]
        if not tokens:
            return ""
        return " AND ".join(f"{token}*" for token in tokens)

    def ensure_collection_tag_ids(self, names: Iterable[str]) -> List[int]:
        normed: List[str] = []
        seen: set[str] = set()
        for raw in names or []:
            if not raw:
                continue
            nm = self._normalize_collection_tag(str(raw))
            if not nm or nm in seen:
                continue
            seen.add(nm)
            normed.append(nm)
        if not normed:
            return []

        ids: List[int] = []
        select_sql = "SELECT id FROM collection_tags WHERE user_id = ? AND name = ?"
        insert_sql = "INSERT INTO collection_tags (user_id, name) VALUES (?, ?)"
        for nm in normed:
            select_params = (self.user_id, nm)
            row = self.backend.execute(select_sql, select_params).first
            if row:
                ids.append(int(row.get("id")))
                continue
            insert_exc: Optional[Exception] = None
            tag_id: Optional[int] = None
            try:
                res = self.backend.execute(insert_sql, (self.user_id, nm))
                if res.lastrowid:
                    tag_id = int(res.lastrowid)
            except Exception as exc:
                insert_exc = exc
            if tag_id is None:
                row = self.backend.execute(select_sql, select_params).first
                if row:
                    tag_id = int(row.get("id"))
            if tag_id is None:
                if insert_exc:
                    raise insert_exc
                raise DatabaseError("Failed to ensure collection tag id")
            ids.append(tag_id)
        return ids

    def _replace_item_tags(self, item_id: int, tag_ids: Iterable[int]) -> None:
        self.backend.execute("DELETE FROM content_item_tags WHERE item_id = ?", (item_id,))
        for tag_id in tag_ids or []:
            try:
                self.backend.execute(
                    "INSERT INTO content_item_tags (item_id, tag_id) VALUES (?, ?)",
                    (item_id, tag_id),
                )
            except DatabaseError:
                # Ignore unique violations (already linked)
                continue

    def _fetch_tags_for_item_ids(self, item_ids: Iterable[int]) -> Dict[int, List[str]]:
        ids = [int(i) for i in set(item_ids or []) if i is not None]
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        rows = self.backend.execute(
            f"""
            SELECT cit.item_id AS item_id, ct.name AS name
            FROM content_item_tags cit
            JOIN collection_tags ct ON ct.id = cit.tag_id
            WHERE cit.item_id IN ({placeholders})
            """,
            tuple(ids),
        ).rows
        mapping: Dict[int, List[str]] = {item_id: [] for item_id in ids}
        for row in rows:
            item_id = int(row.get("item_id"))
            name = str(row.get("name"))
            mapping.setdefault(item_id, []).append(name)
        for tag_list in mapping.values():
            tag_list.sort()
        return mapping

    def _update_content_fts_entry(
        self,
        item_id: int,
        *,
        title: Optional[str],
        summary: Optional[str],
        tags: Optional[List[str]],
        metadata_json: Optional[str],
    ) -> None:
        if not self._fts_available:
            return
        try:
            metadata_text = metadata_json or ""
            self.backend.execute(
                "DELETE FROM content_items_fts WHERE rowid = ?",
                (item_id,),
            )
            self.backend.execute(
                "INSERT INTO content_items_fts(rowid, title, summary, metadata) VALUES (?, ?, ?, ?)",
                (item_id, title or "", summary or "", metadata_text),
            )
        except Exception as exc:
            logger.debug(f"Collections FTS update failed for item {item_id}: {exc}")

    def _delete_content_fts_entry(self, item_id: int) -> None:
        if not self._fts_available:
            return
        try:
            self.backend.execute(
                "DELETE FROM content_items_fts WHERE rowid = ?",
                (item_id,),
            )
        except Exception as exc:
            logger.debug(f"Collections FTS delete failed for item {item_id}: {exc}")

    def _row_to_content_item(
        self,
        row: Dict[str, Any],
        tags: Optional[List[str]] = None,
        *,
        is_new: bool = False,
        content_changed: bool = False,
    ) -> ContentItemRow:
        return ContentItemRow(
            id=int(row.get("id")),
            user_id=str(row.get("user_id")),
            origin=str(row.get("origin")),
            origin_type=row.get("origin_type"),
            origin_id=(int(row.get("origin_id")) if row.get("origin_id") is not None else None),
            url=row.get("url"),
            canonical_url=row.get("canonical_url"),
            domain=row.get("domain"),
            title=row.get("title"),
            summary=row.get("summary"),
            content_hash=row.get("content_hash"),
            word_count=(int(row.get("word_count")) if row.get("word_count") is not None else None),
            published_at=row.get("published_at"),
            status=row.get("status"),
            favorite=bool(row.get("favorite", 0)),
            metadata_json=row.get("metadata_json"),
            media_id=(int(row.get("media_id")) if row.get("media_id") is not None else None),
            job_id=(int(row.get("job_id")) if row.get("job_id") is not None else None),
            run_id=(int(row.get("run_id")) if row.get("run_id") is not None else None),
            source_id=(int(row.get("source_id")) if row.get("source_id") is not None else None),
            read_at=row.get("read_at"),
            created_at=str(row.get("created_at")),
            updated_at=str(row.get("updated_at")),
            tags=tags or [],
            is_new=is_new,
            content_changed=content_changed,
        )

    def get_content_item(self, item_id: int) -> ContentItemRow:
        row = self.backend.execute(
            """
            SELECT id, user_id, origin, origin_type, origin_id, url, canonical_url, domain,
                   title, summary, content_hash, word_count, published_at, status, favorite,
                   metadata_json, media_id, job_id, run_id, source_id, read_at, created_at, updated_at
            FROM content_items
            WHERE id = ? AND user_id = ?
            """,
            (item_id, self.user_id),
        ).first
        if not row:
            raise KeyError("content_item_not_found")
        tags_map = self._fetch_tags_for_item_ids([item_id])
        return self._row_to_content_item(row, tags_map.get(item_id, []))

    def upsert_content_item(
        self,
        *,
        origin: str,
        origin_type: Optional[str] = None,
        origin_id: Optional[int] = None,
        url: Optional[str],
        canonical_url: Optional[str],
        domain: Optional[str],
        title: Optional[str],
        summary: Optional[str],
        content_hash: Optional[str],
        word_count: Optional[int],
        published_at: Optional[str],
        status: Optional[str] = None,
        favorite: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        media_id: Optional[int] = None,
        job_id: Optional[int] = None,
        run_id: Optional[int] = None,
        source_id: Optional[int] = None,
        read_at: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> ContentItemRow:
        """Insert or update a content item record and attach tags."""
        now = _utcnow_iso()
        metadata_json = None
        if metadata:
            try:
                metadata_json = json.dumps(metadata, ensure_ascii=False)
            except Exception as exc:
                logger.debug(f"Failed to encode collections metadata: {exc}")
        domain_val = domain or self._domain_from_url(canonical_url or url)
        favorite_int = 1 if favorite else 0
        status_val = status or "new"
        canonical = canonical_url or url

        selectors: List[Tuple[str, Any]] = []
        if canonical:
            selectors.append(("canonical_url", canonical))
        if content_hash:
            selectors.append(("content_hash", content_hash))
        if url:
            selectors.append(("url", url))

        existing_row: Optional[Dict[str, Any]] = None
        item_id: Optional[int] = None
        for column, value in selectors:
            existing_row = self.backend.execute(
                f"""
                SELECT id, user_id, origin, origin_type, origin_id, url, canonical_url, domain,
                       title, summary, content_hash, word_count, published_at, status, favorite,
                       metadata_json, media_id, job_id, run_id, source_id, read_at, created_at, updated_at
                FROM content_items
                WHERE user_id = ? AND {column} = ?
                """,
                (self.user_id, value),
            ).first
            if existing_row:
                item_id = int(existing_row.get("id"))
                break

        prev_hash = existing_row.get("content_hash") if existing_row else None
        created = item_id is None
        content_changed = created

        if item_id is not None:
            fields: List[str] = [
                "origin = ?",
                "origin_type = ?",
                "origin_id = ?",
                "url = ?",
                "canonical_url = ?",
                "domain = ?",
                "title = ?",
                "summary = ?",
                "content_hash = ?",
                "word_count = ?",
                "published_at = ?",
                "status = ?",
                "favorite = ?",
                "metadata_json = ?",
                "media_id = ?",
                "job_id = ?",
                "run_id = ?",
                "source_id = ?",
                "read_at = ?",
                "updated_at = ?",
            ]
            params = (
                origin,
                origin_type,
                origin_id,
                url,
                canonical,
                domain_val,
                title,
                summary,
                content_hash,
                word_count,
                published_at,
                status_val,
                favorite_int,
                metadata_json,
                media_id,
                job_id,
                run_id,
                source_id,
                read_at,
                now,
                item_id,
                self.user_id,
            )
            self.backend.execute(
                f"UPDATE content_items SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                params,
            )
            if prev_hash == content_hash or (prev_hash is None and content_hash is None):
                content_changed = False
            else:
                content_changed = True
        else:
            res = self.backend.execute(
                """
                INSERT INTO content_items (
                    user_id, origin, origin_type, origin_id, url, canonical_url, domain, title, summary,
                    content_hash, word_count, published_at, status, favorite, metadata_json, media_id,
                    job_id, run_id, source_id, read_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.user_id,
                    origin,
                    origin_type,
                    origin_id,
                    url,
                    canonical,
                    domain_val,
                    title,
                    summary,
                    content_hash,
                    word_count,
                    published_at,
                    status_val,
                    favorite_int,
                    metadata_json,
                    media_id,
                    job_id,
                    run_id,
                    source_id,
                    read_at,
                    now,
                    now,
                ),
            )
            item_id = int(res.lastrowid or 0)

        if tags is not None:
            tag_ids = self.ensure_collection_tag_ids(tags)
            self._replace_item_tags(item_id, tag_ids)

        try:
            self._update_content_fts_entry(
                item_id,
                title=title,
                summary=summary,
                tags=list(tags or []),
                metadata_json=metadata_json,
            )
        except Exception:
            pass

        row = self.get_content_item(item_id)
        row.is_new = created
        row.content_changed = content_changed
        return row

    def list_content_items(
        self,
        *,
        ids: Optional[Iterable[int]] = None,
        q: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        domain: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[Iterable[str]] = None,
        favorite: Optional[bool] = None,
        job_id: Optional[int] = None,
        run_id: Optional[int] = None,
        origin: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[ContentItemRow], int]:
        where: List[str] = ["ci.user_id = ?"]
        params: List[Any] = [self.user_id]
        joins: List[str] = []
        having = ""

        if ids:
            id_list = [int(i) for i in ids]
            if id_list:
                placeholders = ",".join("?" for _ in id_list)
                where.append(f"ci.id IN ({placeholders})")
                params.extend(id_list)

        if q and self._fts_available:
            fts_query = self._fts_query_string(q)
            if fts_query:
                joins.append("INNER JOIN content_items_fts ON content_items_fts.rowid = ci.id")
                where.append("content_items_fts MATCH ?")
                params.append(fts_query)
            else:
                q_like = f"%{q.lower()}%"
                where.append("(LOWER(COALESCE(ci.title, '')) LIKE ? OR LOWER(COALESCE(ci.summary, '')) LIKE ?)")
                params.extend([q_like, q_like])
        elif q:
            q_like = f"%{q.lower()}%"
            where.append("(LOWER(COALESCE(ci.title, '')) LIKE ? OR LOWER(COALESCE(ci.summary, '')) LIKE ?)")
            params.extend([q_like, q_like])

        if domain:
            where.append("ci.domain = ?")
            params.append(domain)

        if date_from:
            where.append("ci.created_at >= ?")
            params.append(date_from)

        if date_to:
            where.append("ci.created_at <= ?")
            params.append(date_to)

        if job_id is not None:
            where.append("ci.job_id = ?")
            params.append(int(job_id))

        if run_id is not None:
            where.append("ci.run_id = ?")
            params.append(int(run_id))

        if origin:
            where.append("ci.origin = ?")
            params.append(origin)

        status_filters: List[str] = []
        if status:
            if isinstance(status, str):
                status_filters = [status.lower()]
            else:
                status_filters = [str(s).lower() for s in status if s]
        if status_filters:
            placeholders = ",".join("?" for _ in status_filters)
            where.append(f"LOWER(ci.status) IN ({placeholders})")
            params.extend(status_filters)

        if favorite is not None:
            where.append("ci.favorite = ?")
            params.append(1 if favorite else 0)

        tag_filters: List[str] = []
        if tags:
            for t in tags:
                if t:
                    tag_filters.append(self._normalize_collection_tag(str(t)))
        if tag_filters:
            tag_filters = list(dict.fromkeys(tag_filters))
            joins.append("INNER JOIN content_item_tags cit ON cit.item_id = ci.id")
            joins.append("INNER JOIN collection_tags ct ON ct.id = cit.tag_id")
            placeholders = ",".join("?" for _ in tag_filters)
            where.append(f"ct.name IN ({placeholders})")
            params.extend(tag_filters)
            having = f"HAVING COUNT(DISTINCT ct.name) >= {len(tag_filters)}"

        where_clause = " AND ".join(where) if where else "1=1"
        group_by = "GROUP BY ci.id"
        joins_sql = f" {' '.join(joins)}" if joins else ""
        base_from = f"FROM content_items ci{joins_sql}"
        subquery = f"SELECT ci.id {base_from} WHERE {where_clause} {group_by} {having}"
        count_sql = f"SELECT COUNT(*) AS cnt FROM ({subquery})"
        total = int(self.backend.execute(count_sql, tuple(params)).scalar or 0)

        limit = size
        offset = max(0, (page - 1) * size)
        rows_sql = f"""
            SELECT
                ci.id, ci.user_id, ci.origin, ci.origin_type, ci.origin_id, ci.url, ci.canonical_url,
                ci.domain, ci.title, ci.summary, ci.content_hash, ci.word_count, ci.published_at,
                ci.status, ci.favorite, ci.metadata_json, ci.media_id, ci.job_id, ci.run_id,
                ci.source_id, ci.read_at, ci.created_at, ci.updated_at
            {base_from}
            WHERE {where_clause}
            {group_by}
            {having}
            ORDER BY ci.updated_at DESC, ci.id DESC
            LIMIT ? OFFSET ?
        """
        row_params = tuple(params + [limit, offset])
        rows = self.backend.execute(rows_sql, row_params).rows
        item_ids = [int(r.get("id")) for r in rows]
        tags_map = self._fetch_tags_for_item_ids(item_ids)
        content_rows = [self._row_to_content_item(r, tags_map.get(int(r.get("id")), [])) for r in rows]
        return content_rows, total

    def update_content_item(
        self,
        item_id: int,
        *,
        status: Optional[str] = None,
        favorite: Optional[bool] = None,
        tags: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        read_at: Optional[str] = None,
    ) -> ContentItemRow:
        """Update persisted content item fields and tags."""
        existing = self.get_content_item(item_id)
        updates: List[str] = []
        params: List[Any] = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if favorite is not None:
            updates.append("favorite = ?")
            params.append(1 if favorite else 0)
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if summary is not None:
            updates.append("summary = ?")
            params.append(summary)
        if read_at is not None:
            updates.append("read_at = ?")
            params.append(read_at)

        metadata_json = None
        if metadata is not None:
            current_meta: Dict[str, Any] = {}
            if existing.metadata_json:
                try:
                    current_meta = json.loads(existing.metadata_json)
                except Exception:
                    current_meta = {}
            current_meta.update(metadata)
            metadata_json = json.dumps(current_meta, ensure_ascii=False)
            updates.append("metadata_json = ?")
            params.append(metadata_json)

        if updates:
            updates.append("updated_at = ?")
            params.append(_utcnow_iso())
            params.extend([item_id, self.user_id])
            self.backend.execute(
                f"UPDATE content_items SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                tuple(params),
            )

        if tags is not None:
            tag_ids = self.ensure_collection_tag_ids(tags)
            self._replace_item_tags(item_id, tag_ids)

        try:
            tgt = self.get_content_item(item_id)
            self._update_content_fts_entry(
                item_id,
                title=tgt.title,
                summary=tgt.summary,
                tags=tgt.tags,
                metadata_json=tgt.metadata_json,
            )
        except Exception:
            pass

        row = self.get_content_item(item_id)
        row.is_new = False
        row.content_changed = False
        return row

    # ------------------------
    # Output Templates API
    # ------------------------
    def list_output_templates(self, q: Optional[str], limit: int, offset: int) -> Tuple[List[OutputTemplateRow], int]:
        where = ["user_id = ?"]
        params: List[Any] = [self.user_id]
        if q:
            where.append("(name LIKE ? OR description LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])
        where_sql = " AND ".join(where)

        count_q = f"SELECT COUNT(*) AS cnt FROM output_templates WHERE {where_sql}"
        total = int(self.backend.execute(count_q, tuple(params)).scalar or 0)

        select_q = (
            f"SELECT id, user_id, name, type, format, body, description, is_default, created_at, updated_at, metadata_json "
            f"FROM output_templates WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        rows = self.backend.execute(select_q, tuple(params + [limit, offset])).rows
        mapped = [OutputTemplateRow(**{**r, "is_default": bool(r.get("is_default", 0))}) for r in rows]
        return mapped, total

    def create_output_template(self, name: str, type_: str, format_: str, body: str, description: Optional[str], is_default: bool, metadata_json: Optional[str] = None) -> OutputTemplateRow:
        now = _utcnow_iso()
        q = (
            "INSERT INTO output_templates (user_id, name, type, format, body, description, is_default, created_at, updated_at, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (self.user_id, name, type_, format_, body, description, 1 if is_default else 0, now, now, metadata_json)
        res = self.backend.execute(q, params)
        new_id = int(res.lastrowid or 0)
        return self.get_output_template(new_id)

    def get_output_template(self, template_id: int) -> OutputTemplateRow:
        q = (
            "SELECT id, user_id, name, type, format, body, description, is_default, created_at, updated_at, metadata_json "
            "FROM output_templates WHERE id = ? AND user_id = ?"
        )
        row = self.backend.execute(q, (template_id, self.user_id)).first
        if not row:
            raise KeyError("template_not_found")
        row["is_default"] = bool(row.get("is_default", 0))
        return OutputTemplateRow(**row)

    def update_output_template(self, template_id: int, patch: Dict[str, Any]) -> OutputTemplateRow:
        if not patch:
            return self.get_output_template(template_id)
        fields = []
        params: List[Any] = []
        for key in ("name", "type", "format", "body", "description", "is_default", "metadata_json"):
            if key in patch and patch[key] is not None:
                fields.append(f"{key} = ?")
                val = patch[key]
                if key == "is_default":
                    val = 1 if bool(val) else 0
                params.append(val)
        fields.append("updated_at = ?")
        params.append(_utcnow_iso())
        params.extend([template_id, self.user_id])
        q = f"UPDATE output_templates SET {', '.join(fields)} WHERE id = ? AND user_id = ?"
        res = self.backend.execute(q, tuple(params))
        if res.rowcount <= 0:
            raise KeyError("template_not_found")
        return self.get_output_template(template_id)

    def delete_output_template(self, template_id: int) -> bool:
        q = "DELETE FROM output_templates WHERE id = ? AND user_id = ?"
        res = self.backend.execute(q, (template_id, self.user_id))
        return res.rowcount > 0

    # ------------------------
    # Highlights API
    # ------------------------
    def create_highlight(
        self,
        item_id: int,
        quote: str,
        start_offset: Optional[int],
        end_offset: Optional[int],
        color: Optional[str],
        note: Optional[str],
        anchor_strategy: str = "fuzzy_quote",
        content_hash_ref: Optional[str] = None,
        context_before: Optional[str] = None,
        context_after: Optional[str] = None,
        state: str = "active",
    ) -> HighlightRow:
        now = _utcnow_iso()
        q = (
            "INSERT INTO reading_highlights (user_id, item_id, quote, start_offset, end_offset, color, note, created_at, "
            "anchor_strategy, content_hash_ref, context_before, context_after, state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            self.user_id,
            item_id,
            quote,
            start_offset,
            end_offset,
            color,
            note,
            now,
            anchor_strategy,
            content_hash_ref,
            context_before,
            context_after,
            state,
        )
        res = self.backend.execute(q, params)
        new_id = int(res.lastrowid or 0)
        return self.get_highlight(new_id)

    def list_highlights_by_item(self, item_id: int) -> List[HighlightRow]:
        q = (
            "SELECT id, user_id, item_id, quote, start_offset, end_offset, color, note, created_at, "
            "anchor_strategy, content_hash_ref, context_before, context_after, state "
            "FROM reading_highlights WHERE user_id = ? AND item_id = ? ORDER BY created_at ASC"
        )
        rows = self.backend.execute(q, (self.user_id, item_id)).rows
        return [HighlightRow(**row) for row in rows]

    def get_highlight(self, highlight_id: int) -> HighlightRow:
        q = (
            "SELECT id, user_id, item_id, quote, start_offset, end_offset, color, note, created_at, "
            "anchor_strategy, content_hash_ref, context_before, context_after, state "
            "FROM reading_highlights WHERE id = ? AND user_id = ?"
        )
        row = self.backend.execute(q, (highlight_id, self.user_id)).first
        if not row:
            raise KeyError("highlight_not_found")
        return HighlightRow(**row)

    def update_highlight(self, highlight_id: int, patch: Dict[str, Any]) -> HighlightRow:
        if not patch:
            return self.get_highlight(highlight_id)
        fields = []
        params: List[Any] = []
        for key in ("color", "note", "state"):
            if key in patch and patch[key] is not None:
                fields.append(f"{key} = ?")
                params.append(patch[key])
        if not fields:
            return self.get_highlight(highlight_id)
        params.extend([highlight_id, self.user_id])
        q = f"UPDATE reading_highlights SET {', '.join(fields)} WHERE id = ? AND user_id = ?"
        res = self.backend.execute(q, tuple(params))
        if res.rowcount <= 0:
            raise KeyError("highlight_not_found")
        return self.get_highlight(highlight_id)

    def delete_highlight(self, highlight_id: int) -> bool:
        q = "DELETE FROM reading_highlights WHERE id = ? AND user_id = ?"
        res = self.backend.execute(q, (highlight_id, self.user_id))
        return res.rowcount > 0

    # ------------------------
    # Maintenance hooks
    # ------------------------
    def mark_highlights_stale_if_content_changed(self, item_id: int, new_content_hash: Optional[str]) -> int:
        """Mark highlights as stale if their stored content_hash_ref doesn't match new hash.

        Returns number of rows updated. Intended to be called by item update pipeline.
        """
        if not new_content_hash:
            return 0
        q = (
            "UPDATE reading_highlights SET state = 'stale' WHERE user_id = ? AND item_id = ? "
            "AND content_hash_ref IS NOT NULL AND content_hash_ref <> ?"
        )
        res = self.backend.execute(q, (self.user_id, item_id, new_content_hash))
        return int(res.rowcount or 0)

    # ------------------------
    # Outputs artifacts API
    # ------------------------
    @dataclass
    class OutputArtifactRow:
        id: int
        user_id: str
        job_id: Optional[int]
        run_id: Optional[int]
        type: str
        title: str
        format: str
        storage_path: str
        metadata_json: Optional[str]
        created_at: str
        media_item_id: Optional[int]
        chatbook_path: Optional[str]

    def create_output_artifact(
        self,
        *,
        type_: str,
        title: str,
        format_: str,
        storage_path: str,
        metadata_json: Optional[str] = None,
        job_id: Optional[int] = None,
        run_id: Optional[int] = None,
        media_item_id: Optional[int] = None,
        chatbook_path: Optional[str] = None,
        retention_until: Optional[str] = None,
    ) -> "CollectionsDatabase.OutputArtifactRow":
        now = _utcnow_iso()
        q = (
            "INSERT INTO outputs (user_id, job_id, run_id, type, title, format, storage_path, metadata_json, created_at, media_item_id, chatbook_path, deleted, deleted_at, retention_until) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)"
        )
        params = (
            self.user_id,
            job_id,
            run_id,
            type_,
            title,
            format_,
            storage_path,
            metadata_json,
            now,
            media_item_id,
            chatbook_path,
            retention_until,
        )
        res = self.backend.execute(q, params)
        new_id = int(res.lastrowid or 0)
        return self.get_output_artifact(new_id)

    def get_output_artifact(self, output_id: int, include_deleted: bool = False) -> "CollectionsDatabase.OutputArtifactRow":
        cond = "id = ? AND user_id = ?" + ("" if include_deleted else " AND deleted = 0")
        q = (
            "SELECT id, user_id, job_id, run_id, type, title, format, storage_path, metadata_json, created_at, media_item_id, chatbook_path "
            f"FROM outputs WHERE {cond}"
        )
        row = self.backend.execute(q, (output_id, self.user_id)).first
        if not row:
            raise KeyError("output_not_found")
        return CollectionsDatabase.OutputArtifactRow(**row)

    def delete_output_artifact(self, output_id: int, *, hard: bool = False) -> bool:
        if hard:
            q = "DELETE FROM outputs WHERE id = ? AND user_id = ?"
            res = self.backend.execute(q, (output_id, self.user_id))
            return res.rowcount > 0
        q = "UPDATE outputs SET deleted = 1, deleted_at = ? WHERE id = ? AND user_id = ? AND deleted = 0"
        res = self.backend.execute(q, (_utcnow_iso(), output_id, self.user_id))
        return res.rowcount > 0

    def get_output_artifact_by_title(self, title: str, format_: Optional[str] = None, include_deleted: bool = False) -> "CollectionsDatabase.OutputArtifactRow":
        where = ["user_id = ?", "title = ?"]
        params: list[Any] = [self.user_id, title]
        if format_:
            where.append("format = ?")
            params.append(format_)
        if not include_deleted:
            where.append("deleted = 0")
        q = (
            "SELECT id, user_id, job_id, run_id, type, title, format, storage_path, metadata_json, created_at, media_item_id, chatbook_path "
            f"FROM outputs WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT 1"
        )
        row = self.backend.execute(q, tuple(params)).first
        if not row:
            raise KeyError("output_not_found")
        return CollectionsDatabase.OutputArtifactRow(**row)

    def list_output_artifacts(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        job_id: Optional[int] = None,
        run_id: Optional[int] = None,
        type_: Optional[str] = None,
        include_deleted: bool = False,
        only_deleted: bool = False,
    ) -> tuple[list["CollectionsDatabase.OutputArtifactRow"], int]:
        where = ["user_id = ?"]
        params: list[Any] = [self.user_id]
        if only_deleted:
            where.append("deleted = 1")
        elif not include_deleted:
            where.append("deleted = 0")
        if job_id is not None:
            where.append("job_id = ?")
            params.append(job_id)
        if run_id is not None:
            where.append("run_id = ?")
            params.append(run_id)
        if type_:
            where.append("type = ?")
            params.append(type_)
        where_sql = " AND ".join(where)

        cq = f"SELECT COUNT(*) AS cnt FROM outputs WHERE {where_sql}"
        total = int(self.backend.execute(cq, tuple(params)).scalar or 0)
        sq = (
            "SELECT id, user_id, job_id, run_id, type, title, format, storage_path, metadata_json, created_at, media_item_id, chatbook_path "
            f"FROM outputs WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        rows = self.backend.execute(sq, tuple(params + [limit, offset])).rows
        return [CollectionsDatabase.OutputArtifactRow(**row) for row in rows], total

    def rename_output_artifact(self, output_id: int, new_title: str, new_storage_path: Optional[str] = None) -> "CollectionsDatabase.OutputArtifactRow":
        fields = ["title = ?"]
        params: list[Any] = [new_title]
        if new_storage_path is not None:
            fields.append("storage_path = ?")
            params.append(new_storage_path)
        params.extend([output_id, self.user_id])
        q = f"UPDATE outputs SET {', '.join(fields)} WHERE id = ? AND user_id = ? AND deleted = 0"
        res = self.backend.execute(q, tuple(params))
        if res.rowcount <= 0:
            raise KeyError("output_not_found")
        return self.get_output_artifact(output_id)

    def purge_expired_outputs(self) -> int:
        """Hard delete expired/retained outputs. Returns number of rows removed."""
        now = _utcnow_iso()
        # Hard delete those with retention_until past
        r1 = self.backend.execute(
            "DELETE FROM outputs WHERE user_id = ? AND retention_until IS NOT NULL AND retention_until <= ?",
            (self.user_id, now),
        )
        # Soft-deleted older than 30 days
        try:
            r2 = self.backend.execute(
                "DELETE FROM outputs WHERE user_id = ? AND deleted = 1 AND deleted_at IS NOT NULL AND julianday(?) - julianday(deleted_at) >= 30",
                (self.user_id, now),
            )
            return int((r1.rowcount or 0) + (r2.rowcount or 0))
        except Exception:
            return int(r1.rowcount or 0)
