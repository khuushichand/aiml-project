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
- scrape_run_items(run_id, media_id)

Notes:
- Backed by DatabaseBackendFactory; default to per-user SQLite Media DB path.
- Provides minimal CRUD required by the API layer; scraping is implemented elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
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


class WatchlistsDatabase:
    def __init__(self, user_id: int | str, backend: Optional[DatabaseBackend] = None):
        self.user_id = str(user_id)
        if backend is None:
            db_path = str(DatabasePaths.get_media_db_path(int(user_id)))
            cfg = DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=db_path)
            backend = DatabaseBackendFactory.create_backend(cfg)
        self.backend = backend
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
        """
        self.backend.create_tables(ddl)
        # Backfill columns in case table existed
        try:
            self.backend.execute("ALTER TABLE scrape_jobs ADD COLUMN wf_schedule_id TEXT", tuple())
        except Exception:
            pass
        try:
            self.backend.execute("ALTER TABLE sources ADD COLUMN defer_until TEXT", tuple())
        except Exception:
            pass
        try:
            self.backend.execute("ALTER TABLE sources ADD COLUMN consec_not_modified INTEGER DEFAULT 0", tuple())
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
        for nm in normed:
            row = self.backend.execute(
                "SELECT id FROM tags WHERE user_id = ? AND name = ?",
                (self.user_id, nm),
            ).first
            if row:
                ids.append(int(row.get("id")))
                continue
            res = self.backend.execute(
                "INSERT INTO tags (user_id, name) VALUES (?, ?)",
                (self.user_id, nm),
            )
            ids.append(int(res.lastrowid or 0))
        return ids

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
                    self.backend.execute("INSERT OR IGNORE INTO source_tags (source_id, tag_id) VALUES (?, ?)", (sid, tid))
                except Exception:
                    pass
        if group_ids:
            for gid in group_ids:
                try:
                    self.backend.execute("INSERT OR IGNORE INTO source_groups (source_id, group_id) VALUES (?, ?)", (sid, gid))
                except Exception:
                    pass
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
            tag_ids = self.ensure_tag_ids(tag_names)
            for tid in tag_ids:
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
                self.backend.execute("INSERT OR IGNORE INTO source_tags (source_id, tag_id) VALUES (?, ?)", (source_id, tid))
            except Exception:
                pass
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
                   s.last_scraped_at, s.etag, s.last_modified, s.defer_until, s.status, s.created_at, s.updated_at
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
    ) -> JobRow:
        now = _utcnow_iso()
        res = self.backend.execute(
            """
            INSERT INTO scrape_jobs (user_id, name, description, scope_json, schedule_expr, active, max_concurrency,
            per_host_delay_ms, retry_policy_json, output_prefs_json, schedule_timezone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                   max_concurrency, per_host_delay_ms, retry_policy_json, output_prefs_json,
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
            f"SELECT id, user_id, name, description, scope_json, schedule_expr, schedule_timezone, active, max_concurrency, per_host_delay_ms, retry_policy_json, output_prefs_json, created_at, updated_at, last_run_at, next_run_at, wf_schedule_id FROM scrape_jobs WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        ).rows
        return [JobRow(**r) for r in rows], total

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

    def append_run_item(self, run_id: int, media_id: int) -> None:
        try:
            self.backend.execute("INSERT OR IGNORE INTO scrape_run_items (run_id, media_id) VALUES (?, ?)", (run_id, media_id))
        except Exception:
            pass

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
