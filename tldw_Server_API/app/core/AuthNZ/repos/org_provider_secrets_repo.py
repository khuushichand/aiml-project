from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import normalize_provider_name


def _normalize_scope_type(scope_type: str) -> str:
    st = (scope_type or "").strip().lower()
    if st in {"org", "organization", "orgs"}:
        return "org"
    if st in {"team", "teams"}:
        return "team"
    raise ValueError(f"Invalid scope_type: {scope_type}")


@dataclass
class AuthnzOrgProviderSecretsRepo:
    """Repository for org/team shared provider secrets (BYOK)."""

    db_pool: DatabasePool

    async def ensure_tables(self) -> None:
        """Ensure org_provider_secrets schema exists."""
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                from tldw_Server_API.app.core.AuthNZ.pg_migrations_extra import (
                    ensure_org_provider_secrets_pg,
                )

                ok = await ensure_org_provider_secrets_pg(self.db_pool)
                if not ok:
                    raise RuntimeError("PostgreSQL org_provider_secrets schema ensure failed")
                return

            row = await self.db_pool.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='org_provider_secrets'"
            )
            if not row:
                raise RuntimeError(
                    "SQLite org_provider_secrets table is missing. "
                    "Run the AuthNZ migrations/bootstrap (see "
                    "'python -m tldw_Server_API.app.core.AuthNZ.initialize')."
                )
        except Exception as exc:
            logger.error(f"AuthnzOrgProviderSecretsRepo.ensure_tables failed: {exc}")
            raise

    @staticmethod
    def _normalize_datetime_for_postgres(dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt

    async def upsert_secret(
        self,
        *,
        scope_type: str,
        scope_id: int,
        provider: str,
        encrypted_blob: str,
        key_hint: Optional[str],
        metadata: Optional[Dict[str, Any]],
        updated_at: datetime,
    ) -> Dict[str, Any]:
        scope_norm = _normalize_scope_type(scope_type)
        provider_norm = normalize_provider_name(provider)
        metadata_json = json.dumps(metadata) if metadata is not None else None
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                ts = self._normalize_datetime_for_postgres(updated_at)
                row = await self.db_pool.fetchone(
                    """
                    INSERT INTO org_provider_secrets (
                        scope_type, scope_id, provider, encrypted_blob, key_hint, metadata, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
                    ON CONFLICT (scope_type, scope_id, provider) DO UPDATE SET
                        encrypted_blob = EXCLUDED.encrypted_blob,
                        key_hint = EXCLUDED.key_hint,
                        metadata = EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id, scope_type, scope_id, provider, key_hint, metadata, created_at, updated_at, last_used_at
                    """,
                    scope_norm,
                    int(scope_id),
                    provider_norm,
                    encrypted_blob,
                    key_hint,
                    metadata_json,
                    ts,
                )
                return dict(row) if row else {}

            await self.db_pool.execute(
                """
                INSERT INTO org_provider_secrets (
                    scope_type, scope_id, provider, encrypted_blob, key_hint, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope_type, scope_id, provider) DO UPDATE SET
                    encrypted_blob = excluded.encrypted_blob,
                    key_hint = excluded.key_hint,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
                """,
                (
                    scope_norm,
                    int(scope_id),
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
                SELECT id, scope_type, scope_id, provider, key_hint, metadata, created_at, updated_at, last_used_at
                FROM org_provider_secrets
                WHERE scope_type = ? AND scope_id = ? AND provider = ?
                """,
                (scope_norm, int(scope_id), provider_norm),
            )
            return dict(row) if row else {}
        except Exception as exc:
            logger.error(f"AuthnzOrgProviderSecretsRepo.upsert_secret failed: {exc}")
            raise

    async def fetch_secret(self, scope_type: str, scope_id: int, provider: str) -> Optional[Dict[str, Any]]:
        scope_norm = _normalize_scope_type(scope_type)
        provider_norm = normalize_provider_name(provider)
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                row = await self.db_pool.fetchone(
                    """
                    SELECT id, scope_type, scope_id, provider, encrypted_blob, key_hint, metadata,
                           created_at, updated_at, last_used_at
                    FROM org_provider_secrets
                    WHERE scope_type = $1 AND scope_id = $2 AND provider = $3
                    """,
                    scope_norm,
                    int(scope_id),
                    provider_norm,
                )
            else:
                row = await self.db_pool.fetchone(
                    """
                    SELECT id, scope_type, scope_id, provider, encrypted_blob, key_hint, metadata,
                           created_at, updated_at, last_used_at
                    FROM org_provider_secrets
                    WHERE scope_type = ? AND scope_id = ? AND provider = ?
                    """,
                    (scope_norm, int(scope_id), provider_norm),
                )
            return dict(row) if row else None
        except Exception as exc:
            logger.error(f"AuthnzOrgProviderSecretsRepo.fetch_secret failed: {exc}")
            raise

    async def list_secrets(
        self,
        *,
        scope_type: Optional[str] = None,
        scope_id: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if scope_id is not None and not scope_type:
            raise ValueError("scope_type is required when scope_id is provided")

        scope_norm = _normalize_scope_type(scope_type) if scope_type else None
        provider_norm = normalize_provider_name(provider) if provider else None

        try:
            if getattr(self.db_pool, "pool", None) is not None:
                clauses = []
                params: List[Any] = []
                idx = 1
                if scope_norm:
                    clauses.append(f"scope_type = ${idx}")
                    params.append(scope_norm)
                    idx += 1
                if scope_id is not None:
                    clauses.append(f"scope_id = ${idx}")
                    params.append(int(scope_id))
                    idx += 1
                if provider_norm:
                    clauses.append(f"provider = ${idx}")
                    params.append(provider_norm)
                    idx += 1
                where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
                rows = await self.db_pool.fetchall(
                    f"""
                    SELECT id, scope_type, scope_id, provider, key_hint, metadata, created_at, updated_at, last_used_at
                    FROM org_provider_secrets
                    {where}
                    ORDER BY scope_type, scope_id, provider
                    """,
                    *params,
                )
            else:
                clauses = []
                params = []
                if scope_norm:
                    clauses.append("scope_type = ?")
                    params.append(scope_norm)
                if scope_id is not None:
                    clauses.append("scope_id = ?")
                    params.append(int(scope_id))
                if provider_norm:
                    clauses.append("provider = ?")
                    params.append(provider_norm)
                where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
                rows = await self.db_pool.fetchall(
                    f"""
                    SELECT id, scope_type, scope_id, provider, key_hint, metadata, created_at, updated_at, last_used_at
                    FROM org_provider_secrets
                    {where}
                    ORDER BY scope_type, scope_id, provider
                    """,
                    tuple(params),
                )

            return [dict(row) if isinstance(row, dict) else {k: row[k] for k in row.keys()} for row in rows]
        except Exception as exc:
            logger.error(f"AuthnzOrgProviderSecretsRepo.list_secrets failed: {exc}")
            raise

    async def delete_secret(self, scope_type: str, scope_id: int, provider: str) -> bool:
        scope_norm = _normalize_scope_type(scope_type)
        provider_norm = normalize_provider_name(provider)
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                result = await self.db_pool.execute(
                    "DELETE FROM org_provider_secrets WHERE scope_type = $1 AND scope_id = $2 AND provider = $3",
                    scope_norm,
                    int(scope_id),
                    provider_norm,
                )
                if isinstance(result, str):
                    parts = result.split()
                    if parts and parts[-1].isdigit():
                        return int(parts[-1]) > 0
                return True

            cursor = await self.db_pool.execute(
                "DELETE FROM org_provider_secrets WHERE scope_type = ? AND scope_id = ? AND provider = ?",
                (scope_norm, int(scope_id), provider_norm),
            )
            rowcount = getattr(cursor, "rowcount", 0)
            return rowcount > 0
        except Exception as exc:
            logger.error(f"AuthnzOrgProviderSecretsRepo.delete_secret failed: {exc}")
            raise

    async def touch_last_used(self, scope_type: str, scope_id: int, provider: str, used_at: datetime) -> None:
        scope_norm = _normalize_scope_type(scope_type)
        provider_norm = normalize_provider_name(provider)
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                ts = self._normalize_datetime_for_postgres(used_at)
                await self.db_pool.execute(
                    """
                    UPDATE org_provider_secrets
                    SET last_used_at = $1, updated_at = $1
                    WHERE scope_type = $2 AND scope_id = $3 AND provider = $4
                    """,
                    ts,
                    scope_norm,
                    int(scope_id),
                    provider_norm,
                )
                return

            await self.db_pool.execute(
                """
                UPDATE org_provider_secrets
                SET last_used_at = ?, updated_at = ?
                WHERE scope_type = ? AND scope_id = ? AND provider = ?
                """,
                (used_at.isoformat(), used_at.isoformat(), scope_norm, int(scope_id), provider_norm),
            )
        except Exception as exc:
            logger.error(f"AuthnzOrgProviderSecretsRepo.touch_last_used failed: {exc}")
            raise
