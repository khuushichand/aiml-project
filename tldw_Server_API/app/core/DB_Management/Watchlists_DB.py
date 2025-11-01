"""
Watchlists_DB - Persistence for Watchlists (sources, groups/tags, jobs, runs).

Tables (per-user, colocated with Media DB):
- sources(id, user_id, name, url, source_type, active, settings_json,
          last_scraped_at, etag, last_modified, status, created_at, updated_at)
- groups(id, user_id, name, description, parent_group_id)
- source_groups(source_id, group_id)
- tags(id, user_id, name) with UNIQUE(user_id, name)
- source_tags(source_id, tag_id)
- scrape_jobs(id, user_id, name, description, scope_json, schedule_expr,
              active, max_concurrency, per_host_delay_ms, retry_policy_json,
              output_prefs_json, schedule_timezone, created_at, updated_at,
              last_run_at, next_run_at)
- scrape_runs(id, job_id, status, started_at, finished_at, stats_json,
              error_msg, log_path)
- scrape_run_items(run_id, media_id, source_id)
- scraped_items(id, run_id, job_id, source_id, media_id, media_uuid, url, title,
                summary, published_at, tags_json, status, reviewed, created_at)
- watchlist_outputs(id, run_id, job_id, type, format, title, content,
                    storage_path, metadata_json, media_item_id, chatbook_path,
                    created_at)

Notes:
- Backed by DatabaseBackendFactory; default to per-user SQLite Media DB path.
- Provides minimal CRUD required by the API layer; scraping is implemented elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from .backends.base import DatabaseBackend, DatabaseConfig, BackendType
from .backends.factory import DatabaseBackendFactory
from .db_path_utils import DatabasePaths


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


@dataclass
class SourceRow:
    id: int
    user_id: str
    name: str
    url: str
    source_type: str
    active: int
    settings_json: Optional[str]
    last_scraped_at: Optional[str]
    etag: Optional[str]
    last_modified: Optional[str]
    defer_until: Optional[str]
    status: Optional[str]
    consec_not_modified: Optional[int]
    created_at: str
    updated_at: str
    tags: List[str]


@dataclass
class GroupRow:
    id: int
    user_id: str
    name: str
    description: Optional[str]
    parent_group_id: Optional[int]


@dataclass
class TagRow:
    id: int
    user_id: str
    name: str


@dataclass
class JobRow:
    id: int
    user_id: str
    name: str
    description: Optional[str]
    scope_json: Optional[str]
    schedule_expr: Optional[str]
    schedule_timezone: Optional[str]
    active: int
    max_concurrency: Optional[int]
    per_host_delay_ms: Optional[int]
    retry_policy_json: Optional[str]
    output_prefs_json: Optional[str]
    job_filters_json: Optional[str]
    created_at: str
    updated_at: str
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    wf_schedule_id: Optional[str] = None


@dataclass
class RunRow:
    id: int
    job_id: int
    status: str
    started_at: Optional[str]
    finished_at: Optional[str]
    stats_json: Optional[str]
    error_msg: Optional[str]
    log_path: Optional[str]


@dataclass
class ScrapedItemRow:
    id: int
    run_id: int
    job_id: int
    source_id: int
    media_id: Optional[int]
    media_uuid: Optional[str]
    url: Optional[str]
    title: Optional[str]
    summary: Optional[str]
    published_at: Optional[str]
    tags_json: Optional[str]
    status: str
    reviewed: int
    created_at: str

    def tags(self) -> List[str]:
        if not self.tags_json:
            return []
        try:
            data = json.loads(self.tags_json)
            if isinstance(data, list):
                return [str(t) for t in data if isinstance(t, str)]
        except Exception:
            return []
        return []


@dataclass
class OutputRow:
    id: int
    run_id: int
    job_id: int
    type: str
    format: str
    title: Optional[str]
    content: Optional[str]
    storage_path: Optional[str]
    metadata_json: Optional[str]
    media_item_id: Optional[int]
    chatbook_path: Optional[str]
    version: int
    expires_at: Optional[str]
    created_at: str

    def metadata(self) -> Dict[str, Any]:
        if not self.metadata_json:
            return {}
        try:
            data = json.loads(self.metadata_json)
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
        return {}


class WatchlistsDatabase:
    # Keep track of schema initialization per DB path to avoid redundant ALTER checks/noise
    _schema_init_keys: set[str] = set()

    def __init__(self, user_id: int | str, backend: Optional[DatabaseBackend] = None):
        self.user_id = str(user_id)
        db_key: Optional[str] = None
        if backend is None:
            db_path = str(DatabasePaths.get_media_db_path(int(user_id)))
            cfg = DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=db_path)
            backend = DatabaseBackendFactory.create_backend(cfg)
            db_key = f"sqlite:{db_path}"
        else:
            # Fallback key when external backend is supplied (best-effort de-dupe)
            db_key = f"backend:{id(backend)}"
        self.backend = backend
        # De-duplicate schema ensures across startup/requests
        if db_key and db_key not in WatchlistsDatabase._schema_init_keys:
            self.ensure_schema()
            WatchlistsDatabase._schema_init_keys.add(db_key)
        elif not db_key:
            # If we couldn't derive a key, fall back to ensuring schema once here
            self.ensure_schema()

    @classmethod
    def for_user(cls, user_id: int | str) -> "WatchlistsDatabase":
        return cls(user_id=user_id)

    def ensure_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            source_type TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            settings_json TEXT,
            last_scraped_at TEXT,
            etag TEXT,
            last_modified TEXT,
            defer_until TEXT,
            status TEXT,
            consec_not_modified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sources_user ON sources(user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_sources_user_url ON sources(user_id, url);

        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            parent_group_id INTEGER
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_groups_user_name ON groups(user_id, name);

        CREATE TABLE IF NOT EXISTS source_groups (
            source_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            UNIQUE (source_id, group_id)
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE (user_id, name)
        );
        CREATE TABLE IF NOT EXISTS source_tags (
            source_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            UNIQUE (source_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS scrape_jobs (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            scope_json TEXT,
            schedule_expr TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            max_concurrency INTEGER,
            per_host_delay_ms INTEGER,
            retry_policy_json TEXT,
            output_prefs_json TEXT,
            job_filters_json TEXT,
            schedule_timezone TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_run_at TEXT,
            next_run_at TEXT,
            wf_schedule_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_user ON scrape_jobs(user_id);

        CREATE TABLE IF NOT EXISTS scrape_runs (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            stats_json TEXT,
            error_msg TEXT,
            log_path TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_runs_job ON scrape_runs(job_id);

        CREATE TABLE IF NOT EXISTS scrape_run_items (
            run_id INTEGER NOT NULL,
            media_id INTEGER NOT NULL,
            source_id INTEGER,
            UNIQUE (run_id, media_id)
        );

        -- Track per-source seen RSS/Atom items for deduplication
        CREATE TABLE IF NOT EXISTS source_seen_items (
            source_id INTEGER NOT NULL,
            item_key TEXT NOT NULL,
            etag TEXT,
            last_modified TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE (source_id, item_key)
        );

        CREATE TABLE IF NOT EXISTS scraped_items (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            source_id INTEGER NOT NULL,
            media_id INTEGER,
            media_uuid TEXT,
            url TEXT,
            title TEXT,
            summary TEXT,
            published_at TEXT,
            tags_json TEXT,
            status TEXT NOT NULL,
            reviewed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_scraped_items_run ON scraped_items(run_id);
        CREATE INDEX IF NOT EXISTS idx_scraped_items_job ON scraped_items(job_id);
        CREATE INDEX IF NOT EXISTS idx_scraped_items_source ON scraped_items(source_id);
        CREATE INDEX IF NOT EXISTS idx_scraped_items_status ON scraped_items(status);
        CREATE INDEX IF NOT EXISTS idx_scraped_items_reviewed ON scraped_items(reviewed);
        CREATE INDEX IF NOT EXISTS idx_scraped_items_created ON scraped_items(created_at);

        CREATE TABLE IF NOT EXISTS watchlist_outputs (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            format TEXT NOT NULL,
            title TEXT,
            content TEXT,
            storage_path TEXT,
            metadata_json TEXT,
            media_item_id INTEGER,
            chatbook_path TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            expires_at TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_watchlist_outputs_run ON watchlist_outputs(run_id);
        CREATE INDEX IF NOT EXISTS idx_watchlist_outputs_job ON watchlist_outputs(job_id);
        """
        self.backend.create_tables(ddl)
        # Backfill columns in case tables existed (guarded to avoid noisy duplicate-column errors)
        def _col_exists(table: str, col: str) -> bool:
            try:
                info = self.backend.get_table_info(table)
                names = {str(c.get("name")) for c in info if c.get("name") is not None}
                return col in names
            except Exception:
                return False

        if not _col_exists("scrape_jobs", "wf_schedule_id"):
            try:
                self.backend.execute("ALTER TABLE scrape_jobs ADD COLUMN wf_schedule_id TEXT", tuple())
            except Exception:
                pass
        if not _col_exists("scrape_jobs", "job_filters_json"):
            try:
                self.backend.execute("ALTER TABLE scrape_jobs ADD COLUMN job_filters_json TEXT", tuple())
            except Exception:
                pass
        if not _col_exists("sources", "defer_until"):
            try:
                self.backend.execute("ALTER TABLE sources ADD COLUMN defer_until TEXT", tuple())
            except Exception:
                pass
        if not _col_exists("sources", "consec_not_modified"):
            try:
                self.backend.execute("ALTER TABLE sources ADD COLUMN consec_not_modified INTEGER DEFAULT 0", tuple())
            except Exception:
                pass
        if not _col_exists("scrape_run_items", "source_id"):
            try:
                self.backend.execute("ALTER TABLE scrape_run_items ADD COLUMN source_id INTEGER", tuple())
            except Exception:
                pass
        if not _col_exists("watchlist_outputs", "version"):
            try:
                self.backend.execute("ALTER TABLE watchlist_outputs ADD COLUMN version INTEGER NOT NULL DEFAULT 1", tuple())
            except Exception:
                pass
        if not _col_exists("watchlist_outputs", "expires_at"):
            try:
                self.backend.execute("ALTER TABLE watchlist_outputs ADD COLUMN expires_at TEXT", tuple())
            except Exception:
                pass

    # ------------------------
    # Tags helpers
    # ------------------------
    def _normalize_tag(self, name: str) -> str:
        return name.strip().lower()

    def ensure_tag_ids(self, names: List[str]) -> List[int]:
        normed = [self._normalize_tag(n) for n in names if n and n.strip()]
        ids: List[int] = []
        select_sql = "SELECT id FROM tags WHERE user_id = ? AND name = ?"
        insert_sql = "INSERT INTO tags (user_id, name) VALUES (?, ?)"
        for nm in normed:
            params = (self.user_id, nm)
            row = self.backend.execute(select_sql, params).first
            if row:
                ids.append(int(row.get("id")))
                continue
            insert_exc: Optional[Exception] = None
            tag_id: Optional[int] = None
            try:
                res = self.backend.execute(insert_sql, params)
                if res.lastrowid:
                    tag_id = int(res.lastrowid)
            except Exception as exc:
                insert_exc = exc
            if tag_id is None:
                row = self.backend.execute(select_sql, params).first
                if row:
                    tag_id = int(row.get("id"))
            if tag_id is None:
                if insert_exc:
                    raise insert_exc
                raise RuntimeError("failed_to_ensure_tag_id")
            ids.append(tag_id)
        return ids

    def _lookup_tag_ids(self, names: Iterable[str]) -> Dict[str, int]:
        normed: List[str] = []
        seen: set[str] = set()
        for raw in names or []:
            if not raw:
                continue
            nm = self._normalize_tag(str(raw))
            if not nm or nm in seen:
                continue
            seen.add(nm)
            normed.append(nm)
        if not normed:
            return {}

        placeholders = ",".join("?" for _ in normed)
        params = [self.user_id, *normed]
        rows = self.backend.execute(
            f"SELECT name, id FROM tags WHERE user_id = ? AND name IN ({placeholders})",
            tuple(params),
        ).rows
        out: Dict[str, int] = {}
        for row in rows:
            name_val = row.get("name")
            tag_id = row.get("id")
            if name_val is None or tag_id is None:
                continue
            try:
                out[str(name_val)] = int(tag_id)
            except Exception:
                continue
        return out

    def list_tags(self, q: Optional[str], limit: int, offset: int) -> Tuple[List[TagRow], int]:
        where = ["user_id = ?"]
        params: List[Any] = [self.user_id]
        if q:
            where.append("name LIKE ?")
            params.append(f"%{q}%")
        where_sql = " AND ".join(where)
        total = int(self.backend.execute(f"SELECT COUNT(*) AS cnt FROM tags WHERE {where_sql}", tuple(params)).scalar or 0)
        rows = self.backend.execute(
            f"SELECT id, user_id, name FROM tags WHERE {where_sql} ORDER BY name LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        ).rows
        return [TagRow(**r) for r in rows], total

    # ------------------------
    # Sources
    # ------------------------
    def create_source(
        self,
        *,
        name: str,
        url: str,
        source_type: str,
        active: bool = True,
        settings_json: Optional[str] = None,
        tags: Optional[List[str]] = None,
        group_ids: Optional[List[int]] = None,
    ) -> SourceRow:
        now = _utcnow_iso()
        # Try insert; if UNIQUE(user_id,url) violates, fetch existing id and proceed idempotently
        sid: Optional[int] = None
        try:
            res = self.backend.execute(
                "INSERT INTO sources (user_id, name, url, source_type, active, settings_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (self.user_id, name, url, source_type, 1 if active else 0, settings_json, now, now),
            )
            sid = int(res.lastrowid or 0)
        except Exception:
            # Look up existing source for idempotency
            try:
                row = self.backend.execute(
                    "SELECT id FROM sources WHERE user_id = ? AND url = ?",
                    (self.user_id, url),
                ).first
                if row and row.get("id") is not None:
                    sid = int(row.get("id"))
                else:
                    raise
            except Exception as e:
                raise e
        if sid is None:
            raise RuntimeError("failed_to_create_or_lookup_source")
        if tags:
            tag_ids = self.ensure_tag_ids(tags)
            for tid in tag_ids:
                try:
                    self.backend.execute(
                        "INSERT INTO source_tags (source_id, tag_id) VALUES (?, ?) ON CONFLICT(source_id, tag_id) DO NOTHING",
                        (sid, tid),
                    )
                except Exception:
                    # Fallback for engines without ON CONFLICT (should rarely trigger)
                    self.backend.execute(
                        "INSERT INTO source_tags (source_id, tag_id) SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM source_tags WHERE source_id = ? AND tag_id = ?)",
                        (sid, tid, sid, tid),
                    )
        if group_ids:
            for gid in group_ids:
                try:
                    self.backend.execute(
                        "INSERT INTO source_groups (source_id, group_id) VALUES (?, ?) ON CONFLICT(source_id, group_id) DO NOTHING",
                        (sid, gid),
                    )
                except Exception:
                    self.backend.execute(
                        "INSERT INTO source_groups (source_id, group_id) SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM source_groups WHERE source_id = ? AND group_id = ?)",
                        (sid, gid, sid, gid),
                    )
        return self.get_source(sid)

    def get_source(self, source_id: int) -> SourceRow:
        row = self.backend.execute(
            "SELECT id, user_id, name, url, source_type, active, settings_json, last_scraped_at, etag, last_modified, defer_until, status, consec_not_modified, created_at, updated_at FROM sources WHERE id = ? AND user_id = ?",
            (source_id, self.user_id),
        ).first
        if not row:
            raise KeyError("source_not_found")
        tags_rows = self.backend.execute(
            "SELECT t.name FROM source_tags st JOIN tags t ON st.tag_id = t.id WHERE st.source_id = ?",
            (source_id,),
        ).rows
        tags = [r.get("name") for r in tags_rows if r.get("name")]
        return SourceRow(tags=tags, **row)  # type: ignore[arg-type]

    def list_sources(self, q: Optional[str], tag_names: Optional[List[str]], limit: int, offset: int) -> Tuple[List[SourceRow], int]:
        where = ["user_id = ?"]
        params: List[Any] = [self.user_id]
        if q:
            where.append("(name LIKE ? OR url LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])
        # Tag filter: require all tags
        if tag_names:
            normalized_tags = []
            for tag in tag_names:
                if not tag:
                    continue
                nm = self._normalize_tag(str(tag))
                if nm and nm not in normalized_tags:
                    normalized_tags.append(nm)
            if normalized_tags:
                tag_map = self._lookup_tag_ids(normalized_tags)
                if len(tag_map) < len(normalized_tags):
                    return [], 0
                for nm in normalized_tags:
                    tid = tag_map[nm]
                    where.append(
                        "EXISTS (SELECT 1 FROM source_tags st WHERE st.source_id = sources.id AND st.tag_id = ?)"
                    )
                    params.append(tid)
        where_sql = " AND ".join(where)
        total = int(self.backend.execute(f"SELECT COUNT(*) AS cnt FROM sources WHERE {where_sql}", tuple(params)).scalar or 0)
        rows = self.backend.execute(
            f"SELECT id, user_id, name, url, source_type, active, settings_json, last_scraped_at, etag, last_modified, defer_until, status, consec_not_modified, created_at, updated_at FROM sources WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        ).rows
        out: List[SourceRow] = []
        for r in rows:
            sid = int(r.get("id"))
            trows = self.backend.execute(
                "SELECT t.name FROM source_tags st JOIN tags t ON st.tag_id = t.id WHERE st.source_id = ?",
                (sid,),
            ).rows
            tags = [tr.get("name") for tr in trows if tr.get("name")]
            out.append(SourceRow(tags=tags, **r))  # type: ignore[arg-type]
        return out, total

    def update_source(self, source_id: int, patch: Dict[str, Any]) -> SourceRow:
        if not patch:
            return self.get_source(source_id)
        fields = []
        params: List[Any] = []
        for key in ("name", "url", "source_type", "active", "settings_json", "status"):
            if key in patch and patch[key] is not None:
                fields.append(f"{key} = ?")
                val = patch[key]
                if key == "active":
                    val = 1 if bool(val) else 0
                params.append(val)
        if fields:
            fields.append("updated_at = ?")
            params.append(_utcnow_iso())
            params.extend([source_id, self.user_id])
            self.backend.execute(
                f"UPDATE sources SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                tuple(params),
            )
        # tags/group updates handled via separate helpers
        return self.get_source(source_id)

    def update_source_scrape_meta(
        self,
        source_id: int,
        *,
        last_scraped_at: Optional[str] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        defer_until: Optional[str] = None,
        status: Optional[str] = None,
        consec_not_modified: Optional[int] = None,
    ) -> None:
        """Update scrape metadata fields for a source (idempotent, partial)."""
        fields: list[str] = []
        params: list[Any] = []
        if last_scraped_at is not None:
            fields.append("last_scraped_at = ?")
            params.append(last_scraped_at)
        if etag is not None:
            fields.append("etag = ?")
            params.append(etag)
        if last_modified is not None:
            fields.append("last_modified = ?")
            params.append(last_modified)
        if defer_until is not None:
            fields.append("defer_until = ?")
            params.append(defer_until)
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if consec_not_modified is not None:
            fields.append("consec_not_modified = ?")
            params.append(int(consec_not_modified))
        if not fields:
            return
        params.extend([source_id, self.user_id])
        self.backend.execute(
            f"UPDATE sources SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(params),
        )

    def clear_source_defer_until(self, source_id: int) -> None:
        self.backend.execute(
            "UPDATE sources SET defer_until = NULL WHERE id = ? AND user_id = ?",
            (source_id, self.user_id),
        )

    def set_source_tags(self, source_id: int, tag_names: List[str]) -> List[str]:
        tag_ids = self.ensure_tag_ids(tag_names)
        self.backend.execute("DELETE FROM source_tags WHERE source_id = ?", (source_id,))
        for tid in tag_ids:
            try:
                self.backend.execute(
                    "INSERT INTO source_tags (source_id, tag_id) VALUES (?, ?) ON CONFLICT(source_id, tag_id) DO NOTHING",
                    (source_id, tid),
                )
            except Exception:
                self.backend.execute(
                    "INSERT INTO source_tags (source_id, tag_id) SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM source_tags WHERE source_id = ? AND tag_id = ?)",
                    (source_id, tid, source_id, tid),
                )
        rows = self.backend.execute(
            "SELECT t.name FROM source_tags st JOIN tags t ON st.tag_id = t.id WHERE st.source_id = ?",
            (source_id,),
        ).rows
        return [r.get("name") for r in rows if r.get("name")]

    def delete_source(self, source_id: int) -> bool:
        res = self.backend.execute("DELETE FROM sources WHERE id = ? AND user_id = ?", (source_id, self.user_id))
        return res.rowcount > 0

    def list_sources_by_group_ids(self, group_ids: List[int], *, active_only: bool = True) -> List[SourceRow]:
        """Return sources that belong to any of the provided group IDs (OR semantics)."""
        if not group_ids:
            return []
        placeholders = ",".join(["?"] * len(group_ids))
        active_clause = "AND s.active = 1" if active_only else ""
        rows = self.backend.execute(
            f"""
            SELECT s.id, s.user_id, s.name, s.url, s.source_type, s.active, s.settings_json,
                   s.last_scraped_at, s.etag, s.last_modified, s.defer_until, s.status,
                   s.consec_not_modified, s.created_at, s.updated_at
            FROM sources s
            WHERE s.user_id = ? {active_clause}
              AND EXISTS (
                SELECT 1 FROM source_groups sg
                WHERE sg.source_id = s.id AND sg.group_id IN ({placeholders})
              )
            ORDER BY s.created_at DESC
            """,
            tuple([self.user_id] + group_ids),
        ).rows
        out: List[SourceRow] = []
        for r in rows:
            sid = int(r.get("id"))
            trows = self.backend.execute(
                "SELECT t.name FROM source_tags st JOIN tags t ON st.tag_id = t.id WHERE st.source_id = ?",
                (sid,),
            ).rows
            tags = [tr.get("name") for tr in trows if tr.get("name")]
            out.append(SourceRow(tags=tags, **r))  # type: ignore[arg-type]
        return out

    # ------------------------
    # Groups
    # ------------------------
    def create_group(self, name: str, description: Optional[str], parent_group_id: Optional[int]) -> GroupRow:
        # Idempotent by (user_id, name)
        try:
            res = self.backend.execute(
                "INSERT INTO groups (user_id, name, description, parent_group_id) VALUES (?, ?, ?, ?)",
                (self.user_id, name, description, parent_group_id),
            )
            return self.get_group(int(res.lastrowid or 0))
        except Exception:
            # On UNIQUE violation, fetch existing
            row = self.backend.execute(
                "SELECT id FROM groups WHERE user_id = ? AND name = ?",
                (self.user_id, name),
            ).first
            if not row:
                # Re-raise original path if not found
                raise
            return self.get_group(int(row.get("id")))

    def get_group(self, group_id: int) -> GroupRow:
        row = self.backend.execute(
            "SELECT id, user_id, name, description, parent_group_id FROM groups WHERE id = ? AND user_id = ?",
            (group_id, self.user_id),
        ).first
        if not row:
            raise KeyError("group_not_found")
        return GroupRow(**row)

    def list_groups(self, q: Optional[str], limit: int, offset: int) -> Tuple[List[GroupRow], int]:
        where = ["user_id = ?"]
        params: List[Any] = [self.user_id]
        if q:
            where.append("name LIKE ?")
            params.append(f"%{q}%")
        total = int(self.backend.execute(f"SELECT COUNT(*) AS cnt FROM groups WHERE {' AND '.join(where)}", tuple(params)).scalar or 0)
        rows = self.backend.execute(
            f"SELECT id, user_id, name, description, parent_group_id FROM groups WHERE {' AND '.join(where)} ORDER BY name LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        ).rows
        return [GroupRow(**r) for r in rows], total

    def update_group(self, group_id: int, patch: Dict[str, Any]) -> GroupRow:
        fields = []
        params: List[Any] = []
        for key in ("name", "description", "parent_group_id"):
            if key in patch and patch[key] is not None:
                fields.append(f"{key} = ?")
                params.append(patch[key])
        if fields:
            params.extend([group_id, self.user_id])
            self.backend.execute(
                f"UPDATE groups SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                tuple(params),
            )
        return self.get_group(group_id)

    def delete_group(self, group_id: int) -> bool:
        res = self.backend.execute("DELETE FROM groups WHERE id = ? AND user_id = ?", (group_id, self.user_id))
        return res.rowcount > 0

    # ------------------------
    # Jobs & Runs
    # ------------------------
    def create_job(
        self,
        *,
        name: str,
        description: Optional[str],
        scope_json: Optional[str],
        schedule_expr: Optional[str],
        schedule_timezone: Optional[str],
        active: bool,
        max_concurrency: Optional[int],
        per_host_delay_ms: Optional[int],
        retry_policy_json: Optional[str],
        output_prefs_json: Optional[str],
        job_filters_json: Optional[str] = None,
    ) -> JobRow:
        now = _utcnow_iso()
        res = self.backend.execute(
            """
            INSERT INTO scrape_jobs (user_id, name, description, scope_json, schedule_expr, active, max_concurrency,
            per_host_delay_ms, retry_policy_json, output_prefs_json, job_filters_json, schedule_timezone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.user_id,
                name,
                description,
                scope_json,
                schedule_expr,
                1 if active else 0,
                max_concurrency,
                per_host_delay_ms,
                retry_policy_json,
                output_prefs_json,
                job_filters_json,
                schedule_timezone,
                now,
                now,
            ),
        )
        return self.get_job(int(res.lastrowid or 0))

    def get_job(self, job_id: int) -> JobRow:
        row = self.backend.execute(
            """
            SELECT id, user_id, name, description, scope_json, schedule_expr, schedule_timezone, active,
                   max_concurrency, per_host_delay_ms, retry_policy_json, output_prefs_json, job_filters_json,
                   created_at, updated_at, last_run_at, next_run_at, wf_schedule_id
            FROM scrape_jobs WHERE id = ? AND user_id = ?
            """,
            (job_id, self.user_id),
        ).first
        if not row:
            raise KeyError("job_not_found")
        return JobRow(**row)

    def list_jobs(self, q: Optional[str], limit: int, offset: int) -> Tuple[List[JobRow], int]:
        where = ["user_id = ?"]
        params: List[Any] = [self.user_id]
        if q:
            where.append("(name LIKE ? OR description LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])
        total = int(self.backend.execute(f"SELECT COUNT(*) AS cnt FROM scrape_jobs WHERE {' AND '.join(where)}", tuple(params)).scalar or 0)
        rows = self.backend.execute(
            f"SELECT id, user_id, name, description, scope_json, schedule_expr, schedule_timezone, active, max_concurrency, per_host_delay_ms, retry_policy_json, output_prefs_json, job_filters_json, created_at, updated_at, last_run_at, next_run_at, wf_schedule_id FROM scrape_jobs WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        ).rows
        return [JobRow(**r) for r in rows], total

    def set_job_filters(self, job_id: int, filters: Optional[Any]) -> JobRow:
        """Replace the job's filters payload.

        Accepts either a dict (e.g., {"filters": [...]}) or a raw list of filter objects.
        Passing None clears the filters (sets NULL).
        Returns the updated JobRow.
        """
        if filters is None:
            payload_json = None
        else:
            try:
                if isinstance(filters, dict):
                    payload = filters
                elif isinstance(filters, list):
                    payload = {"filters": filters}
                else:
                    # Fallback to best-effort JSON-serializable form
                    payload = {"filters": filters}
                payload_json = json.dumps(payload, ensure_ascii=False)
            except Exception:
                payload_json = None
        # Use update_job to ensure updated_at is maintained
        return self.update_job(job_id, {"job_filters_json": payload_json})

    def get_job_filters(self, job_id: int) -> Dict[str, Any]:
        """Fetch and parse the job's filters payload.

        Returns a dict in the normalized shape {"filters": [...]}. Invalid or missing
        payloads yield {"filters": []}.
        """
        row = self.get_job(job_id)
        raw = getattr(row, "job_filters_json", None)
        if not raw:
            return {"filters": []}
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and isinstance(data.get("filters"), list):
                return {"filters": list(data.get("filters") or [])}
            if isinstance(data, list):
                return {"filters": data}
        except Exception:
            pass
        return {"filters": []}

    def update_job(self, job_id: int, patch: Dict[str, Any]) -> JobRow:
        if not patch:
            return self.get_job(job_id)
        fields = []
        params: List[Any] = []
        for key in (
            "name",
            "description",
            "scope_json",
            "schedule_expr",
            "schedule_timezone",
            "active",
            "max_concurrency",
            "per_host_delay_ms",
            "retry_policy_json",
            "output_prefs_json",
            "job_filters_json",
        ):
            if key in patch and patch[key] is not None:
                fields.append(f"{key} = ?")
                val = patch[key]
                if key == "active":
                    val = 1 if bool(val) else 0
                params.append(val)
        if fields:
            fields.append("updated_at = ?")
            params.append(_utcnow_iso())
            params.extend([job_id, self.user_id])
            self.backend.execute(
                f"UPDATE scrape_jobs SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                tuple(params),
            )
        return self.get_job(job_id)

    def delete_job(self, job_id: int) -> bool:
        res = self.backend.execute("DELETE FROM scrape_jobs WHERE id = ? AND user_id = ?", (job_id, self.user_id))
        return res.rowcount > 0

    # ---- Schedule/history helpers ----
    def set_job_schedule_id(self, job_id: int, schedule_id: Optional[str]) -> None:
        self.backend.execute(
            "UPDATE scrape_jobs SET wf_schedule_id = ? WHERE id = ? AND user_id = ?",
            (schedule_id, job_id, self.user_id),
        )

    def set_job_history(self, job_id: int, *, last_run_at: Optional[str] = None, next_run_at: Optional[str] = None) -> None:
        sets = []
        params: list[Any] = []
        if last_run_at is not None:
            sets.append("last_run_at = ?")
            params.append(last_run_at)
        if next_run_at is not None:
            sets.append("next_run_at = ?")
            params.append(next_run_at)
        if not sets:
            return
        params.extend([job_id, self.user_id])
        self.backend.execute(
            f"UPDATE scrape_jobs SET {', '.join(sets)} WHERE id = ? AND user_id = ?",
            tuple(params),
        )

    def create_run(self, job_id: int, status: str = "queued") -> RunRow:
        res = self.backend.execute(
            "INSERT INTO scrape_runs (job_id, status, started_at) VALUES (?, ?, ?)",
            (job_id, status, _utcnow_iso()),
        )
        return self.get_run(int(res.lastrowid or 0))

    def get_run(self, run_id: int) -> RunRow:
        row = self.backend.execute(
            "SELECT id, job_id, status, started_at, finished_at, stats_json, error_msg, log_path FROM scrape_runs WHERE id = ?",
            (run_id,),
        ).first
        if not row:
            raise KeyError("run_not_found")
        return RunRow(**row)

    def list_runs_for_job(self, job_id: int, limit: int, offset: int) -> Tuple[List[RunRow], int]:
        total = int(self.backend.execute("SELECT COUNT(*) AS cnt FROM scrape_runs WHERE job_id = ?", (job_id,)).scalar or 0)
        rows = self.backend.execute(
            "SELECT id, job_id, status, started_at, finished_at, stats_json, error_msg, log_path FROM scrape_runs WHERE job_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (job_id, limit, offset),
        ).rows
        return [RunRow(**r) for r in rows], total

    def list_runs(self, q: Optional[str], limit: int, offset: int) -> Tuple[List[RunRow], int]:
        """List runs across all jobs for this user.

        Optional q filters by job name/description, run status, or run id (text match).
        """
        where = ["j.user_id = ?"]
        params: List[Any] = [self.user_id]
        if q:
            like = f"%{q}%"
            # Match job name/description or run status/id (text)
            where.append("(j.name LIKE ? OR j.description LIKE ? OR sr.status LIKE ? OR CAST(sr.id AS TEXT) LIKE ?)")
            params.extend([like, like, like, like])
        where_sql = " AND ".join(where)
        total = int(
            self.backend.execute(
                f"SELECT COUNT(*) AS cnt FROM scrape_runs sr JOIN scrape_jobs j ON j.id = sr.job_id WHERE {where_sql}",
                tuple(params),
            ).scalar or 0
        )
        rows = self.backend.execute(
            f"""
            SELECT sr.id, sr.job_id, sr.status, sr.started_at, sr.finished_at, sr.stats_json, sr.error_msg, sr.log_path
            FROM scrape_runs sr JOIN scrape_jobs j ON j.id = sr.job_id
            WHERE {where_sql}
            ORDER BY sr.id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [limit, offset]),
        ).rows
        return [RunRow(**r) for r in rows], total

    def append_run_item(self, run_id: int, media_id: int, source_id: Optional[int] = None) -> None:
        stmt = (
            "INSERT INTO scrape_run_items (run_id, media_id, source_id) "
            "VALUES (?, ?, ?) ON CONFLICT(run_id, media_id) DO NOTHING"
        )
        try:
            self.backend.execute(stmt, (run_id, media_id, source_id))
        except Exception:
            self.backend.execute(
                "INSERT INTO scrape_run_items (run_id, media_id, source_id) "
                "SELECT ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM scrape_run_items WHERE run_id = ? AND media_id = ?)",
                (run_id, media_id, source_id, run_id, media_id),
            )

    def list_run_media_ids(self, run_id: int, limit: int = 1000) -> List[int]:
        rows = self.backend.execute(
            "SELECT media_id FROM scrape_run_items WHERE run_id = ? ORDER BY media_id LIMIT ?",
            (run_id, limit),
        ).rows
        mids: List[int] = []
        for r in rows:
            v = r.get("media_id")
            try:
                mids.append(int(v))
            except Exception:
                continue
        return mids

    def purge_expired_outputs(self, now_iso: Optional[str] = None) -> int:
        now_iso = now_iso or _utcnow_iso()
        result = self.backend.execute(
            "DELETE FROM watchlist_outputs WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now_iso,),
        )
        return int(result.rowcount or 0)

    def next_output_version(self, run_id: int) -> int:
        row = self.backend.execute(
            "SELECT MAX(version) AS max_version FROM watchlist_outputs WHERE run_id = ?",
            (run_id,),
        ).first
        max_version = row.get("max_version") if row else None
        try:
            return int(max_version or 0) + 1
        except Exception:
            return 1

    # ------------------------
    # Scraped items
    # ------------------------
    def record_scraped_item(
        self,
        *,
        run_id: int,
        job_id: int,
        source_id: int,
        media_id: Optional[int],
        media_uuid: Optional[str],
        url: Optional[str],
        title: Optional[str],
        summary: Optional[str],
        published_at: Optional[str],
        tags: Optional[List[str]],
        status: str,
    ) -> ScrapedItemRow:
        created_at = _utcnow_iso()
        tags_json = json.dumps(tags or [])
        res = self.backend.execute(
            """
            INSERT INTO scraped_items (
                run_id, job_id, source_id, media_id, media_uuid, url, title,
                summary, published_at, tags_json, status, reviewed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                run_id,
                job_id,
                source_id,
                media_id,
                media_uuid,
                url,
                title,
                summary,
                published_at,
                tags_json,
                status,
                created_at,
            ),
        )
        return self.get_item(int(res.lastrowid or 0))

    def get_item(self, item_id: int) -> ScrapedItemRow:
        row = self.backend.execute(
            """
            SELECT id, run_id, job_id, source_id, media_id, media_uuid, url, title,
                   summary, published_at, tags_json, status, reviewed, created_at
            FROM scraped_items
            WHERE id = ?
            """,
            (item_id,),
        ).first
        if not row:
            raise KeyError("item_not_found")
        return ScrapedItemRow(**row)

    def list_items(
        self,
        *,
        run_id: Optional[int] = None,
        job_id: Optional[int] = None,
        source_id: Optional[int] = None,
        status: Optional[str] = None,
        reviewed: Optional[bool] = None,
        search: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[ScrapedItemRow], int]:
        where = ["1=1"]
        params: List[Any] = []
        if run_id is not None:
            where.append("run_id = ?")
            params.append(run_id)
        if job_id is not None:
            where.append("job_id = ?")
            params.append(job_id)
        if source_id is not None:
            where.append("source_id = ?")
            params.append(source_id)
        if status:
            where.append("status = ?")
            params.append(status)
        if reviewed is not None:
            where.append("reviewed = ?")
            params.append(1 if reviewed else 0)
        if since:
            where.append("created_at >= ?")
            params.append(since)
        if until:
            where.append("created_at <= ?")
            params.append(until)
        if search:
            like = f"%{search}%"
            where.append("(title LIKE ? OR summary LIKE ?)")
            params.extend([like, like])
        where_sql = " AND ".join(where)
        total = int(
            self.backend.execute(
                f"SELECT COUNT(*) AS cnt FROM scraped_items WHERE {where_sql}",
                tuple(params),
            ).scalar
            or 0
        )
        rows = self.backend.execute(
            f"""
            SELECT id, run_id, job_id, source_id, media_id, media_uuid, url, title,
                   summary, published_at, tags_json, status, reviewed, created_at
            FROM scraped_items
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [limit, offset]),
        ).rows
        return [ScrapedItemRow(**r) for r in rows], total

    def get_items_by_ids(self, item_ids: List[int]) -> List[ScrapedItemRow]:
        if not item_ids:
            return []
        placeholders = ",".join("?" for _ in item_ids)
        rows = self.backend.execute(
            f"""
            SELECT id, run_id, job_id, source_id, media_id, media_uuid, url, title,
                   summary, published_at, tags_json, status, reviewed, created_at
            FROM scraped_items
            WHERE id IN ({placeholders})
            """,
            tuple(item_ids),
        ).rows
        return [ScrapedItemRow(**r) for r in rows]

    def update_item_flags(
        self,
        item_id: int,
        *,
        reviewed: Optional[bool] = None,
        status: Optional[str] = None,
    ) -> ScrapedItemRow:
        fields: List[str] = []
        params: List[Any] = []
        if reviewed is not None:
            fields.append("reviewed = ?")
            params.append(1 if reviewed else 0)
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if not fields:
            return self.get_item(item_id)
        params.append(item_id)
        self.backend.execute(
            f"UPDATE scraped_items SET {', '.join(fields)} WHERE id = ?",
            tuple(params),
        )
        return self.get_item(item_id)

    # ------------------------
    # Outputs
    # ------------------------
    def create_output(
        self,
        *,
        run_id: int,
        job_id: int,
        type: str,
        format: str,
        title: Optional[str],
        content: Optional[str],
        storage_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        media_item_id: Optional[int] = None,
        chatbook_path: Optional[str] = None,
        version: int = 1,
        expires_at: Optional[str] = None,
    ) -> OutputRow:
        created_at = _utcnow_iso()
        res = self.backend.execute(
            """
            INSERT INTO watchlist_outputs (
                run_id, job_id, type, format, title, content, storage_path,
                metadata_json, media_item_id, chatbook_path, version, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                job_id,
                type,
                format,
                title,
                content,
                storage_path,
                json.dumps(metadata or {}),
                media_item_id,
                chatbook_path,
                version,
                expires_at,
                created_at,
            ),
        )
        return self.get_output(int(res.lastrowid or 0))

    def get_output(self, output_id: int) -> OutputRow:
        row = self.backend.execute(
            """
            SELECT id, run_id, job_id, type, format, title, content, storage_path,
                   metadata_json, media_item_id, chatbook_path, version, expires_at, created_at
            FROM watchlist_outputs
            WHERE id = ?
            """,
            (output_id,),
        ).first
        if not row:
            raise KeyError("output_not_found")
        return OutputRow(**row)

    def list_outputs(
        self,
        *,
        run_id: Optional[int] = None,
        job_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[OutputRow], int]:
        self.purge_expired_outputs()
        where = ["1=1"]
        params: List[Any] = []
        if run_id is not None:
            where.append("run_id = ?")
            params.append(run_id)
        if job_id is not None:
            where.append("job_id = ?")
            params.append(job_id)
        where_sql = " AND ".join(where)
        total = int(
            self.backend.execute(
                f"SELECT COUNT(*) AS cnt FROM watchlist_outputs WHERE {where_sql}",
                tuple(params),
            ).scalar
            or 0
        )
        rows = self.backend.execute(
            f"""
            SELECT id, run_id, job_id, type, format, title, content, storage_path,
                   metadata_json, media_item_id, chatbook_path, version, expires_at, created_at
            FROM watchlist_outputs
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [limit, offset]),
        ).rows
        return [OutputRow(**r) for r in rows], total

    def update_output_record(
        self,
        output_id: int,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        chatbook_path: Optional[str] = None,
        storage_path: Optional[str] = None,
    ) -> OutputRow:
        assignments: List[str] = []
        params: List[Any] = []
        if metadata is not None:
            assignments.append("metadata_json = ?")
            params.append(json.dumps(metadata))
        if chatbook_path is not None:
            assignments.append("chatbook_path = ?")
            params.append(chatbook_path)
        if storage_path is not None:
            assignments.append("storage_path = ?")
            params.append(storage_path)
        if not assignments:
            return self.get_output(output_id)
        params.append(output_id)
        self.backend.execute(
            f"UPDATE watchlist_outputs SET {', '.join(assignments)} WHERE id = ?",
            tuple(params),
        )
        return self.get_output(output_id)

    def update_run(
        self,
        run_id: int,
        *,
        status: Optional[str] = None,
        finished_at: Optional[str] = None,
        stats_json: Optional[str] = None,
        error_msg: Optional[str] = None,
        log_path: Optional[str] = None,
    ) -> RunRow:
        fields: list[str] = []
        params: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if finished_at is not None:
            fields.append("finished_at = ?")
            params.append(finished_at)
        if stats_json is not None:
            fields.append("stats_json = ?")
            params.append(stats_json)
        if error_msg is not None:
            fields.append("error_msg = ?")
            params.append(error_msg)
        if log_path is not None:
            fields.append("log_path = ?")
            params.append(log_path)
        if not fields:
            return self.get_run(run_id)
        self.backend.execute(
            f"UPDATE scrape_runs SET {', '.join(fields)} WHERE id = ?",
            tuple(params + [run_id]),
        )
        return self.get_run(run_id)

    # ------------------------
    # RSS item-level dedup helpers
    # ------------------------
    def has_seen_item(self, source_id: int, item_key: str) -> bool:
        row = self.backend.execute(
            "SELECT 1 FROM source_seen_items WHERE source_id = ? AND item_key = ?",
            (source_id, item_key),
        ).first
        return bool(row)

    def mark_seen_item(
        self,
        source_id: int,
        item_key: str,
        *,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        seen_at: Optional[str] = None,
    ) -> None:
        ts = seen_at or _utcnow_iso()
        # SQLite upsert pattern; backend handles SQL transparently in SQLite/Postgres where available
        try:
            self.backend.execute(
                """
                INSERT INTO source_seen_items (source_id, item_key, etag, last_modified, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, item_key) DO UPDATE SET
                    etag = COALESCE(excluded.etag, source_seen_items.etag),
                    last_modified = COALESCE(excluded.last_modified, source_seen_items.last_modified),
                    last_seen_at = excluded.last_seen_at
                """,
                (source_id, item_key, etag, last_modified, ts, ts),
            )
        except Exception:
            # Fallback for engines without ON CONFLICT support
            row = self.backend.execute(
                "SELECT 1 FROM source_seen_items WHERE source_id = ? AND item_key = ?",
                (source_id, item_key),
            ).first
            if row:
                self.backend.execute(
                    "UPDATE source_seen_items SET etag = COALESCE(?, etag), last_modified = COALESCE(?, last_modified), last_seen_at = ? WHERE source_id = ? AND item_key = ?",
                    (etag, last_modified, ts, source_id, item_key),
                )
            else:
                self.backend.execute(
                    "INSERT INTO source_seen_items (source_id, item_key, etag, last_modified, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (source_id, item_key, etag, last_modified, ts, ts),
                )

    def list_seen_item_keys(self, source_id: int, *, limit: Optional[int] = None) -> List[str]:
        sql = "SELECT item_key FROM source_seen_items WHERE source_id = ? ORDER BY last_seen_at DESC"
        params: Tuple[Any, ...] = (source_id,)
        if isinstance(limit, int) and limit > 0:
            sql = sql + " LIMIT ?"
            params = (source_id, limit)
        rows = self.backend.execute(sql, params).rows
        keys: List[str] = []
        for r in rows:
            k = r.get("item_key")
            if isinstance(k, str) and k:
                keys.append(k)
        return keys
