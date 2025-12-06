from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


def _strip_tzinfo(dt: datetime) -> datetime:
    """Strip timezone info for PostgreSQL timestamp without timezone columns."""
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


@dataclass
class AuthnzTokenBlacklistRepo:
    """
    Repository for AuthNZ token blacklist persistence.

    This repo centralizes the DB interactions for the ``token_blacklist``
    table so higher-level services (TokenBlacklist, SessionManager) do not
    need to embed backend-specific SQL or DDL logic.
    """

    db_pool: DatabasePool

    async def insert_blacklisted_token(
        self,
        *,
        jti: str,
        user_id: Optional[int],
        token_type: str,
        expires_at: datetime,
        reason: Optional[str],
        revoked_by: Optional[int],
        ip_address: Optional[str],
    ) -> None:
        """
        Insert a blacklisted token row (or no-op on duplicate JTI).
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    exp = _strip_tzinfo(expires_at)
                    await conn.execute(
                        """
                        INSERT INTO token_blacklist
                        (jti, user_id, token_type, expires_at, reason, revoked_by, ip_address)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (jti) DO NOTHING
                        """,
                        jti,
                        user_id,
                        token_type,
                        exp,
                        reason,
                        revoked_by,
                        ip_address,
                    )
                else:
                    try:
                        await conn.execute(
                            """
                            INSERT OR IGNORE INTO token_blacklist
                            (jti, user_id, token_type, expires_at, reason, revoked_by, ip_address)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                jti,
                                user_id,
                                token_type,
                                expires_at.isoformat(),
                                reason,
                                revoked_by,
                                ip_address,
                            ),
                        )
                        try:
                            await conn.commit()
                        except Exception:
                            # Transaction shim may auto-commit; log at debug level
                            logger.debug(
                                "SQLite commit skipped (likely auto-committed by transaction shim)"
                            )
                    except Exception as sqlite_err:
                        if "FOREIGN KEY constraint failed" in str(sqlite_err):
                            logger.warning(
                                "FK constraint failed for user_id={} in token_blacklist; retrying with NULL user_id",
                                user_id,
                            )
                            try:
                                await conn.execute(
                                    """
                                    INSERT OR IGNORE INTO token_blacklist
                                    (jti, user_id, token_type, expires_at, reason, revoked_by, ip_address)
                                    VALUES (?, NULL, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        jti,
                                        token_type,
                                        expires_at.isoformat(),
                                        reason,
                                        revoked_by,
                                        ip_address,
                                    ),
                                )
                                try:
                                    await conn.commit()
                                except Exception:
                                    logger.debug(
                                        "SQLite commit skipped (likely auto-committed)"
                                    )
                            except Exception as inner_exc:
                                logger.error(
                                    "Retry insert with NULL user_id failed: {}", inner_exc
                                )
                                raise
                        else:
                            raise
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzTokenBlacklistRepo.insert_blacklisted_token failed: {exc}"
            )
            raise

    async def get_active_expiry_for_jti(
        self, jti: str, now: datetime
    ) -> Optional[datetime]:
        """
        Return the latest non-expired ``expires_at`` for a given JTI, or None.
        """
        try:
            async with self.db_pool.acquire() as conn:
                if hasattr(conn, "fetchrow"):
                    now_param = _strip_tzinfo(now)
                    row = await conn.fetchrow(
                        """
                        SELECT expires_at
                        FROM token_blacklist
                        WHERE jti = $1 AND expires_at > $2
                        ORDER BY expires_at DESC
                        LIMIT 1
                        """,
                        jti,
                        now_param,
                    )
                    return row["expires_at"] if row else None

                cursor = await conn.execute(
                    """
                    SELECT expires_at
                    FROM token_blacklist
                    WHERE jti = ? AND expires_at > ?
                    ORDER BY expires_at DESC
                    LIMIT 1
                    """,
                    (jti, now.isoformat()),
                )
                result = await cursor.fetchone()
                return result[0] if result else None
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzTokenBlacklistRepo.get_active_expiry_for_jti failed: {exc}"
            )
            raise

    async def cleanup_expired(self, now: datetime) -> int:
        """
        Delete expired blacklist rows and return the approximate count.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    now_param = _strip_tzinfo(now)
                    result = await conn.execute(
                        "DELETE FROM token_blacklist WHERE expires_at < $1",
                        now_param,
                    )
                    try:
                        # asyncpg returns status like "DELETE N"
                        if isinstance(result, str) and result.startswith("DELETE"):
                            return int(result.split()[-1])
                        return 0
                    except (ValueError, IndexError) as parse_err:
                        logger.debug(
                            "Could not parse DELETE result '{}': {}", result, parse_err
                        )
                        return 0

                cursor = await conn.execute(
                    "DELETE FROM token_blacklist WHERE expires_at < ?",
                    (now.isoformat(),),
                )
                deleted = getattr(cursor, "rowcount", 0) or 0
                try:
                    await conn.commit()
                except Exception:
                    logger.debug(
                        "SQLite commit skipped (likely auto-committed by transaction shim)"
                    )
                return int(deleted)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzTokenBlacklistRepo.cleanup_expired failed: {exc}"
            )
            raise

    async def get_blacklist_stats(
        self,
        *,
        now: datetime,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Return blacklist statistics for all users or a single user.
        """
        try:
            async with self.db_pool.acquire() as conn:
                now_param = _strip_tzinfo(now)
                if user_id:
                    if hasattr(conn, "fetchrow"):
                        row = await conn.fetchrow(
                            """
                            SELECT
                                COUNT(*) as total,
                                SUM(CASE WHEN token_type = 'access' THEN 1 ELSE 0 END) as access_tokens,
                                SUM(CASE WHEN token_type = 'refresh' THEN 1 ELSE 0 END) as refresh_tokens,
                                MIN(revoked_at) as earliest_revocation,
                                MAX(revoked_at) as latest_revocation
                            FROM token_blacklist
                            WHERE user_id = $1 AND expires_at > $2
                            """,
                            user_id,
                            now_param,
                        )
                    else:
                        cursor = await conn.execute(
                            """
                            SELECT
                                COUNT(*) as total,
                                SUM(CASE WHEN token_type = 'access' THEN 1 ELSE 0 END) as access_tokens,
                                SUM(CASE WHEN token_type = 'refresh' THEN 1 ELSE 0 END) as refresh_tokens,
                                MIN(revoked_at) as earliest_revocation,
                                MAX(revoked_at) as latest_revocation
                            FROM token_blacklist
                            WHERE user_id = ? AND expires_at > ?
                            """,
                            (user_id, now.isoformat()),
                        )
                        row = await cursor.fetchone()
                else:
                    if hasattr(conn, "fetchrow"):
                        row = await conn.fetchrow(
                            """
                            SELECT
                                COUNT(*) as total,
                                COUNT(DISTINCT user_id) as unique_users,
                                SUM(CASE WHEN token_type = 'access' THEN 1 ELSE 0 END) as access_tokens,
                                SUM(CASE WHEN token_type = 'refresh' THEN 1 ELSE 0 END) as refresh_tokens
                            FROM token_blacklist
                            WHERE expires_at > $1
                            """,
                            now_param,
                        )
                    else:
                        cursor = await conn.execute(
                            """
                            SELECT
                                COUNT(*) as total,
                                COUNT(DISTINCT user_id) as unique_users,
                                SUM(CASE WHEN token_type = 'access' THEN 1 ELSE 0 END) as access_tokens,
                                SUM(CASE WHEN token_type = 'refresh' THEN 1 ELSE 0 END) as refresh_tokens
                            FROM token_blacklist
                            WHERE expires_at > ?
                            """,
                            (now.isoformat(),),
                        )
                        row = await cursor.fetchone()

                if not row:
                    return {
                        "total": 0,
                        "unique_users": 0 if user_id is None else 1,
                        "access_tokens": 0,
                        "refresh_tokens": 0,
                    }

                if hasattr(row, "keys"):
                    stats: Dict[str, Any] = dict(row)
                else:
                    if user_id:
                        stats = {
                            "total": row[0],
                            "access_tokens": row[1],
                            "refresh_tokens": row[2],
                            "earliest_revocation": row[3],
                            "latest_revocation": row[4],
                        }
                    else:
                        stats = {
                            "total": row[0],
                            "unique_users": row[1],
                            "access_tokens": row[2],
                            "refresh_tokens": row[3],
                        }
                if user_id is not None:
                    stats.setdefault("unique_users", 1 if stats.get("total") else 0)
                else:
                    stats.setdefault("unique_users", 0)
                stats.setdefault("access_tokens", 0)
                stats.setdefault("refresh_tokens", 0)
                return stats
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzTokenBlacklistRepo.get_blacklist_stats failed: {exc}"
            )
            raise
