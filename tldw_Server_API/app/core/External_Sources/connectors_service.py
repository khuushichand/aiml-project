from __future__ import annotations

import contextlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.External_Sources.gmail import GmailConnector
from tldw_Server_API.app.core.External_Sources.google_drive import GoogleDriveConnector
from tldw_Server_API.app.core.External_Sources.notion import NotionConnector
from tldw_Server_API.app.core.External_Sources.onedrive import OneDriveConnector
from tldw_Server_API.app.core.External_Sources.sync_adapter import FileSyncAdapter

_CONNECTORS_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    EOFError,
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
)

FILE_SYNC_PROVIDERS = frozenset({"drive", "onedrive"})
_SYNC_STATE_FIELDS = (
    "sync_mode",
    "cursor",
    "cursor_kind",
    "last_bootstrap_at",
    "last_sync_started_at",
    "last_sync_succeeded_at",
    "last_sync_failed_at",
    "last_error",
    "retry_backoff_count",
    "webhook_status",
    "webhook_subscription_id",
    "webhook_expires_at",
    "needs_full_rescan",
    "active_job_id",
    "active_job_started_at",
)
_EXTERNAL_ITEM_BINDING_FIELDS = (
    "name",
    "mime",
    "size",
    "modified_at",
    "version",
    "hash",
    "media_id",
    "sync_status",
    "current_version_number",
    "remote_parent_id",
    "remote_path",
    "last_seen_at",
    "last_content_sync_at",
    "last_metadata_sync_at",
    "remote_deleted_at",
    "access_revoked_at",
    "provider_metadata",
)


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return False


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    keys = getattr(row, "keys", None)
    if callable(keys):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
        return default


def _normalize_sync_state_row(row: Any) -> dict[str, Any] | None:
    if not row:
        return None
    data = _row_to_dict(row)
    data["needs_full_rescan"] = _normalize_bool(data.get("needs_full_rescan"))
    return data


def _normalize_external_item_row(row: Any) -> dict[str, Any] | None:
    if not row:
        return None
    data = _row_to_dict(row)
    if "provider_metadata" in data:
        data["provider_metadata"] = _json_loads(data.get("provider_metadata"), {})
    if "sync_status" not in data or data.get("sync_status") is None:
        data["sync_status"] = "active"
    return data


async def _sqlite_column_names(db, table_name: str) -> set[str]:
    cur = await db.execute(f"PRAGMA table_info({table_name})")
    rows = await cur.fetchall()
    names: set[str] = set()
    for row in rows:
        if hasattr(row, "keys"):
            names.add(str(row["name"]))
        else:
            names.add(str(row[1]))
    return names


async def _ensure_sqlite_column(db, table_name: str, column_name: str, column_sql: str) -> None:
    if column_name in await _sqlite_column_names(db, table_name):
        return
    await db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


async def _mark_sources_needing_rescan(db, *, is_pg: bool) -> None:
    if is_pg:
        await db.execute(
            """
            INSERT INTO external_source_sync_state (
                source_id,
                sync_mode,
                needs_full_rescan
            )
            SELECT DISTINCT source_id, 'manual', TRUE
            FROM external_items
            WHERE media_id IS NULL
            ON CONFLICT (source_id) DO UPDATE SET
                needs_full_rescan = TRUE
            """
        )
        return
    await db.execute(
        """
        INSERT OR IGNORE INTO external_source_sync_state (
            source_id,
            sync_mode,
            needs_full_rescan
        )
        SELECT DISTINCT source_id, 'manual', 1
        FROM external_items
        WHERE media_id IS NULL
        """
    )
    await db.execute(
        """
        UPDATE external_source_sync_state
        SET needs_full_rescan = 1
        WHERE source_id IN (
            SELECT DISTINCT source_id
            FROM external_items
            WHERE media_id IS NULL
        )
        """
    )


def _is_db_pool_object(db: Any) -> bool:
    return isinstance(db, DatabasePool)


def _is_postgres_connection(db: Any) -> bool:
    """Resolve backend mode from connection/adapter shape without global probes."""
    if _is_db_pool_object(db):
        return getattr(db, "pool", None) is not None

    sqlite_hint = getattr(db, "_is_sqlite", None)
    if isinstance(sqlite_hint, bool):
        return not sqlite_hint

    if getattr(db, "_c", None) is not None:
        return False

    module_name = getattr(type(db), "__module__", "")
    if isinstance(module_name, str) and module_name.startswith("asyncpg"):
        return True

    return callable(getattr(db, "fetchrow", None))


def get_connector_by_name(name: str):
    n = name.lower()
    if n == "drive":
        return GoogleDriveConnector()
    if n == "onedrive":
        return OneDriveConnector()
    if n == "notion":
        return NotionConnector()
    if n == "gmail":
        return GmailConnector()
    raise ValueError(f"Unknown connector provider: {name}")


def get_file_sync_connector_by_name(name: str) -> FileSyncAdapter:
    normalized = name.lower()
    if normalized not in FILE_SYNC_PROVIDERS:
        raise ValueError(f"Connector provider does not support file sync: {name}")
    connector = get_connector_by_name(normalized)
    if not isinstance(connector, FileSyncAdapter):  # pragma: no cover - defensive guard
        raise TypeError(f"Connector provider does not implement the file sync adapter contract: {name}")
    return connector


