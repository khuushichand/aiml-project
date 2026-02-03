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

Notes:
- Backed by DatabaseBackendFactory; default to per-user SQLite Media DB path.
- Provides minimal CRUD required by the API layer; scraping is implemented elsewhere.
- Watchlists outputs are stored in Collections outputs; legacy watchlist_outputs is retired.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.DB_Management.content_backend import (
    get_content_backend,
    load_content_db_settings,
)

from .backends.base import BackendType, DatabaseBackend, DatabaseConfig
from .backends.factory import DatabaseBackendFactory
from .backends.query_utils import prepare_backend_statement
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
    settings_json: str | None
    last_scraped_at: str | None
    etag: str | None
    last_modified: str | None
    defer_until: str | None
    status: str | None
    consec_not_modified: int | None
    created_at: str
    updated_at: str
    tags: list[str]


@dataclass
class GroupRow:
    id: int
    user_id: str
    name: str
    description: str | None
    parent_group_id: int | None


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
    description: str | None
    scope_json: str | None
    schedule_expr: str | None
    schedule_timezone: str | None
    active: int
    max_concurrency: int | None
    per_host_delay_ms: int | None
    retry_policy_json: str | None
    output_prefs_json: str | None
    job_filters_json: str | None
    created_at: str
    updated_at: str
    last_run_at: str | None
    next_run_at: str | None
    wf_schedule_id: str | None = None


@dataclass
class RunRow:
    id: int
    job_id: int
    status: str
    started_at: str | None
    finished_at: str | None
    stats_json: str | None
    error_msg: str | None
    log_path: str | None


@dataclass
class ScrapedItemRow:
    id: int
    run_id: int
    job_id: int
    source_id: int
    media_id: int | None
    media_uuid: str | None
    url: str | None
    title: str | None
    summary: str | None
    published_at: str | None
    tags_json: str | None
    status: str
    reviewed: int
    created_at: str

    def tags(self) -> list[str]:
        if not self.tags_json:
            return []
        try:
            data = json.loads(self.tags_json)
            if isinstance(data, list):
                return [str(t) for t in data if isinstance(t, str)]
        except Exception:
            return []
        return []


