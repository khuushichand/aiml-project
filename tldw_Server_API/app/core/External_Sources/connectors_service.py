from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend
from tldw_Server_API.app.core.External_Sources.google_drive import GoogleDriveConnector
from tldw_Server_API.app.core.External_Sources.notion import NotionConnector


def get_connector_by_name(name: str):
    n = name.lower()
    if n == "drive":
        return GoogleDriveConnector()
    if n == "notion":
        return NotionConnector()
    raise ValueError(f"Unknown connector provider: {name}")


async def _ensure_tables(db) -> None:
    """Create connector tables if they don't exist in the AuthNZ DB."""
    is_pg = await is_postgres_backend()
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
    except Exception as e:
        logger.error(f"Failed to ensure connector tables: {e}")
        raise


async def upsert_policy(db, org_id: int, policy: Dict[str, Any]) -> Dict[str, Any]:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
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


async def get_policy(db, org_id: int) -> Dict[str, Any]:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
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
    except Exception:
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
    except Exception:
        row["quotas_per_role"] = {}
    return row


async def create_account(db, user_id: int, provider: str, display_name: str, email: Optional[str], tokens: Dict[str, Any]) -> Dict[str, Any]:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
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
        scopes_store = tokens.get("scope") or None
    except Exception:
        access_token_store = str(tokens.get("access_token") or "")
        refresh_token_store = tokens.get("refresh_token")
        scopes_store = tokens.get("scope") or None

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
    except Exception:
        return dict(r)


async def _get_account_with_tokens(db, user_id: int, account_id: int) -> Optional[Dict[str, Any]]:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
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
        except Exception:
            d = dict(r)
    # Decrypt envelope if present
    tokens: Dict[str, Any] = {}
    import json as _json
    at_raw = d.get("access_token")
    if at_raw and isinstance(at_raw, str) and at_raw.strip().startswith("{"):
        try:
            from tldw_Server_API.app.core.Security.crypto import decrypt_json_blob
            env = _json.loads(at_raw)
            dec = decrypt_json_blob(env) or {}
            tokens.update(dec)
        except Exception:
            pass
    if not tokens.get("access_token") and isinstance(at_raw, str):
        tokens["access_token"] = at_raw
    if not tokens.get("refresh_token") and d.get("refresh_token"):
        tokens["refresh_token"] = d.get("refresh_token")
    d["tokens"] = tokens
    return d


async def get_account_tokens(db, user_id: int, account_id: int) -> Optional[Dict[str, Any]]:
    row = await _get_account_with_tokens(db, user_id, account_id)
    if not row:
        return None
    return row.get("tokens") or {}


async def get_account_email(db, user_id: int, account_id: int) -> Optional[str]:
    row = await _get_account_with_tokens(db, user_id, account_id)
    return None if not row else (row.get("email") or None)


async def update_account_tokens(db, user_id: int, account_id: int, new_tokens: Dict[str, Any]) -> bool:
    """Persist refreshed tokens for an account. Uses envelope encryption when configured.

    new_tokens may include: access_token, refresh_token, expires_in/at, scope.
    """
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
    import json as _json
    # Build storage values similar to create_account
    try:
        from tldw_Server_API.app.core.Security.crypto import encrypt_json_blob
        env = encrypt_json_blob({
            "access_token": new_tokens.get("access_token"),
            "refresh_token": new_tokens.get("refresh_token"),
            "token_type": new_tokens.get("token_type"),
            "expires_in": new_tokens.get("expires_in"),
            "expires_at": new_tokens.get("expires_at"),
            "scope": new_tokens.get("scope"),
        })
        access_token_store = _json.dumps(env) if env else str(new_tokens.get("access_token") or "")
        refresh_token_store = None
        scopes_store = new_tokens.get("scope") or None
    except Exception:
        access_token_store = str(new_tokens.get("access_token") or "")
        refresh_token_store = new_tokens.get("refresh_token")
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


async def get_source_by_id(db, user_id: int, source_id: int) -> Optional[Dict[str, Any]]:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
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
    except Exception:
        return dict(r)


async def should_ingest_item(
    db, *, source_id: int, provider: str, external_id: str, version: Optional[str], modified_at: Optional[str], content_hash: Optional[str]
) -> bool:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
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
        except Exception:
            r = dict(r)
    # Decide using hash > version > modified_at
    if content_hash and r.get("hash") and content_hash == r.get("hash"):
        return False
    if version and r.get("version") and version == r.get("version"):
        return False
    if modified_at and r.get("modified_at") and str(modified_at) == str(r.get("modified_at")):
        return False
    return True


