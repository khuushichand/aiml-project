from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


@dataclass
class AuthnzSessionsRepo:
    """
    Repository for AuthNZ session persistence.

    This repo centralizes the core read/write paths for the ``sessions``
    table so that SessionManager does not need to embed backend-specific
    SQL or DDL checks for PostgreSQL vs SQLite.
    """

    db_pool: DatabasePool

    async def create_session_record(
        self,
        *,
        user_id: int,
        token_hash: str,
        refresh_token_hash: str,
        encrypted_token: str,
        encrypted_refresh: str,
        expires_at: datetime,
        refresh_expires_at: Optional[datetime],
        ip_address: str,
        user_agent: str,
        device_id: str,
        access_jti: Optional[str],
        refresh_jti: Optional[str],
    ) -> int:
        """
        Insert a new session row and return its ``id``.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchval"):
                    session_id = await conn.fetchval(
                        """
                        INSERT INTO sessions (
                            user_id, token_hash, refresh_token_hash,
                            encrypted_token, encrypted_refresh,
                            expires_at, refresh_expires_at,
                            ip_address, user_agent, device_id,
                            access_jti, refresh_jti
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        RETURNING id
                        """,
                        user_id,
                        token_hash,
                        refresh_token_hash,
                        encrypted_token,
                        encrypted_refresh,
                        expires_at,
                        refresh_expires_at,
                        ip_address,
                        user_agent,
                        device_id,
                        access_jti,
                        refresh_jti,
                    )
                    return int(session_id)

                cursor = await conn.execute(
                    """
                    INSERT INTO sessions (
                        user_id, token_hash, refresh_token_hash,
                        encrypted_token, encrypted_refresh,
                        expires_at, refresh_expires_at,
                        ip_address, user_agent, device_id,
                        access_jti, refresh_jti
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        token_hash,
                        refresh_token_hash,
                        encrypted_token,
                        encrypted_refresh,
                        expires_at.isoformat(),
                        refresh_expires_at.isoformat() if refresh_expires_at else None,
                        ip_address,
                        user_agent,
                        device_id,
                        access_jti,
                        refresh_jti,
                    ),
                )
                session_id = getattr(cursor, "lastrowid", None)
                try:
                    await conn.commit()
                except Exception:
                    pass

                if session_id is None:
                    raise RuntimeError("Failed to obtain session id for new session row")
                return int(session_id)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzSessionsRepo.create_session_record failed: {exc}")
            raise

    async def revoke_session_record(
        self,
        *,
        session_id: int,
        revoked_by: Optional[int],
        reason: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Mark a single session as revoked and return its details for blacklist use.
        """
        try:
            async with self.db_pool.transaction() as conn:
                session_details: Optional[Dict[str, Any]] = None

                if hasattr(conn, "fetchrow"):
                    session_row = await conn.fetchrow(
                        """
                        SELECT id, user_id, access_jti, refresh_jti, expires_at, refresh_expires_at
                        FROM sessions
                        WHERE id = $1
                        """,
                        session_id,
                    )
                    if session_row:
                        session_details = dict(session_row)

                    await conn.execute(
                        """
                        UPDATE sessions
                        SET is_active = FALSE,
                            is_revoked = TRUE,
                            revoked_at = CURRENT_TIMESTAMP,
                            revoked_by = $2,
                            revoke_reason = $3
                        WHERE id = $1
                        """,
                        session_id,
                        revoked_by,
                        reason,
                    )
                else:
                    cursor = await conn.execute(
                        """
                        SELECT id, user_id, access_jti, refresh_jti, expires_at, refresh_expires_at
                        FROM sessions
                        WHERE id = ?
                        """,
                        (session_id,),
                    )
                    row = await cursor.fetchone()
                    if row:
                        session_details = {
                            "id": row[0],
                            "user_id": row[1],
                            "access_jti": row[2],
                            "refresh_jti": row[3],
                            "expires_at": row[4],
                            "refresh_expires_at": row[5],
                        }
                    await conn.execute(
                        """
                        UPDATE sessions
                        SET is_active = 0,
                            is_revoked = 1,
                            revoked_at = datetime('now'),
                            revoked_by = ?,
                            revoke_reason = ?
                        WHERE id = ?
                        """,
                        (revoked_by, reason, session_id),
                    )
                    try:
                        await conn.commit()
                    except Exception:
                        pass

                return session_details
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzSessionsRepo.revoke_session_record failed: {exc}")
            raise

    async def revoke_all_sessions_for_user(
        self,
        *,
        user_id: int,
        except_session_id: Optional[int] = None,
    ) -> int:
        """
        Mark all sessions for a user as revoked (optionally excluding one).

        Returns the approximate number of rows affected (best-effort).
        """
        try:
            async with self.db_pool.transaction() as conn:
                affected = 0
                if hasattr(conn, "fetchrow"):
                    if except_session_id:
                        result = await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = FALSE,
                                is_revoked = TRUE,
                                revoked_at = CURRENT_TIMESTAMP
                            WHERE user_id = $1 AND id != $2
                            """,
                            user_id,
                            except_session_id,
                        )
                    else:
                        result = await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = FALSE,
                                is_revoked = TRUE,
                                revoked_at = CURRENT_TIMESTAMP
                            WHERE user_id = $1
                            """,
                            user_id,
                        )
                    try:
                        affected = int(result.split()[-1]) if isinstance(result, str) else 0
                    except Exception:
                        affected = 0
                else:
                    if except_session_id:
                        cursor = await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = 0,
                                is_revoked = 1,
                                revoked_at = datetime('now')
                            WHERE user_id = ? AND id != ?
                            """,
                            (user_id, except_session_id),
                        )
                    else:
                        cursor = await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = 0,
                                is_revoked = 1,
                                revoked_at = datetime('now')
                            WHERE user_id = ?
                            """,
                            (user_id,),
                        )
                    try:
                        await conn.commit()
                    except Exception:
                        pass
                    affected = getattr(cursor, "rowcount", 0) or 0

                return int(affected)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzSessionsRepo.revoke_all_sessions_for_user failed: {exc}")
            raise

    async def get_active_sessions_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Return active sessions for a user, ordered by last activity.
        """
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                rows = await self.db_pool.fetch(
                    """
                    SELECT id, ip_address, user_agent, device_id,
                           created_at, last_activity, expires_at
                    FROM sessions
                    WHERE user_id = $1 AND is_active = TRUE
                    ORDER BY last_activity DESC
                    """,
                    user_id,
                )
                return [dict(r) for r in rows]

            # SQLite path
            async with self.db_pool.acquire() as conn:
                cursor = await conn.execute(
                    """
                    SELECT id, ip_address, user_agent, device_id,
                           created_at, last_activity, expires_at
                    FROM sessions
                    WHERE user_id = ? AND is_active = 1
                    ORDER BY last_activity DESC
                    """,
                    (user_id,),
                )
                rows = await cursor.fetchall()
                sessions: List[Dict[str, Any]] = []
                for row in rows:
                    sessions.append(
                        {
                            "id": row[0],
                            "ip_address": row[1],
                            "user_agent": row[2],
                            "device_id": row[3],
                            "created_at": row[4],
                            "last_activity": row[5],
                            "expires_at": row[6],
                        }
                    )
                return sessions
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzSessionsRepo.get_active_sessions_for_user failed: {exc}"
            )
            raise

    async def cleanup_expired_sessions(self) -> int:
        """
        Delete expired or long-revoked sessions.

        Returns the number of deleted rows (best-effort).
        """
        try:
            async with self.db_pool.transaction() as conn:
                # First check if the sessions table exists
                if hasattr(conn, "fetchval"):
                    table_exists = await conn.fetchval(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'sessions'
                        )
                        """
                    )
                else:
                    cursor = await conn.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='sessions'
                        """
                    )
                    result = await cursor.fetchone()
                    table_exists = result is not None

                if not table_exists:
                    logger.debug("Sessions table does not exist, skipping cleanup")
                    return 0

                deleted = 0
                if hasattr(conn, "fetchval"):
                    rows = await conn.fetch(
                        """
                        DELETE FROM sessions
                        WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day'
                        OR (is_active = FALSE AND revoked_at < CURRENT_TIMESTAMP - INTERVAL '7 days')
                        RETURNING id
                        """
                    )
                    deleted = len(rows or [])
                else:
                    cursor = await conn.execute(
                        """
                        DELETE FROM sessions
                        WHERE datetime(expires_at) < datetime('now', '-1 day')
                        OR (is_active = 0 AND datetime(revoked_at) < datetime('now', '-7 days'))
                        """
                    )
                    deleted = getattr(cursor, "rowcount", 0) or 0
                    try:
                        await conn.commit()
                    except Exception:
                        pass

                return int(deleted or 0)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzSessionsRepo.cleanup_expired_sessions failed: {exc}"
            )
            raise

    async def update_last_activity(self, session_id: int) -> None:
        """
        Best-effort last-activity update for a session.
        """
        try:
            async with self.db_pool.acquire() as conn:
                if hasattr(conn, "fetchrow"):
                    await conn.execute(
                        "UPDATE sessions SET last_activity = CURRENT_TIMESTAMP WHERE id = $1",
                        session_id,
                    )
                else:
                    await conn.execute(
                        "UPDATE sessions SET last_activity = datetime('now') WHERE id = ?",
                        (session_id,),
                    )
                    try:
                        await conn.commit()
                    except Exception:
                        pass
        except Exception:
            # Do not fail callers on activity update errors
            return