class WatchlistsDatabase:
    # Keep track of schema initialization per DB path to avoid redundant ALTER checks/noise
    _schema_init_keys: set[str] = set()

    def __init__(self, user_id: int | str, backend: DatabaseBackend | None = None):
        self.user_id = str(user_id)
        db_key: str | None = None
        if backend is None:
            backend, db_key = self._resolve_backend()
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

    def _resolve_backend(self) -> tuple[DatabaseBackend, str | None]:
        backend_mode_env = (os.getenv("TLDW_CONTENT_DB_BACKEND") or "").strip().lower()
        if backend_mode_env in {"postgres", "postgresql"}:
            parser = load_comprehensive_config()
            resolved = get_content_backend(parser)
            if resolved is None:
                raise RuntimeError("PostgreSQL content backend requested but not initialized")
            return resolved, f"postgres:{resolved.config.connection_string or resolved.config.pg_database}"

        try:
            parser = load_comprehensive_config()
        except Exception:
            parser = None

        if parser is not None:
            try:
                content_settings = load_content_db_settings(parser)
                if content_settings.backend_type == BackendType.POSTGRESQL:
                    resolved = get_content_backend(parser)
                    if resolved is None:
                        raise RuntimeError("PostgreSQL content backend requested but not initialized")
                    return resolved, f"postgres:{resolved.config.connection_string or resolved.config.pg_database}"
            except Exception:
                pass

        db_path = str(DatabasePaths.get_media_db_path(int(self.user_id)))
        cfg = DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=db_path)
        return DatabaseBackendFactory.create_backend(cfg), f"sqlite:{db_path}"

    def _execute_insert(self, query: str, params: tuple[Any, ...]) -> Any:
        if self.backend.backend_type == BackendType.POSTGRESQL:
            prepared_query, prepared_params = prepare_backend_statement(
                BackendType.POSTGRESQL,
                query,
                params,
                apply_default_transform=True,
                ensure_returning=True,
            )
            return self.backend.execute(prepared_query, prepared_params)
        return self.backend.execute(query, params)

    @staticmethod
    def _extract_lastrowid(result: Any) -> int | None:
        try:
            if result is None:
                return None
            lastrowid = getattr(result, "lastrowid", None)
            if lastrowid:
                return int(lastrowid)
            first = getattr(result, "first", None)
            if isinstance(first, dict) and first.get("id") is not None:
                return int(first.get("id"))
        except Exception:
            return None
        return None

    def ensure_schema(self) -> None:
        if self.backend.backend_type == BackendType.POSTGRESQL:
            ddl = """
            CREATE TABLE IF NOT EXISTS sources (
                id BIGSERIAL PRIMARY KEY,
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
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                parent_group_id BIGINT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ux_groups_user_name ON groups(user_id, name);

            CREATE TABLE IF NOT EXISTS source_groups (
                source_id BIGINT NOT NULL,
                group_id BIGINT NOT NULL,
                UNIQUE (source_id, group_id)
            );

            CREATE TABLE IF NOT EXISTS tags (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                UNIQUE (user_id, name)
            );
            CREATE TABLE IF NOT EXISTS source_tags (
                source_id BIGINT NOT NULL,
                tag_id BIGINT NOT NULL,
                UNIQUE (source_id, tag_id)
            );

            CREATE TABLE IF NOT EXISTS scrape_jobs (
                id BIGSERIAL PRIMARY KEY,
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
                id BIGSERIAL PRIMARY KEY,
                job_id BIGINT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                stats_json TEXT,
                error_msg TEXT,
                log_path TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_runs_job ON scrape_runs(job_id);

            CREATE TABLE IF NOT EXISTS scrape_run_items (
                run_id BIGINT NOT NULL,
                media_id BIGINT NOT NULL,
                source_id BIGINT,
                UNIQUE (run_id, media_id)
            );

            CREATE TABLE IF NOT EXISTS source_seen_items (
                source_id BIGINT NOT NULL,
                item_key TEXT NOT NULL,
                etag TEXT,
                last_modified TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                UNIQUE (source_id, item_key)
            );

            CREATE TABLE IF NOT EXISTS scraped_items (
                id BIGSERIAL PRIMARY KEY,
                run_id BIGINT NOT NULL,
                job_id BIGINT NOT NULL,
                source_id BIGINT NOT NULL,
                media_id BIGINT,
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

            CREATE TABLE IF NOT EXISTS watchlist_clusters (
                job_id BIGINT NOT NULL,
                cluster_id BIGINT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (job_id, cluster_id)
            );
            CREATE INDEX IF NOT EXISTS idx_watchlist_clusters_job ON watchlist_clusters(job_id);
            CREATE INDEX IF NOT EXISTS idx_watchlist_clusters_cluster ON watchlist_clusters(cluster_id);
            """
        else:
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

            CREATE TABLE IF NOT EXISTS watchlist_clusters (
                job_id INTEGER NOT NULL,
                cluster_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (job_id, cluster_id)
            );
            CREATE INDEX IF NOT EXISTS idx_watchlist_clusters_job ON watchlist_clusters(job_id);
            CREATE INDEX IF NOT EXISTS idx_watchlist_clusters_cluster ON watchlist_clusters(cluster_id);
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
    # ------------------------
    # Tags helpers
    # ------------------------
    def _normalize_tag(self, name: str) -> str:
        return name.strip().lower()

    def ensure_tag_ids(self, names: list[str]) -> list[int]:
        normed = [self._normalize_tag(n) for n in names if n and n.strip()]
        ids: list[int] = []
        select_sql = "SELECT id FROM tags WHERE user_id = ? AND name = ?"
        insert_sql = "INSERT INTO tags (user_id, name) VALUES (?, ?)"
        for nm in normed:
            params = (self.user_id, nm)
            row = self.backend.execute(select_sql, params).first
            if row:
                ids.append(int(row.get("id")))
                continue
            insert_exc: Exception | None = None
            tag_id: int | None = None
            try:
                res = self._execute_insert(insert_sql, params)
                tag_id = self._extract_lastrowid(res)
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

    def _lookup_tag_ids(self, names: Iterable[str]) -> dict[str, int]:
        normed: list[str] = []
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
        out: dict[str, int] = {}
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

    def list_tags(self, q: str | None, limit: int, offset: int) -> tuple[list[TagRow], int]:
        where = ["user_id = ?"]
        params: list[Any] = [self.user_id]
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
        settings_json: str | None = None,
        tags: list[str] | None = None,
        group_ids: list[int] | None = None,
    ) -> SourceRow:
        now = _utcnow_iso()
        # Try insert; if UNIQUE(user_id,url) violates, fetch existing id and proceed idempotently
        sid: int | None = None
        try:
            res = self._execute_insert(
                "INSERT INTO sources (user_id, name, url, source_type, active, settings_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (self.user_id, name, url, source_type, 1 if active else 0, settings_json, now, now),
            )
            sid = self._extract_lastrowid(res)
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

    def list_sources(self, q: str | None, tag_names: list[str] | None, limit: int, offset: int) -> tuple[list[SourceRow], int]:
        where = ["user_id = ?"]
        params: list[Any] = [self.user_id]
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
        out: list[SourceRow] = []
        for r in rows:
            sid = int(r.get("id"))
            trows = self.backend.execute(
                "SELECT t.name FROM source_tags st JOIN tags t ON st.tag_id = t.id WHERE st.source_id = ?",
                (sid,),
            ).rows
            tags = [tr.get("name") for tr in trows if tr.get("name")]
            out.append(SourceRow(tags=tags, **r))  # type: ignore[arg-type]
        return out, total

    def update_source(self, source_id: int, patch: dict[str, Any]) -> SourceRow:
        if not patch:
            return self.get_source(source_id)
        fields = []
        params: list[Any] = []
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
        last_scraped_at: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
        defer_until: str | None = None,
        status: str | None = None,
        consec_not_modified: int | None = None,
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

    def set_source_tags(self, source_id: int, tag_names: list[str]) -> list[str]:
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

    def set_source_groups(self, source_id: int, group_ids: list[int]) -> list[int]:
        clean_ids: list[int] = []
        seen: set[int] = set()
        for gid in group_ids or []:
            try:
                val = int(gid)
            except Exception:
                continue
            if val in seen:
                continue
            seen.add(val)
            clean_ids.append(val)
        self.backend.execute("DELETE FROM source_groups WHERE source_id = ?", (source_id,))
        for gid in clean_ids:
            try:
                self.backend.execute(
                    "INSERT INTO source_groups (source_id, group_id) VALUES (?, ?) ON CONFLICT(source_id, group_id) DO NOTHING",
                    (source_id, gid),
                )
            except Exception:
                self.backend.execute(
                    "INSERT INTO source_groups (source_id, group_id) SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM source_groups WHERE source_id = ? AND group_id = ?)",
                    (source_id, gid, source_id, gid),
                )
        return clean_ids

    def delete_source(self, source_id: int) -> bool:
        res = self.backend.execute("DELETE FROM sources WHERE id = ? AND user_id = ?", (source_id, self.user_id))
        return res.rowcount > 0

    def list_sources_by_group_ids(self, group_ids: list[int], *, active_only: bool = True) -> list[SourceRow]:
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
        out: list[SourceRow] = []
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
    def create_group(self, name: str, description: str | None, parent_group_id: int | None) -> GroupRow:
        # Idempotent by (user_id, name)
        try:
            res = self._execute_insert(
                "INSERT INTO groups (user_id, name, description, parent_group_id) VALUES (?, ?, ?, ?)",
                (self.user_id, name, description, parent_group_id),
            )
            new_id = self._extract_lastrowid(res)
            if not new_id:
                raise RuntimeError("failed_to_create_group")
            return self.get_group(new_id)
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

    def list_groups(self, q: str | None, limit: int, offset: int) -> tuple[list[GroupRow], int]:
        where = ["user_id = ?"]
        params: list[Any] = [self.user_id]
        if q:
            where.append("name LIKE ?")
            params.append(f"%{q}%")
        total = int(self.backend.execute(f"SELECT COUNT(*) AS cnt FROM groups WHERE {' AND '.join(where)}", tuple(params)).scalar or 0)
        rows = self.backend.execute(
            f"SELECT id, user_id, name, description, parent_group_id FROM groups WHERE {' AND '.join(where)} ORDER BY name LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        ).rows
        return [GroupRow(**r) for r in rows], total

    def update_group(self, group_id: int, patch: dict[str, Any]) -> GroupRow:
        fields = []
        params: list[Any] = []
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
        description: str | None,
        scope_json: str | None,
        schedule_expr: str | None,
        schedule_timezone: str | None,
        active: bool,
        max_concurrency: int | None,
        per_host_delay_ms: int | None,
        retry_policy_json: str | None,
        output_prefs_json: str | None,
        job_filters_json: str | None = None,
    ) -> JobRow:
        now = _utcnow_iso()
        res = self._execute_insert(
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
        new_id = self._extract_lastrowid(res)
        if not new_id:
            raise RuntimeError("failed_to_create_job")
        return self.get_job(new_id)

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

    def list_jobs(self, q: str | None, limit: int, offset: int) -> tuple[list[JobRow], int]:
        where = ["user_id = ?"]
        params: list[Any] = [self.user_id]
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

    def set_job_filters(self, job_id: int, filters: Any | None) -> JobRow:
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

    def get_job_filters(self, job_id: int) -> dict[str, Any]:
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

    def update_job(self, job_id: int, patch: dict[str, Any]) -> JobRow:
        if not patch:
            return self.get_job(job_id)
        fields = []
        params: list[Any] = []
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
    def set_job_schedule_id(self, job_id: int, schedule_id: str | None) -> None:
        self.backend.execute(
            "UPDATE scrape_jobs SET wf_schedule_id = ? WHERE id = ? AND user_id = ?",
            (schedule_id, job_id, self.user_id),
        )

    def set_job_history(self, job_id: int, *, last_run_at: str | None = None, next_run_at: str | None = None) -> None:
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
        res = self._execute_insert(
            "INSERT INTO scrape_runs (job_id, status, started_at) VALUES (?, ?, ?)",
            (job_id, status, _utcnow_iso()),
        )
        new_id = self._extract_lastrowid(res)
        if not new_id:
            raise RuntimeError("failed_to_create_run")
        return self.get_run(new_id)

    def get_run(self, run_id: int) -> RunRow:
        row = self.backend.execute(
            "SELECT id, job_id, status, started_at, finished_at, stats_json, error_msg, log_path FROM scrape_runs WHERE id = ?",
            (run_id,),
        ).first
        if not row:
            raise KeyError("run_not_found")
        return RunRow(**row)

    def list_runs_for_job(self, job_id: int, limit: int, offset: int) -> tuple[list[RunRow], int]:
        total = int(self.backend.execute("SELECT COUNT(*) AS cnt FROM scrape_runs WHERE job_id = ?", (job_id,)).scalar or 0)
        rows = self.backend.execute(
            "SELECT id, job_id, status, started_at, finished_at, stats_json, error_msg, log_path FROM scrape_runs WHERE job_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (job_id, limit, offset),
        ).rows
        return [RunRow(**r) for r in rows], total

    def list_runs(self, q: str | None, limit: int, offset: int) -> tuple[list[RunRow], int]:
        """List runs across all jobs for this user.

        Optional q filters by job name/description, run status, or run id (text match).
        """
        where = ["j.user_id = ?"]
        params: list[Any] = [self.user_id]
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

    def append_run_item(self, run_id: int, media_id: int, source_id: int | None = None) -> None:
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

    def list_run_media_ids(self, run_id: int, limit: int = 1000) -> list[int]:
        rows = self.backend.execute(
            "SELECT media_id FROM scrape_run_items WHERE run_id = ? ORDER BY media_id LIMIT ?",
            (run_id, limit),
        ).rows
        mids: list[int] = []
        for r in rows:
            v = r.get("media_id")
            try:
                mids.append(int(v))
            except Exception:
                continue
        return mids

    # ------------------------
    # Scraped items
    # ------------------------
    def record_scraped_item(
        self,
        *,
        run_id: int,
        job_id: int,
        source_id: int,
        media_id: int | None,
        media_uuid: str | None,
        url: str | None,
        title: str | None,
        summary: str | None,
        published_at: str | None,
        tags: list[str] | None,
        status: str,
    ) -> ScrapedItemRow:
        created_at = _utcnow_iso()
        tags_json = json.dumps(tags or [])
        res = self._execute_insert(
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
        new_id = self._extract_lastrowid(res)
        if not new_id:
            raise RuntimeError("failed_to_record_scraped_item")
        return self.get_item(new_id)

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
        run_id: int | None = None,
        job_id: int | None = None,
        source_id: int | None = None,
        status: str | None = None,
        reviewed: bool | None = None,
        search: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ScrapedItemRow], int]:
        where = ["1=1"]
        params: list[Any] = []
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

    def get_items_by_ids(self, item_ids: list[int]) -> list[ScrapedItemRow]:
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
        reviewed: bool | None = None,
        status: str | None = None,
    ) -> ScrapedItemRow:
        fields: list[str] = []
        params: list[Any] = []
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

    def update_run(
        self,
        run_id: int,
        *,
        status: str | None = None,
        finished_at: str | None = None,
        stats_json: str | None = None,
        error_msg: str | None = None,
        log_path: str | None = None,
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
        etag: str | None = None,
        last_modified: str | None = None,
        seen_at: str | None = None,
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

    def list_seen_item_keys(self, source_id: int, *, limit: int | None = None) -> list[str]:
        sql = "SELECT item_key FROM source_seen_items WHERE source_id = ? ORDER BY last_seen_at DESC"
        params: tuple[Any, ...] = (source_id,)
        if isinstance(limit, int) and limit > 0:
            sql = sql + " LIMIT ?"
            params = (source_id, limit)
        rows = self.backend.execute(sql, params).rows
        keys: list[str] = []
        for r in rows:
            k = r.get("item_key")
            if isinstance(k, str) and k:
                keys.append(k)
        return keys

    # ------------------------
    # Claim cluster subscriptions
    # ------------------------
    def add_watchlist_cluster(self, job_id: int, cluster_id: int) -> None:
        ts = _utcnow_iso()
        self.backend.execute(
            "INSERT INTO watchlist_clusters (job_id, cluster_id, created_at) "
            "VALUES (?, ?, ?) ON CONFLICT(job_id, cluster_id) DO NOTHING",
            (int(job_id), int(cluster_id), ts),
        )

    def remove_watchlist_cluster(self, job_id: int, cluster_id: int) -> bool:
        result = self.backend.execute(
            "DELETE FROM watchlist_clusters WHERE job_id = ? AND cluster_id = ?",
            (int(job_id), int(cluster_id)),
        )
        try:
            return int(getattr(result, "rowcount", 0) or 0) > 0
        except Exception:
            return False

    def list_watchlist_clusters(self, job_id: int) -> list[dict[str, Any]]:
        rows = self.backend.execute(
            "SELECT cluster_id, created_at FROM watchlist_clusters WHERE job_id = ? "
            "ORDER BY created_at DESC",
            (int(job_id),),
        ).rows
        return [dict(r) for r in rows or []]

    def list_watchlist_cluster_subscriptions(
        self,
        *,
        cluster_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT job_id, cluster_id, created_at FROM watchlist_clusters"
        params: list[Any] = []
        if cluster_ids:
            placeholders = ",".join("?" * len(cluster_ids))
            sql += f" WHERE cluster_id IN ({placeholders})"
            params.extend(int(cid) for cid in cluster_ids)
        sql += " ORDER BY created_at DESC"
        rows = self.backend.execute(sql, tuple(params)).rows
        return [dict(r) for r in rows or []]

    def list_watchlist_cluster_counts(
        self,
        *,
        cluster_ids: list[int] | None = None,
    ) -> dict[int, int]:
        sql = "SELECT cluster_id, COUNT(*) AS cnt FROM watchlist_clusters"
        params: list[Any] = []
        if cluster_ids:
            placeholders = ",".join("?" * len(cluster_ids))
            sql += f" WHERE cluster_id IN ({placeholders})"
            params.extend(int(cid) for cid in cluster_ids)
        sql += " GROUP BY cluster_id"
        rows = self.backend.execute(sql, tuple(params)).rows
        counts: dict[int, int] = {}
        for row in rows or []:
            try:
                cluster_id = int(row.get("cluster_id"))
                counts[cluster_id] = int(row.get("cnt") or 0)
            except Exception:
                continue
        return counts
