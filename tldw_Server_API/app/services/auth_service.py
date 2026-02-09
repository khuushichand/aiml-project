from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any

from loguru import logger

_USER_ROW_FALLBACK_COLUMNS = (
    "id",
    "uuid",
    "username",
    "email",
    "password_hash",
    "role",
    "is_active",
    "is_verified",
    "created_at",
    "updated_at",
    "last_login",
    "storage_quota_mb",
    "storage_used_mb",
)


def _normalize_user_row(row: Any) -> dict[str, Any] | None:
    if not row:
        return None
    if isinstance(row, dict):
        return dict(row)
    with contextlib.suppress(Exception):
        return dict(row)
    with contextlib.suppress(Exception):
        return {key: row[key] for key in row.keys()}
    return {
        _USER_ROW_FALLBACK_COLUMNS[i]: row[i]
        for i in range(min(len(_USER_ROW_FALLBACK_COLUMNS), len(row)))
    }


async def _execute_compat(db: Any, query: str, *params: Any) -> Any:
    execute = getattr(db, "execute")
    try:
        return await execute(query, *params)
    except TypeError:
        # Compatibility for sqlite-like execute(query, tuple(params))
        return await execute(query, tuple(params))


async def _fetchrow_compat(db: Any, query: str, *params: Any) -> Any:
    fetchrow = getattr(db, "fetchrow", None)
    if callable(fetchrow):
        return await fetchrow(query, *params)
    cursor = await _execute_compat(db, query.replace("$1", "?").replace("$2", "?"), *params)
    return await cursor.fetchone()


async def _maybe_commit(db: Any) -> None:
    commit = getattr(db, "commit", None)
    if callable(commit):
        with contextlib.suppress(Exception):
            await commit()


async def fetch_user_by_login_identifier(db, identifier: str) -> dict[str, Any] | None:
    """Fetch a user row by username or email (case-insensitive)."""
    ident_l = identifier.strip().lower()
    try:
        row = await _fetchrow_compat(
            db,
            "SELECT * FROM users WHERE lower(username) = $1 OR lower(email) = $2",
            ident_l,
            ident_l,
        )
        return _normalize_user_row(row)
    except Exception as e:
        logger.error(f"auth_service.fetch_user_by_login_identifier failed: {e}")
        raise


async def update_user_password_hash(db, user_id: int, new_hash: str) -> None:
    """Persist a new password hash for the user."""
    try:
        await _execute_compat(
            db,
            "UPDATE users SET password_hash = $1 WHERE id = $2",
            new_hash,
            user_id,
        )
        await _maybe_commit(db)
    except Exception as e:
        logger.error(f"auth_service.update_user_password_hash failed for user {user_id}: {e}")
        raise


async def update_user_last_login(db, user_id: int, now: datetime | None = None) -> None:
    """Update last_login timestamp for the user."""
    now = now or datetime.utcnow()
    try:
        await _execute_compat(
            db,
            "UPDATE users SET last_login = $1 WHERE id = $2",
            now,
            user_id,
        )
        await _maybe_commit(db)
    except Exception as e:
        logger.error(f"auth_service.update_user_last_login failed for user {user_id}: {e}")
        raise


async def fetch_active_user_by_id(db, user_id: int) -> dict[str, Any] | None:
    """Fetch an active user by id, normalized to dict, or None if not found."""
    try:
        row = await _fetchrow_compat(
            db,
            "SELECT * FROM users WHERE id = $1 AND is_active = $2",
            user_id,
            True,
        )
        user = _normalize_user_row(row)
        if user and "is_active" in user:
            user["is_active"] = bool(user.get("is_active"))
        return user
    except Exception as e:
        logger.error(f"auth_service.fetch_active_user_by_id failed: {e}")
        raise
