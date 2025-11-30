from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


@dataclass
class AuthnzApiKeysRepo:
    """
    Repository for AuthNZ API key storage.

    This class centralizes the core queries for the ``api_keys`` table
    so callers do not need to worry about PostgreSQL vs SQLite dialect
    differences. It is intentionally small; additional helpers can be
    added incrementally as more modules adopt the repository layer.
    """

    db_pool: DatabasePool

    async def fetch_active_by_hash_candidates(
        self,
        hash_candidates: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch the most recent active API key whose hash matches any of the
        provided candidates.

        The query mirrors the lookup used by APIKeyManager.validate_api_key,
        but is encapsulated here to avoid duplicating dialect-specific SQL.
        """
        if not hash_candidates:
            return None

        try:
            # PostgreSQL path: use ANY($1::text[]) for hash candidate list
            if getattr(self.db_pool, "pool", None) is not None:
                row = await self.db_pool.fetchone(
                    """
                    SELECT id, user_id, name, scope, status, expires_at,
                           rate_limit, allowed_ips, usage_count, key_hash,
                           COALESCE(is_virtual, FALSE) AS is_virtual,
                           parent_key_id, org_id, team_id,
                           llm_budget_day_tokens, llm_budget_month_tokens,
                           llm_budget_day_usd, llm_budget_month_usd,
                           llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models,
                           metadata
                    FROM api_keys
                    WHERE key_hash = ANY($1::text[]) AND status = $2
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    hash_candidates,
                    "active",
                )
            else:
                # SQLite path: emulate ANY with an IN (...) clause
                placeholders = ",".join("?" for _ in hash_candidates)
                query = f"""
                    SELECT id, user_id, name, scope, status, expires_at,
                           rate_limit, allowed_ips, usage_count, key_hash,
                           COALESCE(is_virtual, 0) AS is_virtual,
                           parent_key_id, org_id, team_id,
                           llm_budget_day_tokens, llm_budget_month_tokens,
                           llm_budget_day_usd, llm_budget_month_usd,
                           llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models,
                           metadata
                    FROM api_keys
                    WHERE key_hash IN ({placeholders}) AND status = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                params = (*hash_candidates, "active")
                row = await self.db_pool.fetchone(query, params)

            if not row:
                return None

            return dict(row)
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.fetch_active_by_hash_candidates failed: {exc}")
            raise

    async def upsert_primary_key(
        self,
        *,
        user_id: int,
        key_hash: str,
        key_prefix: str,
        name: str,
        description: str,
        scope: str,
        is_virtual: bool = False,
    ) -> None:
        """
        Upsert a primary API key row for the given user and hash.

        This mirrors the bootstrap logic for the single-user primary key,
        but is backend-agnostic and safe to call repeatedly.
        """
        async with self.db_pool.transaction() as conn:
            try:
                if hasattr(conn, "fetchval"):
                    # PostgreSQL: upsert on key_hash
                    await conn.execute(
                        """
                        INSERT INTO api_keys (
                            user_id, key_hash, key_prefix, name, description,
                            scope, status, is_virtual
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, 'active', $7)
                        ON CONFLICT (key_hash) DO UPDATE SET
                            user_id = EXCLUDED.user_id,
                            key_prefix = EXCLUDED.key_prefix,
                            scope = EXCLUDED.scope,
                            status = EXCLUDED.status,
                            is_virtual = EXCLUDED.is_virtual
                        """,
                        user_id,
                        key_hash,
                        key_prefix,
                        name,
                        description,
                        scope,
                        bool(is_virtual),
                    )
                else:
                    # SQLite: emulate upsert by key_hash
                    await conn.execute(
                        """
                        INSERT OR REPLACE INTO api_keys (
                            id, user_id, key_hash, key_prefix, name, description,
                            scope, status, is_virtual
                        )
                        VALUES (
                            COALESCE(
                                (SELECT id FROM api_keys WHERE key_hash = ?),
                                COALESCE((SELECT MAX(id) FROM api_keys), 0) + 1
                            ),
                            ?, ?, ?, ?, ?, ?, 'active', ?
                        )
                        """,
                        (
                            key_hash,
                            user_id,
                            key_hash,
                            key_prefix,
                            name,
                            description,
                            scope,
                            1 if is_virtual else 0,
                        ),
                    )
                if hasattr(conn, "commit"):
                    await conn.commit()  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover - surfaced via higher layers
                logger.error(f"AuthnzApiKeysRepo.upsert_primary_key failed: {exc}")
                raise

    async def list_user_keys(
        self,
        *,
        user_id: int,
        include_revoked: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List API keys for a given user.

        This returns raw rows (including ``key_hash``); callers decide which
        fields to expose externally.
        """
        try:
            if include_revoked:
                query = """
                    SELECT * FROM api_keys
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                """
                rows = await self.db_pool.fetchall(query, user_id)
            else:
                query = """
                    SELECT * FROM api_keys
                    WHERE user_id = ? AND status = ?
                    ORDER BY created_at DESC
                """
                rows = await self.db_pool.fetchall(query, user_id, "active")

            return [dict(row) for row in rows]
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.list_user_keys failed: {exc}")
            raise
