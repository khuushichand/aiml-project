from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import normalize_provider_name


@dataclass
class AuthnzUserProviderSecretsRepo:
    """Repository for per-user provider secrets (BYOK)."""

    db_pool: DatabasePool

    async def ensure_tables(self) -> None:
        """Ensure user_provider_secrets schema exists."""
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                from tldw_Server_API.app.core.AuthNZ.pg_migrations_extra import (
                    ensure_user_provider_secrets_pg,
                )

                ok = await ensure_user_provider_secrets_pg(self.db_pool)
                if not ok:
                    raise RuntimeError("PostgreSQL user_provider_secrets schema ensure failed")
                return

            row = await self.db_pool.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_provider_secrets'"
            )
            if not row:
                raise RuntimeError(
                    "SQLite user_provider_secrets table is missing. "
                    "Run the AuthNZ migrations/bootstrap (see "
                    "'python -m tldw_Server_API.app.core.AuthNZ.initialize')."
                )
        except Exception as exc:
            logger.error(f"AuthnzUserProviderSecretsRepo.ensure_tables failed: {exc}")
            raise

    @staticmethod
    def _normalize_datetime_for_postgres(dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt

    async def upsert_secret(
        self,
        *,
        user_id: int,
        provider: str,
        encrypted_blob: str,
        key_hint: Optional[str],
        metadata: Optional[Dict[str, Any]],
        updated_at: datetime,
    ) -> Dict[str, Any]:
        provider_norm = normalize_provider_name(provider)
        metadata_json = json.dumps(metadata) if metadata is not None else None
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                ts = self._normalize_datetime_for_postgres(updated_at)
                row = await self.db_pool.fetchone(
                    """
                    INSERT INTO user_provider_secrets (
                        user_id, provider, encrypted_blob, key_hint, metadata, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $6)
                    ON CONFLICT (user_id, provider) DO UPDATE SET
                        encrypted_blob = EXCLUDED.encrypted_blob,
                        key_hint = EXCLUDED.key_hint,
                        metadata = EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id, user_id, provider, key_hint, metadata, created_at, updated_at, last_used_at
                    """,
                    user_id,
                    provider_norm,
                    encrypted_blob,
                    key_hint,
                    metadata_json,
                    ts,
                )
                return dict(row) if row else {}

            await self.db_pool.execute(
                """
                INSERT INTO user_provider_secrets (
                    user_id, provider, encrypted_blob, key_hint, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, provider) DO UPDATE SET
                    encrypted_blob = excluded.encrypted_blob,
                    key_hint = excluded.key_hint,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    provider_norm,
                    encrypted_blob,
                    key_hint,
                    metadata_json,
                    updated_at.isoformat(),
                    updated_at.isoformat(),
                ),
            )
            row = await self.db_pool.fetchone(
                """
                SELECT id, user_id, provider, key_hint, metadata, created_at, updated_at, last_used_at
                FROM user_provider_secrets
                WHERE user_id = ? AND provider = ?
                """,
                (user_id, provider_norm),
            )
            return dict(row) if row else {}
        except Exception as exc:
            logger.error(f"AuthnzUserProviderSecretsRepo.upsert_secret failed: {exc}")
            raise

    async def fetch_secret_for_user(self, user_id: int, provider: str) -> Optional[Dict[str, Any]]:
        provider_norm = normalize_provider_name(provider)
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                row = await self.db_pool.fetchone(
                    """
                    SELECT id, user_id, provider, encrypted_blob, key_hint, metadata,
                           created_at, updated_at, last_used_at
                    FROM user_provider_secrets
                    WHERE user_id = $1 AND provider = $2
                    """,
                    user_id,
                    provider_norm,
                )
            else:
                row = await self.db_pool.fetchone(
                    """
                    SELECT id, user_id, provider, encrypted_blob, key_hint, metadata,
                           created_at, updated_at, last_used_at
                    FROM user_provider_secrets
                    WHERE user_id = ? AND provider = ?
                    """,
                    (user_id, provider_norm),
                )
            return dict(row) if row else None
        except Exception as exc:
            logger.error(f"AuthnzUserProviderSecretsRepo.fetch_secret_for_user failed: {exc}")
            raise

    async def list_secrets_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                rows = await self.db_pool.fetchall(
                    """
                    SELECT id, user_id, provider, key_hint, metadata, created_at, updated_at, last_used_at
                    FROM user_provider_secrets
                    WHERE user_id = $1
                    ORDER BY provider
                    """,
                    user_id,
                )
            else:
                rows = await self.db_pool.fetchall(
                    """
                    SELECT id, user_id, provider, key_hint, metadata, created_at, updated_at, last_used_at
                    FROM user_provider_secrets
                    WHERE user_id = ?
                    ORDER BY provider
                    """,
                    (user_id,),
                )
            return [dict(row) if isinstance(row, dict) else {k: row[k] for k in row.keys()} for row in rows]
        except Exception as exc:
            logger.error(f"AuthnzUserProviderSecretsRepo.list_secrets_for_user failed: {exc}")
            raise

    async def delete_secret(self, user_id: int, provider: str) -> bool:
        provider_norm = normalize_provider_name(provider)
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                result = await self.db_pool.execute(
                    "DELETE FROM user_provider_secrets WHERE user_id = $1 AND provider = $2",
                    user_id,
                    provider_norm,
                )
                if isinstance(result, str):
                    parts = result.split()
                    if parts and parts[-1].isdigit():
                        return int(parts[-1]) > 0
                return True

            cursor = await self.db_pool.execute(
                "DELETE FROM user_provider_secrets WHERE user_id = ? AND provider = ?",
                (user_id, provider_norm),
            )
            rowcount = getattr(cursor, "rowcount", 0)
            return rowcount > 0
        except Exception as exc:
            logger.error(f"AuthnzUserProviderSecretsRepo.delete_secret failed: {exc}")
            raise

    async def touch_last_used(self, user_id: int, provider: str, used_at: datetime) -> None:
        provider_norm = normalize_provider_name(provider)
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                ts = self._normalize_datetime_for_postgres(used_at)
                await self.db_pool.execute(
                    """
                    UPDATE user_provider_secrets
                    SET last_used_at = $1, updated_at = $1
                    WHERE user_id = $2 AND provider = $3
                    """,
                    ts,
                    user_id,
                    provider_norm,
                )
                return

            await self.db_pool.execute(
                """
                UPDATE user_provider_secrets
                SET last_used_at = ?, updated_at = ?
                WHERE user_id = ? AND provider = ?
                """,
                (used_at.isoformat(), used_at.isoformat(), user_id, provider_norm),
            )
        except Exception as exc:
            logger.error(f"AuthnzUserProviderSecretsRepo.touch_last_used failed: {exc}")
            raise
