from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


@dataclass
class AuthnzQuotasRepo:
    """
    Repository for AuthNZ virtual-key quota counters.

    This repo centralizes the cross-backend upsert logic for the
    ``vk_jwt_counters`` and ``vk_api_key_counters`` tables so that
    higher-level guardrail code does not embed dialect-specific SQL.
    """

    db_pool: DatabasePool

    def _is_postgres_backend(self) -> bool:
        """
        Return True when the underlying DatabasePool is using PostgreSQL.

        Backend selection should be derived from DatabasePool state instead of
        probing connection-method presence at runtime, which can misclassify
        shim/wrapper connections.
        """
        return bool(getattr(self.db_pool, "pool", None))

    async def ensure_schema(self) -> None:
        """
        Ensure the virtual-key counters tables exist for the current backend.

        This is a thin wrapper over the existing migration/bootstrap helpers:
        - SQLite: delegates to ``ensure_authnz_tables`` so that
          ``migration_023_create_virtual_key_counters`` is applied.
        - Postgres: delegates to ``ensure_virtual_key_counters_pg`` in
          ``pg_migrations_extra``.

        Callers SHOULD rely on this helper (or the higher-level schema
        bootstrap paths) instead of embedding new vk_* DDL.
        """
        try:
            if self._is_postgres_backend():
                from tldw_Server_API.app.core.AuthNZ.pg_migrations_extra import (
                    ensure_virtual_key_counters_pg,
                )

                await ensure_virtual_key_counters_pg(self.db_pool)
                return

            # SQLite backends use a filesystem path; let migrations own DDL.
            from pathlib import Path

            from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables

            db_fs_path = getattr(self.db_pool, "_sqlite_fs_path", None) or getattr(
                self.db_pool, "db_path", None
            )
            if db_fs_path:
                ensure_authnz_tables(Path(str(db_fs_path)))
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.debug(f"AuthnzQuotasRepo.ensure_schema skipped/failed: {exc}")

    async def increment_and_check_jwt_quota(
        self,
        *,
        jti: str,
        counter_type: str,
        limit: int | None,
        bucket: str | None = None,
    ) -> tuple[bool, int]:
        """
        Atomically increment the JWT quota counter for a given ``jti``
        and compare to ``limit``.

        Returns ``(allowed, new_count)``. When ``limit`` is ``None`` or
        ``jti`` is empty, this is treated as a no-op and ``(True, -1)``
        is returned. On error, the caller is expected to fall back to
        process-local counters and this method returns ``(True, -1)``.
        """
        if not jti or limit is None:
            return True, -1

        counter_key = f"{counter_type}@{bucket}" if bucket else str(counter_type)

        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres_backend():
                    # Postgres path – ON CONFLICT upsert with returning count
                    new_count = await conn.fetchval(
                        """
                        INSERT INTO vk_jwt_counters (jti, counter_type, count, updated_at)
                        VALUES ($1, $2, 1, CURRENT_TIMESTAMP)
                        ON CONFLICT (jti, counter_type)
                        DO UPDATE SET count = vk_jwt_counters.count + 1,
                                      updated_at = CURRENT_TIMESTAMP
                        RETURNING count
                        """,
                        jti,
                        counter_key,
                    )
                else:
                    # SQLite path – INSERT OR IGNORE + UPDATE + SELECT
                    now_iso = datetime.now(timezone.utc).isoformat()
                    await conn.execute(
                        """
                        INSERT OR IGNORE INTO vk_jwt_counters (jti, counter_type, count, updated_at)
                        VALUES (?, ?, 0, ?)
                        """,
                        (jti, counter_key, now_iso),
                    )
                    await conn.execute(
                        """
                        UPDATE vk_jwt_counters
                        SET count = count + 1, updated_at = ?
                        WHERE jti = ? AND counter_type = ?
                        """,
                        (now_iso, jti, counter_key),
                    )
                    cursor = await conn.execute(
                        """
                        SELECT count FROM vk_jwt_counters
                        WHERE jti = ? AND counter_type = ?
                        """,
                        (jti, counter_key),
                    )
                    row = await cursor.fetchone()
                    new_count = int(row[0]) if row else 0

            return (int(new_count) <= int(limit)), int(new_count)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.debug(
                f"AuthnzQuotasRepo.increment_and_check_jwt_quota failed; "
                f"falling back to process-local counters: {exc}"
            )
            return True, -1

    async def increment_and_check_api_key_quota(
        self,
        *,
        api_key_id: int,
        counter_type: str,
        limit: int | None,
        bucket: str | None = None,
    ) -> tuple[bool, int]:
        """
        Atomically increment the API-key quota counter for a given
        ``api_key_id`` and compare to ``limit``.

        Returns ``(allowed, new_count)``. When ``limit`` is ``None`` or
        ``api_key_id`` is ``None``, this is treated as a no-op and
        ``(True, -1)`` is returned. On error, the caller is expected to
        fall back to process-local counters and this method returns
        ``(True, -1)``.
        """
        if api_key_id is None or limit is None:
            return True, -1

        counter_key = f"{counter_type}@{bucket}" if bucket else str(counter_type)
        key_int = int(api_key_id)

        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres_backend():
                    # Postgres path – ON CONFLICT upsert with returning count
                    new_count = await conn.fetchval(
                        """
                        INSERT INTO vk_api_key_counters (api_key_id, counter_type, count, updated_at)
                        VALUES ($1, $2, 1, CURRENT_TIMESTAMP)
                        ON CONFLICT (api_key_id, counter_type)
                        DO UPDATE SET count = vk_api_key_counters.count + 1,
                                      updated_at = CURRENT_TIMESTAMP
                        RETURNING count
                        """,
                        key_int,
                        counter_key,
                    )
                else:
                    # SQLite path – INSERT OR IGNORE + UPDATE + SELECT
                    now_iso = datetime.now(timezone.utc).isoformat()
                    await conn.execute(
                        """
                        INSERT OR IGNORE INTO vk_api_key_counters (api_key_id, counter_type, count, updated_at)
                        VALUES (?, ?, 0, ?)
                        """,
                        (key_int, counter_key, now_iso),
                    )
                    await conn.execute(
                        """
                        UPDATE vk_api_key_counters
                        SET count = count + 1, updated_at = ?
                        WHERE api_key_id = ? AND counter_type = ?
                        """,
                        (now_iso, key_int, counter_key),
                    )
                    cursor = await conn.execute(
                        """
                        SELECT count FROM vk_api_key_counters
                        WHERE api_key_id = ? AND counter_type = ?
                        """,
                        (key_int, counter_key),
                    )
                    row = await cursor.fetchone()
                    new_count = int(row[0]) if row else 0

            return (int(new_count) <= int(limit)), int(new_count)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.debug(
                f"AuthnzQuotasRepo.increment_and_check_api_key_quota failed; "
                f"falling back to process-local counters: {exc}"
            )
            return True, -1
