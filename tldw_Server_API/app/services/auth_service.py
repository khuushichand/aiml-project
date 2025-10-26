from __future__ import annotations

from typing import Any, Dict, Optional
from loguru import logger
from datetime import datetime
from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend


async def fetch_user_by_login_identifier(db, identifier: str) -> Optional[Dict[str, Any]]:
    """Fetch a user row by username or email (case-insensitive), normalized to dict."""
    ident_l = identifier.strip().lower()
    is_pg = await is_postgres_backend()
    try:
        if is_pg:
            row = await db.fetchrow(
                "SELECT * FROM users WHERE lower(username) = $1 OR lower(email) = $2",
                ident_l, ident_l
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM users WHERE lower(username) = ? OR lower(email) = ?",
                (ident_l, ident_l)
            )
            row = await cursor.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            return row
        # Convert common row types to dict
        try:
            return dict(row)
        except Exception:
            cols = ['id','uuid','username','email','password_hash','role','is_active','is_verified','created_at','updated_at','last_login','storage_quota_mb','storage_used_mb']
            return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}
    except Exception as e:
        logger.error(f"auth_service.fetch_user_by_login_identifier failed: {e}")
        raise


async def update_user_password_hash(db, user_id: int, new_hash: str) -> None:
    """Persist a new password hash for the user."""
    is_pg = await is_postgres_backend()
    try:
        if is_pg:
            await db.execute("UPDATE users SET password_hash = $1 WHERE id = $2", new_hash, user_id)
        else:
            await db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
            commit = getattr(db, "commit", None)
            if callable(commit):
                await commit()
    except Exception as e:
        logger.error(f"auth_service.update_user_password_hash failed for user {user_id}: {e}")
        raise


async def update_user_last_login(db, user_id: int, now: Optional[datetime] = None) -> None:
    """Update last_login timestamp for the user."""
    now = now or datetime.utcnow()
    is_pg = await is_postgres_backend()
    try:
        if is_pg:
            await db.execute("UPDATE users SET last_login = $1 WHERE id = $2", now, user_id)
        else:
            await db.execute("UPDATE users SET last_login = ? WHERE id = ?", (now.isoformat(), user_id))
            commit = getattr(db, "commit", None)
            if callable(commit):
                await commit()
    except Exception as e:
        logger.error(f"auth_service.update_user_last_login failed for user {user_id}: {e}")
        raise


async def fetch_active_user_by_id(db, user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch an active user by id, normalized to dict, or None if not found."""
    is_pg = await is_postgres_backend()
    try:
        if is_pg:
            row = await db.fetchrow("SELECT * FROM users WHERE id = $1 AND is_active = $2", user_id, True)
        else:
            cursor = await db.execute("SELECT * FROM users WHERE id = ? AND is_active = ?", (user_id, 1))
            row = await cursor.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            return row
        try:
            return dict(row)
        except Exception:
            cols = ['id','uuid','username','email','password_hash','role','is_active','is_verified','created_at','updated_at','last_login','storage_quota_mb','storage_used_mb']
            return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}
    except Exception as e:
        logger.error(f"auth_service.fetch_active_user_by_id failed: {e}")
        raise
