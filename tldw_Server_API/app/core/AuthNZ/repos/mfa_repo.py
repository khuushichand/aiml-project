from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.exceptions import UserNotFoundError


@dataclass
class AuthnzMfaRepo:
    """
    Repository for MFA-related fields stored on the ``users`` table.

    This repo centralizes the small set of reads and updates used by
    ``MFAService`` so that backend-specific SQL for PostgreSQL vs SQLite
    is not embedded directly in the service logic.
    """

    db_pool: DatabasePool

    @staticmethod
    def _is_postgres(conn: Any) -> bool:
        """Return True when the underlying connection is PostgreSQL (asyncpg-style)."""
        return hasattr(conn, "fetchrow")

    @staticmethod
    def _normalize_datetime_for_postgres(dt: datetime) -> datetime:
        """Strip timezone info for PostgreSQL TIMESTAMP columns."""
        return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt

    @staticmethod
    def _assert_user_row_updated(result: Any, user_id: int, *, operation: str) -> None:
        """
        Ensure an UPDATE affected at least one row; raise if the user is missing.

        For PostgreSQL (asyncpg), ``result`` is a status string like ``\"UPDATE 1\"``.
        For SQLite (aiosqlite), ``result`` is a cursor with a ``rowcount`` attribute.
        """
        try:
            # asyncpg status string: e.g. "UPDATE 0", "UPDATE 1"
            if isinstance(result, str):
                parts = result.split()
                if parts and parts[-1].isdigit():
                    if int(parts[-1]) == 0:
                        msg = f"User {user_id} not found during {operation}"
                        logger.warning(msg)
                        raise UserNotFoundError(msg)
                return

            # aiosqlite cursor-style result
            rowcount = getattr(result, "rowcount", None)
            if rowcount == 0:
                msg = f"User {user_id} not found during {operation}"
                logger.warning(msg)
                raise UserNotFoundError(msg)
        except UserNotFoundError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            # Introspection failures must not hide the underlying DB behavior.
            logger.debug(f"AuthnzMfaRepo._assert_user_row_updated introspection failed: {exc}")

    async def set_mfa_config(
        self,
        *,
        user_id: int,
        encrypted_secret: str,
        backup_codes_json: str,
        updated_at: datetime,
    ) -> None:
        """
        Enable MFA for a user by updating the TOTP secret, backup codes,
        and two-factor flag.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres(conn):
                    ts = self._normalize_datetime_for_postgres(updated_at)
                    result = await conn.execute(
                        """
                        UPDATE users
                        SET totp_secret = $1,
                            two_factor_enabled = TRUE,
                            backup_codes = $2,
                            updated_at = $3
                        WHERE id = $4
                        """,
                        encrypted_secret,
                        backup_codes_json,
                        ts,
                        user_id,
                    )
                else:
                    result = await conn.execute(
                        """
                        UPDATE users
                        SET totp_secret = ?,
                            two_factor_enabled = 1,
                            backup_codes = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            encrypted_secret,
                            backup_codes_json,
                            updated_at.isoformat(),
                            user_id,
                        ),
                    )
                self._assert_user_row_updated(result, user_id, operation="set_mfa_config")
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzMfaRepo.set_mfa_config failed: {exc}")
            raise

    async def clear_mfa_config(
        self,
        *,
        user_id: int,
        updated_at: datetime,
    ) -> None:
        """
        Disable MFA for a user and clear secret/backup codes.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres(conn):
                    ts = self._normalize_datetime_for_postgres(updated_at)
                    result = await conn.execute(
                        """
                        UPDATE users
                        SET totp_secret = NULL,
                            two_factor_enabled = FALSE,
                            backup_codes = NULL,
                            updated_at = $1
                        WHERE id = $2
                        """,
                        ts,
                        user_id,
                    )
                else:
                    result = await conn.execute(
                        """
                        UPDATE users
                        SET totp_secret = NULL,
                            two_factor_enabled = 0,
                            backup_codes = NULL,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (updated_at.isoformat(), user_id),
                    )
                self._assert_user_row_updated(result, user_id, operation="clear_mfa_config")
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzMfaRepo.clear_mfa_config failed: {exc}")
            raise

    async def get_encrypted_totp_secret(self, user_id: int) -> Optional[str]:
        """
        Return the encrypted TOTP secret for a user, if present.
        """
        try:
            async with self.db_pool.acquire() as conn:
                if self._is_postgres(conn):
                    encrypted = await conn.fetchval(
                        "SELECT totp_secret FROM users WHERE id = $1",
                        user_id,
                    )
                else:
                    cursor = await conn.execute(
                        "SELECT totp_secret FROM users WHERE id = ?",
                        (user_id,),
                    )
                    row = await cursor.fetchone()
                    encrypted = row[0] if row else None
            return encrypted
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzMfaRepo.get_encrypted_totp_secret failed for user {user_id}: {exc}"
            )
            raise

    async def get_mfa_status_row(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch raw MFA status fields for a user.

        Returns a mapping with keys:
        - ``two_factor_enabled``
        - ``has_secret``
        - ``has_backup_codes``
        or ``None`` if the user row does not exist.
        """
        try:
            async with self.db_pool.acquire() as conn:
                if self._is_postgres(conn):
                    row = await conn.fetchrow(
                        """
                        SELECT two_factor_enabled,
                               totp_secret IS NOT NULL AS has_secret,
                               backup_codes IS NOT NULL AS has_backup_codes
                        FROM users
                        WHERE id = $1
                        """,
                        user_id,
                    )
                    return dict(row) if row else None

                cursor = await conn.execute(
                    """
                    SELECT two_factor_enabled,
                           totp_secret IS NOT NULL AS has_secret,
                           backup_codes IS NOT NULL AS has_backup_codes
                    FROM users
                    WHERE id = ?
                    """,
                    (user_id,),
                )
                row = await cursor.fetchone()
                if not row:
                    return None
                return {
                    "two_factor_enabled": row[0],
                    "has_secret": row[1],
                    "has_backup_codes": row[2],
                }
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzMfaRepo.get_mfa_status_row failed for user {user_id}: {exc}"
            )
            raise

    async def get_backup_codes_json(self, user_id: int) -> Optional[str]:
        """
        Return the raw ``backup_codes`` JSON for a user, if present.
        """
        try:
            async with self.db_pool.acquire() as conn:
                if self._is_postgres(conn):
                    value = await conn.fetchval(
                        "SELECT backup_codes FROM users WHERE id = $1",
                        user_id,
                    )
                else:
                    cursor = await conn.execute(
                        "SELECT backup_codes FROM users WHERE id = ?",
                        (user_id,),
                    )
                    row = await cursor.fetchone()
                    value = row[0] if row else None
            return value
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzMfaRepo.get_backup_codes_json failed for user {user_id}: {exc}"
            )
            raise

    async def update_backup_codes_json(
        self,
        *,
        user_id: int,
        backup_codes_json: str,
    ) -> None:
        """
        Persist an updated ``backup_codes`` JSON payload for a user.

        This mirrors the semantics used when consuming a single backup code
        during verification and intentionally does not modify ``updated_at``.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres(conn):
                    result = await conn.execute(
                        "UPDATE users SET backup_codes = $1 WHERE id = $2",
                        backup_codes_json,
                        user_id,
                    )
                else:
                    result = await conn.execute(
                        "UPDATE users SET backup_codes = ? WHERE id = ?",
                        (backup_codes_json, user_id),
                    )
                self._assert_user_row_updated(result, user_id, operation="update_backup_codes_json")
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzMfaRepo.update_backup_codes_json failed for user {user_id}: {exc}"
            )
            raise

    async def set_backup_codes_with_timestamp(
        self,
        *,
        user_id: int,
        backup_codes_json: str,
        updated_at: datetime,
    ) -> None:
        """
        Set ``backup_codes`` and bump ``updated_at`` for a user.

        Used when regenerating backup codes so callers can distinguish
        the refresh event in audit-style views.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres(conn):
                    ts = self._normalize_datetime_for_postgres(updated_at)
                    result = await conn.execute(
                        "UPDATE users SET backup_codes = $1, updated_at = $2 WHERE id = $3",
                        backup_codes_json,
                        ts,
                        user_id,
                    )
                else:
                    result = await conn.execute(
                        "UPDATE users SET backup_codes = ?, updated_at = ? WHERE id = ?",
                        (backup_codes_json, updated_at.isoformat(), user_id),
                    )
                self._assert_user_row_updated(result, user_id, operation="set_backup_codes_with_timestamp")
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzMfaRepo.set_backup_codes_with_timestamp failed for user {user_id}: {exc}"
            )
            raise