async def _ensure_tables(db) -> None:
    """Create connector tables if they don't exist in the AuthNZ DB."""
    is_pg = _is_postgres_connection(db)
    try:
        if is_pg:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_accounts (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    display_name TEXT,
                    email TEXT,
                    access_token TEXT,  -- may store encrypted envelope JSON
                    refresh_token TEXT,
                    token_expires_at TIMESTAMP NULL,
                    scopes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_sources (
                    id SERIAL PRIMARY KEY,
                    account_id INTEGER NOT NULL REFERENCES external_accounts(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    remote_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    path TEXT,
                    options JSONB,
                    enabled BOOLEAN DEFAULT TRUE,
                    last_synced_at TIMESTAMP NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_items (
                    id SERIAL PRIMARY KEY,
                    source_id INTEGER NOT NULL REFERENCES external_sources(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    name TEXT,
                    mime TEXT,
                    size BIGINT,
                    modified_at TIMESTAMP NULL,
                    version TEXT,
                    hash TEXT,
                    last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_id, provider, external_id)
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS org_connector_policy (
                    org_id INTEGER PRIMARY KEY,
                    enabled_providers TEXT,
                    allowed_export_formats TEXT,
                    allowed_file_types TEXT,
                    max_file_size_mb INTEGER,
                    account_linking_role TEXT,
                    allowed_account_domains TEXT,
                    allowed_remote_paths TEXT,
                    denied_remote_paths TEXT,
                    allowed_notion_workspaces TEXT,
                    denied_notion_workspaces TEXT,
                    quotas_per_role JSONB,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_oauth_state (
                    state TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (state, user_id)
                )
                """
            )
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS media_id INTEGER")
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS sync_status TEXT")
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS current_version_number INTEGER")
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS remote_parent_id TEXT")
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS remote_path TEXT")
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP NULL")
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS last_content_sync_at TIMESTAMP NULL")
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS last_metadata_sync_at TIMESTAMP NULL")
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS remote_deleted_at TIMESTAMP NULL")
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS access_revoked_at TIMESTAMP NULL")
            await db.execute("ALTER TABLE external_items ADD COLUMN IF NOT EXISTS provider_metadata JSONB")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_source_sync_state (
                    source_id INTEGER PRIMARY KEY REFERENCES external_sources(id) ON DELETE CASCADE,
                    sync_mode TEXT NOT NULL DEFAULT 'manual',
                    cursor TEXT,
                    cursor_kind TEXT,
                    last_bootstrap_at TIMESTAMP NULL,
                    last_sync_started_at TIMESTAMP NULL,
                    last_sync_succeeded_at TIMESTAMP NULL,
                    last_sync_failed_at TIMESTAMP NULL,
                    last_error TEXT,
                    retry_backoff_count INTEGER DEFAULT 0,
                    webhook_status TEXT,
                    webhook_subscription_id TEXT,
                    webhook_expires_at TIMESTAMP NULL,
                    needs_full_rescan BOOLEAN DEFAULT FALSE,
                    active_job_id TEXT,
                    active_job_started_at TIMESTAMP NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_item_events (
                    id SERIAL PRIMARY KEY,
                    external_item_id INTEGER NOT NULL REFERENCES external_items(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    job_id TEXT,
                    payload_json JSONB,
                    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        else:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    display_name TEXT,
                    email TEXT,
                    access_token TEXT,
                    refresh_token TEXT,
                    token_expires_at TEXT,
                    scopes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """,
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    remote_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    path TEXT,
                    options TEXT,
                    enabled INTEGER DEFAULT 1,
                    last_synced_at TEXT
                )
                """,
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    name TEXT,
                    mime TEXT,
                    size INTEGER,
                    modified_at TEXT,
                    version TEXT,
                    hash TEXT,
                    last_ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_id, provider, external_id)
                )
                """,
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS org_connector_policy (
                    org_id INTEGER PRIMARY KEY,
                    enabled_providers TEXT,
                    allowed_export_formats TEXT,
                    allowed_file_types TEXT,
                    max_file_size_mb INTEGER,
                    account_linking_role TEXT,
                    allowed_account_domains TEXT,
                    allowed_remote_paths TEXT,
                    denied_remote_paths TEXT,
                    allowed_notion_workspaces TEXT,
                    denied_notion_workspaces TEXT,
                    quotas_per_role TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """,
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_oauth_state (
                    state TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (state, user_id)
                )
                """,
            )
            await _ensure_sqlite_column(db, "external_items", "media_id", "media_id INTEGER")
            await _ensure_sqlite_column(db, "external_items", "sync_status", "sync_status TEXT")
            await _ensure_sqlite_column(db, "external_items", "current_version_number", "current_version_number INTEGER")
            await _ensure_sqlite_column(db, "external_items", "remote_parent_id", "remote_parent_id TEXT")
            await _ensure_sqlite_column(db, "external_items", "remote_path", "remote_path TEXT")
            await _ensure_sqlite_column(db, "external_items", "last_seen_at", "last_seen_at TEXT")
            await _ensure_sqlite_column(db, "external_items", "last_content_sync_at", "last_content_sync_at TEXT")
            await _ensure_sqlite_column(db, "external_items", "last_metadata_sync_at", "last_metadata_sync_at TEXT")
            await _ensure_sqlite_column(db, "external_items", "remote_deleted_at", "remote_deleted_at TEXT")
            await _ensure_sqlite_column(db, "external_items", "access_revoked_at", "access_revoked_at TEXT")
            await _ensure_sqlite_column(db, "external_items", "provider_metadata", "provider_metadata TEXT")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_source_sync_state (
                    source_id INTEGER PRIMARY KEY,
                    sync_mode TEXT NOT NULL DEFAULT 'manual',
                    cursor TEXT,
                    cursor_kind TEXT,
                    last_bootstrap_at TEXT,
                    last_sync_started_at TEXT,
                    last_sync_succeeded_at TEXT,
                    last_sync_failed_at TEXT,
                    last_error TEXT,
                    retry_backoff_count INTEGER DEFAULT 0,
                    webhook_status TEXT,
                    webhook_subscription_id TEXT,
                    webhook_expires_at TEXT,
                    needs_full_rescan INTEGER DEFAULT 0,
                    active_job_id TEXT,
                    active_job_started_at TEXT
                )
                """,
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS external_item_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_item_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    job_id TEXT,
                    payload_json TEXT,
                    occurred_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """,
            )
            await getattr(db, "commit", lambda: None)()
        await _mark_sources_needing_rescan(db, is_pg=is_pg)
        if not is_pg:
            await getattr(db, "commit", lambda: None)()
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Failed to ensure connector tables: {e}")
        raise


async def upsert_policy(db, org_id: int, policy: dict[str, Any]) -> dict[str, Any]:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    fields = [
        "enabled_providers",
        "allowed_export_formats",
        "allowed_file_types",
        "max_file_size_mb",
        "account_linking_role",
        "allowed_account_domains",
        "allowed_remote_paths",
        "denied_remote_paths",
        "allowed_notion_workspaces",
        "denied_notion_workspaces",
        "quotas_per_role",
    ]
    data = {k: policy.get(k) for k in fields}
    if is_pg:
        await db.execute(
            """
            INSERT INTO org_connector_policy (
                org_id, enabled_providers, allowed_export_formats, allowed_file_types,
                max_file_size_mb, account_linking_role, allowed_account_domains,
                allowed_remote_paths, denied_remote_paths, allowed_notion_workspaces,
                denied_notion_workspaces, quotas_per_role
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (org_id) DO UPDATE SET
                enabled_providers = EXCLUDED.enabled_providers,
                allowed_export_formats = EXCLUDED.allowed_export_formats,
                allowed_file_types = EXCLUDED.allowed_file_types,
                max_file_size_mb = EXCLUDED.max_file_size_mb,
                account_linking_role = EXCLUDED.account_linking_role,
                allowed_account_domains = EXCLUDED.allowed_account_domains,
                allowed_remote_paths = EXCLUDED.allowed_remote_paths,
                denied_remote_paths = EXCLUDED.denied_remote_paths,
                allowed_notion_workspaces = EXCLUDED.allowed_notion_workspaces,
                denied_notion_workspaces = EXCLUDED.denied_notion_workspaces,
                quotas_per_role = EXCLUDED.quotas_per_role,
                updated_at = CURRENT_TIMESTAMP
            """,
            org_id,
            ",".join(data.get("enabled_providers") or []),
            ",".join(data.get("allowed_export_formats") or []),
            ",".join(data.get("allowed_file_types") or []),
            int(data.get("max_file_size_mb") or 0),
            data.get("account_linking_role"),
            ",".join(data.get("allowed_account_domains") or []),
            ",".join(data.get("allowed_remote_paths") or []),
            ",".join(data.get("denied_remote_paths") or []),
            ",".join(data.get("allowed_notion_workspaces") or []),
            ",".join(data.get("denied_notion_workspaces") or []),
            (data.get("quotas_per_role") or {}),
        )
    else:
        await db.execute(
            """
            INSERT OR REPLACE INTO org_connector_policy (
                org_id, enabled_providers, allowed_export_formats, allowed_file_types,
                max_file_size_mb, account_linking_role, allowed_account_domains,
                allowed_remote_paths, denied_remote_paths, allowed_notion_workspaces,
                denied_notion_workspaces, quotas_per_role, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                org_id,
                ",".join(data.get("enabled_providers") or []),
                ",".join(data.get("allowed_export_formats") or []),
                ",".join(data.get("allowed_file_types") or []),
                int(data.get("max_file_size_mb") or 0),
                data.get("account_linking_role"),
                ",".join(data.get("allowed_account_domains") or []),
                ",".join(data.get("allowed_remote_paths") or []),
                ",".join(data.get("denied_remote_paths") or []),
                ",".join(data.get("allowed_notion_workspaces") or []),
                ",".join(data.get("denied_notion_workspaces") or []),
                __import__("json").dumps(data.get("quotas_per_role") or {}),
            ),
        )
    return await get_policy(db, org_id)


async def get_policy(db, org_id: int) -> dict[str, Any]:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        row = await db.fetchrow("SELECT * FROM org_connector_policy WHERE org_id = $1", org_id)
        if not row:
            return {}
        row = dict(row)
        row["enabled_providers"] = (row.get("enabled_providers") or "").split(",") if row.get("enabled_providers") else []
        row["allowed_export_formats"] = (row.get("allowed_export_formats") or "").split(",") if row.get("allowed_export_formats") else []
        row["allowed_file_types"] = (row.get("allowed_file_types") or "").split(",") if row.get("allowed_file_types") else []
        row["allowed_account_domains"] = (row.get("allowed_account_domains") or "").split(",") if row.get("allowed_account_domains") else []
        row["allowed_remote_paths"] = (row.get("allowed_remote_paths") or "").split(",") if row.get("allowed_remote_paths") else []
        row["denied_remote_paths"] = (row.get("denied_remote_paths") or "").split(",") if row.get("denied_remote_paths") else []
        row["allowed_notion_workspaces"] = (row.get("allowed_notion_workspaces") or "").split(",") if row.get("allowed_notion_workspaces") else []
        row["denied_notion_workspaces"] = (row.get("denied_notion_workspaces") or "").split(",") if row.get("denied_notion_workspaces") else []
        return row
    cur = await db.execute("SELECT * FROM org_connector_policy WHERE org_id = ?", (org_id,))
    r = await cur.fetchone()
    if not r:
        return {}
    try:
        keys = [c[0] for c in getattr(cur, "description", [])]  # aiosqlite cursor
        row = {k: r[i] for i, k in enumerate(keys)}
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
        # Fallback assuming sqlite Row-like access
        row = dict(r)
    row["enabled_providers"] = (row.get("enabled_providers") or "").split(",") if row.get("enabled_providers") else []
    row["allowed_export_formats"] = (row.get("allowed_export_formats") or "").split(",") if row.get("allowed_export_formats") else []
    row["allowed_file_types"] = (row.get("allowed_file_types") or "").split(",") if row.get("allowed_file_types") else []
    row["allowed_account_domains"] = (row.get("allowed_account_domains") or "").split(",") if row.get("allowed_account_domains") else []
    row["allowed_remote_paths"] = (row.get("allowed_remote_paths") or "").split(",") if row.get("allowed_remote_paths") else []
    row["denied_remote_paths"] = (row.get("denied_remote_paths") or "").split(",") if row.get("denied_remote_paths") else []
    row["allowed_notion_workspaces"] = (row.get("allowed_notion_workspaces") or "").split(",") if row.get("allowed_notion_workspaces") else []
    row["denied_notion_workspaces"] = (row.get("denied_notion_workspaces") or "").split(",") if row.get("denied_notion_workspaces") else []
    # quotas_per_role as JSON string
    try:
        row["quotas_per_role"] = __import__("json").loads(row.get("quotas_per_role") or "{}")
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
        row["quotas_per_role"] = {}
    return row


def _oauth_state_cutoff(max_age_minutes: int) -> tuple[datetime, str]:
    cutoff_dt = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    return cutoff_dt, cutoff_str


async def create_oauth_state(db, user_id: int, provider: str, state: str) -> None:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        await db.execute(
            """
            INSERT INTO external_oauth_state (state, user_id, provider, created_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (state, user_id) DO UPDATE SET
                provider = EXCLUDED.provider,
                created_at = CURRENT_TIMESTAMP
            """,
            state, user_id, provider,
        )
        return
    await db.execute(
        """
        INSERT OR REPLACE INTO external_oauth_state (state, user_id, provider, created_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (state, user_id, provider),
    )
    await getattr(db, "commit", lambda: None)()


async def consume_oauth_state(
    db,
    *,
    user_id: int,
    provider: str,
    state: str,
    max_age_minutes: int = 10,
) -> bool:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    cutoff_dt, cutoff_str = _oauth_state_cutoff(max_age_minutes)
    if is_pg:
        row = await db.fetchrow(
            """
            SELECT state FROM external_oauth_state
            WHERE state = $1 AND user_id = $2 AND provider = $3 AND created_at >= $4
            """,
            state, user_id, provider, cutoff_dt,
        )
        if not row:
            return False
        await db.execute(
            "DELETE FROM external_oauth_state WHERE state = $1 AND user_id = $2",
            state, user_id,
        )
        return True
    cur = await db.execute(
        """
        SELECT state FROM external_oauth_state
        WHERE state = ? AND user_id = ? AND provider = ? AND created_at >= ?
        """,
        (state, user_id, provider, cutoff_str),
    )
    row = await cur.fetchone()
    if not row:
        return False
    await db.execute(
        "DELETE FROM external_oauth_state WHERE state = ? AND user_id = ?",
        (state, user_id),
    )
    await getattr(db, "commit", lambda: None)()
    return True


async def create_account(db, user_id: int, provider: str, display_name: str, email: str | None, tokens: dict[str, Any]) -> dict[str, Any]:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    # Securely envelope tokens if crypto is configured; fallback to storing access token raw
    import json as _json
    try:
        from tldw_Server_API.app.core.Security.crypto import encrypt_json_blob
        env = encrypt_json_blob({
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "token_type": tokens.get("token_type"),
            "expires_in": tokens.get("expires_in"),
            "expires_at": tokens.get("expires_at"),
            "scope": tokens.get("scope"),
        })
        access_token_store = _json.dumps(env) if env else str(tokens.get("access_token") or "")
        refresh_token_store = None  # envelope contains refresh
        tokens.get("scope") or None
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
        access_token_store = str(tokens.get("access_token") or "")
        refresh_token_store = tokens.get("refresh_token")
        tokens.get("scope") or None

    if is_pg:
        row = await db.fetchrow(
            """
            INSERT INTO external_accounts (user_id, provider, display_name, email, access_token, refresh_token, token_expires_at, scopes)
            VALUES ($1, $2, $3, $4, $5, $6, NULL, NULL)
            RETURNING id, user_id, provider, display_name, email, created_at
            """,
            user_id, provider, display_name, email, access_token_store, refresh_token_store
        )
        return dict(row)
    cur = await db.execute(
        """
        INSERT INTO external_accounts (user_id, provider, display_name, email, access_token, refresh_token, token_expires_at, scopes)
        VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        (user_id, provider, display_name, email, access_token_store, refresh_token_store),
    )
    await getattr(db, "commit", lambda: None)()
    rid = cur.lastrowid
    cur2 = await db.execute("SELECT id, user_id, provider, display_name, email, created_at FROM external_accounts WHERE id = ?", (rid,))
    r = await cur2.fetchone()
    try:
        return {"id": r[0], "user_id": r[1], "provider": r[2], "display_name": r[3], "email": r[4], "created_at": r[5]}
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
        return dict(r)


async def _get_account_with_tokens(db, user_id: int, account_id: int) -> dict[str, Any] | None:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        row = await db.fetchrow("SELECT id, user_id, provider, display_name, email, access_token, refresh_token FROM external_accounts WHERE id = $1 AND user_id = $2", account_id, user_id)
        if not row:
            return None
        d = dict(row)
    else:
        cur = await db.execute("SELECT id, user_id, provider, display_name, email, access_token, refresh_token FROM external_accounts WHERE id = ? AND user_id = ?", (account_id, user_id))
        r = await cur.fetchone()
        if not r:
            return None
        try:
            d = {"id": r[0], "user_id": r[1], "provider": r[2], "display_name": r[3], "email": r[4], "access_token": r[5], "refresh_token": r[6]}
        except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
            d = dict(r)
    # Decrypt envelope if present
    tokens: dict[str, Any] = {}
    import json as _json
    at_raw = d.get("access_token")
    if at_raw and isinstance(at_raw, str) and at_raw.strip().startswith("{"):
        try:
            from tldw_Server_API.app.core.Security.crypto import decrypt_json_blob
            env = _json.loads(at_raw)
            dec = decrypt_json_blob(env) or {}
            tokens.update(dec)
        except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
            pass
    if not tokens.get("access_token") and isinstance(at_raw, str):
        tokens["access_token"] = at_raw
    if not tokens.get("refresh_token") and d.get("refresh_token"):
        tokens["refresh_token"] = d.get("refresh_token")
    d["tokens"] = tokens
    return d


async def get_account_tokens(db, user_id: int, account_id: int) -> dict[str, Any] | None:
    row = await _get_account_with_tokens(db, user_id, account_id)
    if not row:
        return None
    return row.get("tokens") or {}


async def get_account_email(db, user_id: int, account_id: int) -> str | None:
    row = await _get_account_with_tokens(db, user_id, account_id)
    return None if not row else (row.get("email") or None)


async def get_account_for_user(db, user_id: int, account_id: int) -> dict[str, Any] | None:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        row = await db.fetchrow(
            """
            SELECT id, user_id, provider, display_name, email, created_at
            FROM external_accounts
            WHERE id = $1 AND user_id = $2
            """,
            account_id, user_id,
        )
        return dict(row) if row else None
    cur = await db.execute(
        """
        SELECT id, user_id, provider, display_name, email, created_at
        FROM external_accounts
        WHERE id = ? AND user_id = ?
        """,
        (account_id, user_id),
    )
    r = await cur.fetchone()
    if not r:
        return None
    try:
        return {
            "id": r[0],
            "user_id": r[1],
            "provider": r[2],
            "display_name": r[3],
            "email": r[4],
            "created_at": r[5],
        }
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
        return dict(r)


async def update_account_tokens(db, user_id: int, account_id: int, new_tokens: dict[str, Any]) -> bool:
    """Persist refreshed tokens for an account. Uses envelope encryption when configured.

    new_tokens may include: access_token, refresh_token, expires_in/at, scope.
    """
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    import json as _json
    existing_refresh: str | None = None
    if not new_tokens.get("refresh_token"):
        existing = await _get_account_with_tokens(db, user_id, account_id)
        if not existing:
            return False
        existing_refresh = (existing.get("tokens") or {}).get("refresh_token")
    refresh_token_value = new_tokens.get("refresh_token") or existing_refresh
    # Build storage values similar to create_account
    try:
        from tldw_Server_API.app.core.Security.crypto import encrypt_json_blob
        env = encrypt_json_blob({
            "access_token": new_tokens.get("access_token"),
            "refresh_token": refresh_token_value,
            "token_type": new_tokens.get("token_type"),
            "expires_in": new_tokens.get("expires_in"),
            "expires_at": new_tokens.get("expires_at"),
            "scope": new_tokens.get("scope"),
        })
        access_token_store = _json.dumps(env) if env else str(new_tokens.get("access_token") or "")
        refresh_token_store = None
        scopes_store = new_tokens.get("scope") or None
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
        access_token_store = str(new_tokens.get("access_token") or "")
        refresh_token_store = refresh_token_value
        scopes_store = new_tokens.get("scope") or None

    if is_pg:
        # Ensure ownership
        r = await db.fetchrow("SELECT id FROM external_accounts WHERE id = $1 AND user_id = $2", account_id, user_id)
        if not r:
            return False
        await db.execute(
            """
            UPDATE external_accounts
            SET access_token = $1,
                refresh_token = COALESCE($2, refresh_token),
                updated_at = CURRENT_TIMESTAMP,
                scopes = COALESCE($3, scopes)
            WHERE id = $4
            """,
            access_token_store, refresh_token_store, scopes_store, account_id,
        )
        return True
    # SQLite path
    cur = await db.execute("SELECT id FROM external_accounts WHERE id = ? AND user_id = ?", (account_id, user_id))
    if not await cur.fetchone():
        return False
    await db.execute(
        "UPDATE external_accounts SET access_token = ?, refresh_token = COALESCE(?, refresh_token), scopes = COALESCE(?, scopes), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (access_token_store, refresh_token_store, scopes_store, account_id),
    )
    await getattr(db, "commit", lambda: None)()
    return True


async def get_source_by_id(db, user_id: int, source_id: int) -> dict[str, Any] | None:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        row = await db.fetchrow(
            """
            SELECT s.*, a.user_id, a.email FROM external_sources s
            JOIN external_accounts a ON s.account_id = a.id
            WHERE s.id = $1 AND a.user_id = $2
            """,
            source_id, user_id,
        )
        return dict(row) if row else None
    cur = await db.execute(
        """
        SELECT s.id, s.account_id, s.provider, s.remote_id, s.type, s.path, s.options, s.enabled, s.last_synced_at, a.user_id, a.email
        FROM external_sources s JOIN external_accounts a ON s.account_id = a.id
        WHERE s.id = ? AND a.user_id = ?
        """,
        (source_id, user_id),
    )
    r = await cur.fetchone()
    if not r:
        return None
    try:
        return {
            "id": r[0], "account_id": r[1], "provider": r[2], "remote_id": r[3], "type": r[4], "path": r[5],
            "options": __import__("json").loads(r[6] or "{}"), "enabled": bool(r[7]), "last_synced_at": r[8],
            "user_id": r[9], "email": r[10],
        }
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
        return dict(r)


async def get_source_sync_state(db, *, source_id: int) -> dict[str, Any] | None:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        row = await db.fetchrow(
            "SELECT * FROM external_source_sync_state WHERE source_id = $1",
            source_id,
        )
        return _normalize_sync_state_row(row)
    cur = await db.execute(
        "SELECT * FROM external_source_sync_state WHERE source_id = ?",
        (source_id,),
    )
    row = await cur.fetchone()
    return _normalize_sync_state_row(row)


async def upsert_source_sync_state(db, *, source_id: int, **updates: Any) -> dict[str, Any]:
    await _ensure_tables(db)
    existing = await get_source_sync_state(db, source_id=source_id) or {}
    data = {"source_id": source_id, "sync_mode": "manual", **existing}
    for field in _SYNC_STATE_FIELDS:
        if field in updates and updates[field] is not None:
            data[field] = updates[field]

    is_pg = _is_postgres_connection(db)
    values = [
        data.get("source_id"),
        data.get("sync_mode") or "manual",
        data.get("cursor"),
        data.get("cursor_kind"),
        data.get("last_bootstrap_at"),
        data.get("last_sync_started_at"),
        data.get("last_sync_succeeded_at"),
        data.get("last_sync_failed_at"),
        data.get("last_error"),
        int(data.get("retry_backoff_count") or 0),
        data.get("webhook_status"),
        data.get("webhook_subscription_id"),
        data.get("webhook_expires_at"),
        bool(data.get("needs_full_rescan")),
        data.get("active_job_id"),
        data.get("active_job_started_at"),
    ]
    if is_pg:
        row = await db.fetchrow(
            """
            INSERT INTO external_source_sync_state (
                source_id,
                sync_mode,
                cursor,
                cursor_kind,
                last_bootstrap_at,
                last_sync_started_at,
                last_sync_succeeded_at,
                last_sync_failed_at,
                last_error,
                retry_backoff_count,
                webhook_status,
                webhook_subscription_id,
                webhook_expires_at,
                needs_full_rescan,
                active_job_id,
                active_job_started_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8,
                $9, $10, $11, $12, $13, $14, $15, $16
            )
            ON CONFLICT (source_id) DO UPDATE SET
                sync_mode = EXCLUDED.sync_mode,
                cursor = EXCLUDED.cursor,
                cursor_kind = EXCLUDED.cursor_kind,
                last_bootstrap_at = EXCLUDED.last_bootstrap_at,
                last_sync_started_at = EXCLUDED.last_sync_started_at,
                last_sync_succeeded_at = EXCLUDED.last_sync_succeeded_at,
                last_sync_failed_at = EXCLUDED.last_sync_failed_at,
                last_error = EXCLUDED.last_error,
                retry_backoff_count = EXCLUDED.retry_backoff_count,
                webhook_status = EXCLUDED.webhook_status,
                webhook_subscription_id = EXCLUDED.webhook_subscription_id,
                webhook_expires_at = EXCLUDED.webhook_expires_at,
                needs_full_rescan = EXCLUDED.needs_full_rescan,
                active_job_id = EXCLUDED.active_job_id,
                active_job_started_at = EXCLUDED.active_job_started_at
            RETURNING *
            """,
            *values,
        )
        return _normalize_sync_state_row(row) or {}

    await db.execute(
        """
        INSERT INTO external_source_sync_state (
            source_id,
            sync_mode,
            cursor,
            cursor_kind,
            last_bootstrap_at,
            last_sync_started_at,
            last_sync_succeeded_at,
            last_sync_failed_at,
            last_error,
            retry_backoff_count,
            webhook_status,
            webhook_subscription_id,
            webhook_expires_at,
            needs_full_rescan,
            active_job_id,
            active_job_started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            sync_mode = excluded.sync_mode,
            cursor = excluded.cursor,
            cursor_kind = excluded.cursor_kind,
            last_bootstrap_at = excluded.last_bootstrap_at,
            last_sync_started_at = excluded.last_sync_started_at,
            last_sync_succeeded_at = excluded.last_sync_succeeded_at,
            last_sync_failed_at = excluded.last_sync_failed_at,
            last_error = excluded.last_error,
            retry_backoff_count = excluded.retry_backoff_count,
            webhook_status = excluded.webhook_status,
            webhook_subscription_id = excluded.webhook_subscription_id,
            webhook_expires_at = excluded.webhook_expires_at,
            needs_full_rescan = excluded.needs_full_rescan,
            active_job_id = excluded.active_job_id,
            active_job_started_at = excluded.active_job_started_at
        """,
        (
            values[0],
            values[1],
            values[2],
            values[3],
            values[4],
            values[5],
            values[6],
            values[7],
            values[8],
            values[9],
            values[10],
            values[11],
            values[12],
            1 if values[13] else 0,
            values[14],
            values[15],
        ),
    )
    await getattr(db, "commit", lambda: None)()
    return await get_source_sync_state(db, source_id=source_id) or {}


async def get_external_item_binding(
    db,
    *,
    source_id: int,
    provider: str,
    external_id: str,
) -> dict[str, Any] | None:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        row = await db.fetchrow(
            """
            SELECT *
            FROM external_items
            WHERE source_id = $1 AND provider = $2 AND external_id = $3
            """,
            source_id,
            provider,
            external_id,
        )
        return _normalize_external_item_row(row)
    cur = await db.execute(
        """
        SELECT *
        FROM external_items
        WHERE source_id = ? AND provider = ? AND external_id = ?
        """,
        (source_id, provider, external_id),
    )
    row = await cur.fetchone()
    return _normalize_external_item_row(row)


async def list_external_items_for_source(db, *, source_id: int) -> list[dict[str, Any]]:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        rows = await db.fetch(
            "SELECT * FROM external_items WHERE source_id = $1 ORDER BY id ASC",
            source_id,
        )
        return [_normalize_external_item_row(row) or {} for row in rows]
    cur = await db.execute(
        "SELECT * FROM external_items WHERE source_id = ? ORDER BY id ASC",
        (source_id,),
    )
    rows = await cur.fetchall()
    return [_normalize_external_item_row(row) or {} for row in rows]


async def upsert_external_item_binding(
    db,
    *,
    source_id: int,
    provider: str,
    external_id: str,
    name: str | None = None,
    mime: str | None = None,
    size: int | None = None,
    version: str | None = None,
    modified_at: str | None = None,
    content_hash: str | None = None,
    media_id: int | None = None,
    sync_status: str | None = None,
    current_version_number: int | None = None,
    remote_parent_id: str | None = None,
    remote_path: str | None = None,
    last_seen_at: str | None = None,
    last_content_sync_at: str | None = None,
    last_metadata_sync_at: str | None = None,
    remote_deleted_at: str | None = None,
    access_revoked_at: str | None = None,
    provider_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    last_seen_value = last_seen_at or _utc_now_text()
    provider_metadata_value = provider_metadata or None
    sqlite_provider_metadata = json.dumps(provider_metadata_value) if provider_metadata_value is not None else None
    sync_status_value = sync_status or "active"

    if is_pg:
        await db.execute(
            """
            INSERT INTO external_items (
                source_id,
                provider,
                external_id,
                name,
                mime,
                size,
                modified_at,
                version,
                hash,
                last_ingested_at,
                media_id,
                sync_status,
                current_version_number,
                remote_parent_id,
                remote_path,
                last_seen_at,
                last_content_sync_at,
                last_metadata_sync_at,
                remote_deleted_at,
                access_revoked_at,
                provider_metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP,
                $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
            )
            ON CONFLICT (source_id, provider, external_id) DO UPDATE SET
                name = COALESCE(EXCLUDED.name, external_items.name),
                mime = COALESCE(EXCLUDED.mime, external_items.mime),
                size = COALESCE(EXCLUDED.size, external_items.size),
                modified_at = COALESCE(EXCLUDED.modified_at, external_items.modified_at),
                version = COALESCE(EXCLUDED.version, external_items.version),
                hash = COALESCE(EXCLUDED.hash, external_items.hash),
                last_ingested_at = CURRENT_TIMESTAMP,
                media_id = COALESCE(EXCLUDED.media_id, external_items.media_id),
                sync_status = COALESCE(EXCLUDED.sync_status, external_items.sync_status),
                current_version_number = COALESCE(EXCLUDED.current_version_number, external_items.current_version_number),
                remote_parent_id = COALESCE(EXCLUDED.remote_parent_id, external_items.remote_parent_id),
                remote_path = COALESCE(EXCLUDED.remote_path, external_items.remote_path),
                last_seen_at = COALESCE(EXCLUDED.last_seen_at, external_items.last_seen_at),
                last_content_sync_at = COALESCE(EXCLUDED.last_content_sync_at, external_items.last_content_sync_at),
                last_metadata_sync_at = COALESCE(EXCLUDED.last_metadata_sync_at, external_items.last_metadata_sync_at),
                remote_deleted_at = COALESCE(EXCLUDED.remote_deleted_at, external_items.remote_deleted_at),
                access_revoked_at = COALESCE(EXCLUDED.access_revoked_at, external_items.access_revoked_at),
                provider_metadata = COALESCE(EXCLUDED.provider_metadata, external_items.provider_metadata)
            """,
            source_id,
            provider,
            external_id,
            name,
            mime,
            size,
            modified_at,
            version,
            content_hash,
            media_id,
            sync_status_value,
            current_version_number,
            remote_parent_id,
            remote_path,
            last_seen_value,
            last_content_sync_at,
            last_metadata_sync_at,
            remote_deleted_at,
            access_revoked_at,
            provider_metadata_value,
        )
    else:
        await db.execute(
            """
            INSERT INTO external_items (
                source_id,
                provider,
                external_id,
                name,
                mime,
                size,
                modified_at,
                version,
                hash,
                last_ingested_at,
                media_id,
                sync_status,
                current_version_number,
                remote_parent_id,
                remote_path,
                last_seen_at,
                last_content_sync_at,
                last_metadata_sync_at,
                remote_deleted_at,
                access_revoked_at,
                provider_metadata
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(source_id, provider, external_id) DO UPDATE SET
                name = COALESCE(excluded.name, external_items.name),
                mime = COALESCE(excluded.mime, external_items.mime),
                size = COALESCE(excluded.size, external_items.size),
                modified_at = COALESCE(excluded.modified_at, external_items.modified_at),
                version = COALESCE(excluded.version, external_items.version),
                hash = COALESCE(excluded.hash, external_items.hash),
                last_ingested_at = CURRENT_TIMESTAMP,
                media_id = COALESCE(excluded.media_id, external_items.media_id),
                sync_status = COALESCE(excluded.sync_status, external_items.sync_status),
                current_version_number = COALESCE(excluded.current_version_number, external_items.current_version_number),
                remote_parent_id = COALESCE(excluded.remote_parent_id, external_items.remote_parent_id),
                remote_path = COALESCE(excluded.remote_path, external_items.remote_path),
                last_seen_at = COALESCE(excluded.last_seen_at, external_items.last_seen_at),
                last_content_sync_at = COALESCE(excluded.last_content_sync_at, external_items.last_content_sync_at),
                last_metadata_sync_at = COALESCE(excluded.last_metadata_sync_at, external_items.last_metadata_sync_at),
                remote_deleted_at = COALESCE(excluded.remote_deleted_at, external_items.remote_deleted_at),
                access_revoked_at = COALESCE(excluded.access_revoked_at, external_items.access_revoked_at),
                provider_metadata = COALESCE(excluded.provider_metadata, external_items.provider_metadata)
            """,
            (
                source_id,
                provider,
                external_id,
                name,
                mime,
                size,
                modified_at,
                version,
                content_hash,
                media_id,
                sync_status_value,
                current_version_number,
                remote_parent_id,
                remote_path,
                last_seen_value,
                last_content_sync_at,
                last_metadata_sync_at,
                remote_deleted_at,
                access_revoked_at,
                sqlite_provider_metadata,
            ),
        )
        await getattr(db, "commit", lambda: None)()

    return await get_external_item_binding(
        db,
        source_id=source_id,
        provider=provider,
        external_id=external_id,
    ) or {}


async def record_item_event(
    db,
    *,
    external_item_id: int,
    event_type: str,
    job_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        row = await db.fetchrow(
            """
            INSERT INTO external_item_events (
                external_item_id,
                event_type,
                job_id,
                payload_json
            ) VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            external_item_id,
            event_type,
            job_id,
            payload or {},
        )
        out = _row_to_dict(row)
        out["payload_json"] = _json_loads(out.get("payload_json"), {})
        return out
    cur = await db.execute(
        """
        INSERT INTO external_item_events (
            external_item_id,
            event_type,
            job_id,
            payload_json
        ) VALUES (?, ?, ?, ?)
        """,
        (
            external_item_id,
            event_type,
            job_id,
            json.dumps(payload or {}),
        ),
    )
    await getattr(db, "commit", lambda: None)()
    row_id = cur.lastrowid
    cur2 = await db.execute(
        "SELECT * FROM external_item_events WHERE id = ?",
        (row_id,),
    )
    row = await cur2.fetchone()
    out = _row_to_dict(row)
    out["payload_json"] = _json_loads(out.get("payload_json"), {})
    return out


async def mark_external_item_archived(
    db,
    *,
    source_id: int,
    provider: str,
    external_id: str,
    sync_status: str = "archived_upstream_removed",
) -> dict[str, Any] | None:
    await _ensure_tables(db)
    deleted_at = _utc_now_text()
    is_pg = _is_postgres_connection(db)
    if is_pg:
        await db.execute(
            """
            UPDATE external_items
            SET sync_status = $1,
                remote_deleted_at = COALESCE(remote_deleted_at, $2),
                last_metadata_sync_at = $2
            WHERE source_id = $3 AND provider = $4 AND external_id = $5
            """,
            sync_status,
            deleted_at,
            source_id,
            provider,
            external_id,
        )
    else:
        await db.execute(
            """
            UPDATE external_items
            SET sync_status = ?,
                remote_deleted_at = COALESCE(remote_deleted_at, ?),
                last_metadata_sync_at = ?
            WHERE source_id = ? AND provider = ? AND external_id = ?
            """,
            (sync_status, deleted_at, deleted_at, source_id, provider, external_id),
        )
        await getattr(db, "commit", lambda: None)()
    return await get_external_item_binding(
        db,
        source_id=source_id,
        provider=provider,
        external_id=external_id,
    )


async def should_ingest_item(
    db, *, source_id: int, provider: str, external_id: str, version: str | None, modified_at: str | None, content_hash: str | None
) -> bool:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        row = await db.fetchrow("SELECT version, modified_at, hash FROM external_items WHERE source_id = $1 AND provider = $2 AND external_id = $3", source_id, provider, external_id)
        if not row:
            return True
        r = dict(row)
    else:
        cur = await db.execute("SELECT version, modified_at, hash FROM external_items WHERE source_id = ? AND provider = ? AND external_id = ?", (source_id, provider, external_id))
        r = await cur.fetchone()
        if not r:
            return True
        try:
            r = {"version": r[0], "modified_at": r[1], "hash": r[2]}
        except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
            r = dict(r)
    # Decide using hash > version > modified_at
    if content_hash and r.get("hash") and content_hash == r.get("hash"):
        return False
    if version and r.get("version") and version == r.get("version"):
        return False
    return not (modified_at and r.get("modified_at") and str(modified_at) == str(r.get("modified_at")))


async def record_ingested_item(
    db, *, source_id: int, provider: str, external_id: str, name: str | None, mime: str | None, size: int | None, version: str | None, modified_at: str | None, content_hash: str | None
) -> None:
    await upsert_external_item_binding(
        db,
        source_id=source_id,
        provider=provider,
        external_id=external_id,
        name=name,
        mime=mime,
        size=int(size or 0),
        version=version,
        modified_at=modified_at,
        content_hash=content_hash,
        sync_status="active",
        last_content_sync_at=_utc_now_text(),
    )


def _today_utc_start_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def count_connectors_jobs_today(user_id: int) -> int:
    from tldw_Server_API.app.core.Jobs.manager import JobManager
    jm = JobManager()
    conn = jm._connect()
    try:
        if jm.backend == "postgres":
            with jm._pg_cursor(conn) as cur:  # type: ignore[attr-defined]
                cur.execute(
                    "SELECT COUNT(*) AS c FROM jobs WHERE domain = %s AND owner_user_id = %s AND created_at >= %s",
                    ("connectors", str(user_id), _today_utc_start_str()),
                )
                row = cur.fetchone()
                return int(row["c"]) if row else 0
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE domain = ? AND owner_user_id = ? AND created_at >= ?",
                ("connectors", str(user_id), _today_utc_start_str()),
            ).fetchone()
            return int(row[0]) if row else 0
    finally:
        with contextlib.suppress(_CONNECTORS_NONCRITICAL_EXCEPTIONS):
            conn.close()


async def list_accounts(db, user_id: int) -> list[dict[str, Any]]:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        rows = await db.fetch("SELECT id, provider, display_name, email, created_at FROM external_accounts WHERE user_id = $1 ORDER BY created_at DESC", user_id)
        return [dict(r) for r in rows]
    cur = await db.execute("SELECT id, provider, display_name, email, created_at FROM external_accounts WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = await cur.fetchall()
    return [{"id": r[0], "provider": r[1], "display_name": r[2], "email": r[3], "created_at": r[4]} for r in rows]


async def delete_account(db, user_id: int, account_id: int) -> bool:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        await db.execute("DELETE FROM external_accounts WHERE id = $1 AND user_id = $2", account_id, user_id)
        return True
    await db.execute("DELETE FROM external_accounts WHERE id = ? AND user_id = ?", (account_id, user_id))
    await getattr(db, "commit", lambda: None)()
    return True


async def create_source(
    db,
    *,
    account_id: int,
    provider: str,
    remote_id: str,
    type_: str,
    path: str | None,
    options: dict[str, Any],
    enabled: bool = True,
) -> dict[str, Any]:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    if is_pg:
        row = await db.fetchrow(
            """
            INSERT INTO external_sources (account_id, provider, remote_id, type, path, options, enabled)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, account_id, provider, remote_id, type, path, options, enabled, last_synced_at
            """,
            account_id, provider, remote_id, type_, path, options, enabled,
        )
        d = dict(row)
        return d
    cur = await db.execute(
        """
        INSERT INTO external_sources (account_id, provider, remote_id, type, path, options, enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (account_id, provider, remote_id, type_, path, __import__("json").dumps(options or {}), 1 if enabled else 0),
    )
    await getattr(db, "commit", lambda: None)()
    rid = cur.lastrowid
    cur2 = await db.execute("SELECT id, account_id, provider, remote_id, type, path, options, enabled, last_synced_at FROM external_sources WHERE id = ?", (rid,))
    r = await cur2.fetchone()
    options_raw = r[6]
    try:
        return {
            "id": r[0],
            "account_id": r[1],
            "provider": r[2],
            "remote_id": r[3],
            "type": r[4],
            "path": r[5],
            "options": __import__("json").loads(options_raw or "{}"),
            "enabled": bool(r[7]),
            "last_synced_at": r[8],
        }
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
        row = dict(r)
        with contextlib.suppress(_CONNECTORS_NONCRITICAL_EXCEPTIONS):
            row["options"] = __import__("json").loads(row.get("options") or "{}")
        return row


async def list_sources(db, user_id: int) -> list[dict[str, Any]]:
    await _ensure_tables(db)
    # Join through accounts to enforce per-user scoping
    is_pg = _is_postgres_connection(db)
    if is_pg:
        rows = await db.fetch(
            """
            SELECT s.id, s.account_id, s.provider, s.remote_id, s.type, s.path, s.options, s.enabled, s.last_synced_at
            FROM external_sources s
            JOIN external_accounts a ON s.account_id = a.id
            WHERE a.user_id = $1
            ORDER BY s.id DESC
            """,
            user_id,
        )
        return [dict(r) for r in rows]
    cur = await db.execute(
        """
        SELECT s.id, s.account_id, s.provider, s.remote_id, s.type, s.path, s.options, s.enabled, s.last_synced_at
        FROM external_sources s
        JOIN external_accounts a ON s.account_id = a.id
        WHERE a.user_id = ?
        ORDER BY s.id DESC
        """,
        (user_id,),
    )
    rows = await cur.fetchall()
    out = []
    for r in rows:
        try:
            opts = __import__("json").loads(r[6] or "{}")
            out.append({
                "id": r[0],
                "account_id": r[1],
                "provider": r[2],
                "remote_id": r[3],
                "type": r[4],
                "path": r[5],
                "options": opts,
                "enabled": bool(r[7]),
                "last_synced_at": r[8],
            })
        except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
            row = dict(r)
            with contextlib.suppress(_CONNECTORS_NONCRITICAL_EXCEPTIONS):
                row["options"] = __import__("json").loads(row.get("options") or "{}")
            out.append(row)
    return out


async def update_source(db, user_id: int, source_id: int, *, enabled: bool | None = None, options: dict[str, Any] | None = None) -> dict[str, Any] | None:
    await _ensure_tables(db)
    is_pg = _is_postgres_connection(db)
    # Ensure source belongs to user via join
    if is_pg:
        row = await db.fetchrow(
            "SELECT s.id, s.account_id FROM external_sources s JOIN external_accounts a ON s.account_id = a.id WHERE s.id = $1 AND a.user_id = $2",
            source_id, user_id,
        )
        if not row:
            return None
        sets = []
        params: list[Any] = []
        if enabled is not None:
            sets.append(f"enabled = ${len(params) + 1}")
            params.append(enabled)
        if options is not None:
            sets.append(f"options = ${len(params) + 1}")
            params.append(options)
        if not sets:
            pass
        else:
            params.extend([source_id])
            set_clause = ", ".join(sets)
            source_id_param = len(params)
            update_source_sql_template = "UPDATE external_sources SET {set_clause} WHERE id = ${source_id_param}"
            update_source_sql = update_source_sql_template.format_map(locals())  # nosec B608
            await db.execute(update_source_sql, *params)
        row2 = await db.fetchrow("SELECT id, account_id, provider, remote_id, type, path, options, enabled, last_synced_at FROM external_sources WHERE id = $1", source_id)
        return dict(row2)
    cur = await db.execute(
        """
        SELECT s.id, s.account_id
        FROM external_sources s
        JOIN external_accounts a ON s.account_id = a.id
        WHERE s.id = ? AND a.user_id = ?
        """,
        (source_id, user_id),
    )
    r = await cur.fetchone()
    if not r:
        return None
    sets = []
    params: list[Any] = []
    if enabled is not None:
        sets.append("enabled = ?")
        params.append(1 if enabled else 0)
    if options is not None:
        sets.append("options = ?")
        params.append(__import__("json").dumps(options or {}))
    if sets:
        params.extend([source_id])
        set_clause = ", ".join(sets)
        update_source_sql_template = "UPDATE external_sources SET {set_clause} WHERE id = ?"
        update_source_sql = update_source_sql_template.format_map(locals())  # nosec B608
        await db.execute(update_source_sql, params)
        await getattr(db, "commit", lambda: None)()
    cur2 = await db.execute("SELECT id, account_id, provider, remote_id, type, path, options, enabled, last_synced_at FROM external_sources WHERE id = ?", (source_id,))
    r2 = await cur2.fetchone()
    try:
        return {
            "id": r2[0],
            "account_id": r2[1],
            "provider": r2[2],
            "remote_id": r2[3],
            "type": r2[4],
            "path": r2[5],
            "options": __import__("json").loads(r2[6] or "{}"),
            "enabled": bool(r2[7]),
            "last_synced_at": r2[8],
        }
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS:
        row = dict(r2)
        with contextlib.suppress(_CONNECTORS_NONCRITICAL_EXCEPTIONS):
            row["options"] = __import__("json").loads(row.get("options") or "{}")
        return row


async def create_import_job(user_id: int, source_id: int, *, request_id: str | None = None) -> dict[str, Any]:
    """Create a generic job in the core Jobs manager for connector import.

    Scaffold behavior: creates a job with payload but does not perform ingestion.
    """
    try:
        from tldw_Server_API.app.core.Jobs.manager import JobManager
        jm = JobManager()
        payload = {
            "source_id": source_id,
            "user_id": user_id,
        }
        if request_id:
            payload["request_id"] = request_id
        job = jm.create_job(domain="connectors", queue="default", job_type="import", owner_user_id=str(user_id), payload=payload, priority=50, request_id=request_id)
        job_id = job.get("id") or job.get("job_id") or job.get("uuid")
        return {
            "id": str(job_id),
            "source_id": source_id,
            "type": "import",
            "status": "queued",
            "progress_pct": 0,
            "counts": {"processed": 0, "skipped": 0, "failed": 0},
        }
    except _CONNECTORS_NONCRITICAL_EXCEPTIONS as e:
        logger.warning(f"Failed to create connectors job via JobManager: {e}")
        # Fallback to synthetic ID
        import uuid
        jid = uuid.uuid4().hex
        return {
            "id": jid,
            "source_id": source_id,
            "type": "import",
            "status": "queued",
            "progress_pct": 0,
            "counts": {"processed": 0, "skipped": 0, "failed": 0},
        }