async def record_ingested_item(
    db, *, source_id: int, provider: str, external_id: str, name: Optional[str], mime: Optional[str], size: Optional[int], version: Optional[str], modified_at: Optional[str], content_hash: Optional[str]
) -> None:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
    if is_pg:
        await db.execute(
            """
            INSERT INTO external_items (source_id, provider, external_id, name, mime, size, modified_at, version, hash, last_ingested_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9, CURRENT_TIMESTAMP)
            ON CONFLICT (source_id, provider, external_id) DO UPDATE SET
                name=EXCLUDED.name, mime=EXCLUDED.mime, size=EXCLUDED.size,
                modified_at=EXCLUDED.modified_at, version=EXCLUDED.version, hash=EXCLUDED.hash,
                last_ingested_at=CURRENT_TIMESTAMP
            """,
            source_id, provider, external_id, name, mime, int(size or 0), modified_at, version, content_hash,
        )
        return
    await db.execute(
        """
        INSERT OR REPLACE INTO external_items (id, source_id, provider, external_id, name, mime, size, modified_at, version, hash, last_ingested_at)
        VALUES (
            COALESCE((SELECT id FROM external_items WHERE source_id = ? AND provider = ? AND external_id = ?), NULL),
            ?,?,?,?,?,?,?,?, ?, CURRENT_TIMESTAMP
        )
        """,
        (source_id, provider, external_id, source_id, provider, external_id, name, mime, int(size or 0), modified_at, version, content_hash),
    )
    await getattr(db, "commit", lambda: None)()


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
        try:
            conn.close()
        except Exception:
            pass


async def list_accounts(db, user_id: int) -> List[Dict[str, Any]]:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
    if is_pg:
        rows = await db.fetch("SELECT id, provider, display_name, email, created_at FROM external_accounts WHERE user_id = $1 ORDER BY created_at DESC", user_id)
        return [dict(r) for r in rows]
    cur = await db.execute("SELECT id, provider, display_name, email, created_at FROM external_accounts WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = await cur.fetchall()
    return [{"id": r[0], "provider": r[1], "display_name": r[2], "email": r[3], "created_at": r[4]} for r in rows]


async def delete_account(db, user_id: int, account_id: int) -> bool:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
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
    path: Optional[str],
    options: Dict[str, Any],
    enabled: bool = True,
) -> Dict[str, Any]:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
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
    except Exception:
        row = dict(r)
        try:
            row["options"] = __import__("json").loads(row.get("options") or "{}")
        except Exception:
            pass
        return row


async def list_sources(db, user_id: int) -> List[Dict[str, Any]]:
    await _ensure_tables(db)
    # Join through accounts to enforce per-user scoping
    is_pg = await is_postgres_backend()
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
        except Exception:
            row = dict(r)
            try:
                row["options"] = __import__("json").loads(row.get("options") or "{}")
            except Exception:
                pass
            out.append(row)
    return out


async def update_source(db, user_id: int, source_id: int, *, enabled: Optional[bool] = None, options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    await _ensure_tables(db)
    is_pg = await is_postgres_backend()
    # Ensure source belongs to user via join
    if is_pg:
        row = await db.fetchrow(
            "SELECT s.id, s.account_id FROM external_sources s JOIN external_accounts a ON s.account_id = a.id WHERE s.id = $1 AND a.user_id = $2",
            source_id, user_id,
        )
        if not row:
            return None
        sets = []
        params: List[Any] = []
        if enabled is not None:
            sets.append("enabled = $%d" % (len(params) + 1))
            params.append(enabled)
        if options is not None:
            sets.append("options = $%d" % (len(params) + 1))
            params.append(options)
        if not sets:
            pass
        else:
            params.extend([source_id])
            await db.execute(f"UPDATE external_sources SET {', '.join(sets)} WHERE id = $%d" % (len(params)), *params)
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
    params: List[Any] = []
    if enabled is not None:
        sets.append("enabled = ?")
        params.append(1 if enabled else 0)
    if options is not None:
        sets.append("options = ?")
        params.append(__import__("json").dumps(options or {}))
    if sets:
        params.extend([source_id])
        await db.execute(f"UPDATE external_sources SET {', '.join(sets)} WHERE id = ?", params)
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
    except Exception:
        row = dict(r2)
        try:
            row["options"] = __import__("json").loads(row.get("options") or "{}")
        except Exception:
            pass
        return row


async def create_import_job(user_id: int, source_id: int, *, request_id: Optional[str] = None) -> Dict[str, Any]:
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
    except Exception as e:
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
