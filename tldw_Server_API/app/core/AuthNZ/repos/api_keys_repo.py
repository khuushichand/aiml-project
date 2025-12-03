from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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

    async def fetch_key_limits(
        self,
        key_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch LLM budget and org/team limit fields for a specific API key.

        This mirrors the select used by the virtual-keys budget helpers while
        encapsulating PostgreSQL vs SQLite differences in one place.
        """
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                # PostgreSQL: use BOOL-aware COALESCE for is_virtual
                row = await self.db_pool.fetchone(
                    """
                    SELECT id,
                           COALESCE(is_virtual, FALSE) AS is_virtual,
                           org_id, team_id,
                           llm_budget_day_tokens, llm_budget_month_tokens,
                           llm_budget_day_usd, llm_budget_month_usd,
                           llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models
                    FROM api_keys
                    WHERE id = $1
                    """,
                    key_id,
                )
            else:
                # SQLite: fall back to INTEGER-based COALESCE
                row = await self.db_pool.fetchone(
                    """
                    SELECT id,
                           COALESCE(is_virtual,0) AS is_virtual,
                           org_id, team_id,
                           llm_budget_day_tokens, llm_budget_month_tokens,
                           llm_budget_day_usd, llm_budget_month_usd,
                           llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models
                    FROM api_keys
                    WHERE id = ?
                    """,
                    key_id,
                )

            return row
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.fetch_key_limits failed: {exc}")
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

    async def create_api_key_row(
        self,
        *,
        user_id: int,
        key_hash: str,
        key_prefix: str,
        name: Optional[str],
        description: Optional[str],
        scope: str,
        expires_at: Optional[datetime],
        rate_limit: Optional[int],
        allowed_ips: Optional[List[str]],
        metadata: Optional[Dict[str, Any]],
    ) -> int:
        """
        Insert a new API key row and return its id.

        This mirrors the INSERT logic used by APIKeyManager.create_api_key
        while centralizing dialect-specific SQL in the repository layer.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchval"):
                    import json

                    key_id = await conn.fetchval(
                        """
                        INSERT INTO api_keys (
                            user_id, key_hash, key_prefix, name, description,
                            scope, expires_at, rate_limit, allowed_ips, metadata
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        RETURNING id
                        """,
                        user_id,
                        key_hash,
                        key_prefix,
                        name,
                        description,
                        scope,
                        expires_at,
                        rate_limit,
                        json.dumps(allowed_ips) if allowed_ips else None,
                        json.dumps(metadata) if metadata else None,
                    )
                else:
                    import json

                    cursor = await conn.execute(
                        """
                        INSERT INTO api_keys (
                            user_id, key_hash, key_prefix, name, description,
                            scope, expires_at, rate_limit, allowed_ips, metadata
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            key_hash,
                            key_prefix,
                            name,
                            description,
                            scope,
                            expires_at.isoformat() if expires_at else None,
                            rate_limit,
                            json.dumps(allowed_ips) if allowed_ips else None,
                            json.dumps(metadata) if metadata else None,
                        ),
                    )
                    key_id = getattr(cursor, "lastrowid", None)
                    try:
                        await conn.commit()
                    except Exception:
                        pass

            return int(key_id)
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.create_api_key_row failed: {exc}")
            raise

    async def create_virtual_key_row(
        self,
        *,
        user_id: int,
        key_hash: str,
        key_prefix: str,
        name: Optional[str],
        description: Optional[str],
        expires_at: Optional[datetime],
        org_id: Optional[int],
        team_id: Optional[int],
        allowed_endpoints: Optional[List[str]],
        allowed_providers: Optional[List[str]],
        allowed_models: Optional[List[str]],
        budget_day_tokens: Optional[int],
        budget_month_tokens: Optional[int],
        budget_day_usd: Optional[float],
        budget_month_usd: Optional[float],
        parent_key_id: Optional[int],
        allowed_methods: Optional[List[str]],
        allowed_paths: Optional[List[str]],
        max_calls: Optional[int],
        max_runs: Optional[int],
    ) -> int:
        """
        Insert a new virtual API key row and return its id.

        This mirrors the INSERT logic used by APIKeyManager.create_virtual_key
        while centralizing dialect-specific SQL in the repository layer.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchval"):
                    import json as _json

                    _endpoints = (
                        _json.dumps(allowed_endpoints)
                        if allowed_endpoints is not None
                        else None
                    )
                    _providers = (
                        _json.dumps(allowed_providers)
                        if allowed_providers is not None
                        else None
                    )
                    _models = (
                        _json.dumps(allowed_models)
                        if allowed_models is not None
                        else None
                    )
                    _meta_dict: Dict[str, Any] = {}
                    if allowed_methods:
                        _meta_dict["allowed_methods"] = [
                            str(x).upper() for x in allowed_methods
                        ]
                    if allowed_paths:
                        _meta_dict["allowed_paths"] = [str(x) for x in allowed_paths]
                    if max_calls is not None:
                        _meta_dict["max_calls"] = int(max_calls)
                    if max_runs is not None:
                        _meta_dict["max_runs"] = int(max_runs)
                    _metadata = _json.dumps(_meta_dict) if _meta_dict else None

                    # Detect column types to choose JSONB cast or plain text insert
                    try:
                        col_type = await conn.fetchval(
                            """
                            SELECT data_type FROM information_schema.columns
                            WHERE table_name = 'api_keys' AND column_name = 'llm_allowed_endpoints'
                            """
                        )
                    except Exception:
                        col_type = None
                    is_jsonb = isinstance(col_type, str) and ("json" in col_type.lower())

                    if is_jsonb:
                        key_id = await conn.fetchval(
                            """
                            INSERT INTO api_keys (
                                user_id, key_hash, key_prefix, name, description, scope, status, expires_at,
                                is_virtual, parent_key_id, org_id, team_id,
                                llm_budget_day_tokens, llm_budget_month_tokens,
                                llm_budget_day_usd, llm_budget_month_usd,
                                llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models,
                                metadata
                            ) VALUES (
                                $1,$2,$3,$4,$5,$6,'active',$7,
                                TRUE,$8,$9,$10,
                                $11,$12,$13,$14,$15::jsonb,$16::jsonb,$17::jsonb,
                                ($18)::jsonb
                            ) RETURNING id
                            """,
                            user_id,
                            key_hash,
                            key_prefix,
                            name,
                            description,
                            "read",
                            expires_at,
                            parent_key_id,
                            org_id,
                            team_id,
                            budget_day_tokens,
                            budget_month_tokens,
                            budget_day_usd,
                            budget_month_usd,
                            _endpoints,
                            _providers,
                            _models,
                            _metadata,
                        )
                    else:
                        key_id = await conn.fetchval(
                            """
                            INSERT INTO api_keys (
                                user_id, key_hash, key_prefix, name, description, scope, status, expires_at,
                                is_virtual, parent_key_id, org_id, team_id,
                                llm_budget_day_tokens, llm_budget_month_tokens,
                                llm_budget_day_usd, llm_budget_month_usd,
                                llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models,
                                metadata
                            ) VALUES (
                                $1,$2,$3,$4,$5,$6,'active',$7,
                                TRUE,$8,$9,$10,
                                $11,$12,$13,$14,$15,$16,$17,
                                $18
                            ) RETURNING id
                            """,
                            user_id,
                            key_hash,
                            key_prefix,
                            name,
                            description,
                            "read",
                            expires_at,
                            parent_key_id,
                            org_id,
                            team_id,
                            budget_day_tokens,
                            budget_month_tokens,
                            budget_day_usd,
                            budget_month_usd,
                            _endpoints,
                            _providers,
                            _models,
                            _metadata,
                        )
                else:
                    import json

                    _meta_dict: Dict[str, Any] = {}
                    if allowed_methods:
                        _meta_dict["allowed_methods"] = [
                            str(x).upper() for x in allowed_methods
                        ]
                    if allowed_paths:
                        _meta_dict["allowed_paths"] = [str(x) for x in allowed_paths]
                    if max_calls is not None:
                        _meta_dict["max_calls"] = int(max_calls)
                    if max_runs is not None:
                        _meta_dict["max_runs"] = int(max_runs)
                    _metadata = json.dumps(_meta_dict) if _meta_dict else None

                    cursor = await conn.execute(
                        """
                        INSERT INTO api_keys (
                            user_id, key_hash, key_prefix, name, description, scope, status, expires_at,
                            is_virtual, parent_key_id, org_id, team_id,
                            llm_budget_day_tokens, llm_budget_month_tokens,
                            llm_budget_day_usd, llm_budget_month_usd,
                            llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models,
                            metadata
                        ) VALUES (?,?,?,?,?,?,'active',?,
                            1,?,?,?,?,?,?,?,?,?,?,?
                        )
                        """,
                        (
                            user_id,
                            key_hash,
                            key_prefix,
                            name,
                            description,
                            "read",
                            expires_at.isoformat() if expires_at else None,
                            parent_key_id,
                            org_id,
                            team_id,
                            budget_day_tokens,
                            budget_month_tokens,
                            budget_day_usd,
                            budget_month_usd,
                            (json.dumps(allowed_endpoints) if allowed_endpoints else None),
                            (json.dumps(allowed_providers) if allowed_providers else None),
                            (json.dumps(allowed_models) if allowed_models else None),
                            _metadata,
                        ),
                    )
                    key_id = getattr(cursor, "lastrowid", None)
                    try:
                        await conn.commit()
                    except Exception:
                        pass

            return int(key_id)
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.create_virtual_key_row failed: {exc}")
            raise

    async def mark_rotated(
        self,
        *,
        old_key_id: int,
        new_key_id: int,
        rotated_status: str,
        reason: str,
        revoked_at: datetime,
    ) -> None:
        """
        Mark an existing key as rotated and link it to a new key.

        This updates:
        - old key: ``status``, ``rotated_to``, ``revoked_at``, ``revoke_reason``
        - new key: ``rotated_from``
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    await conn.execute(
                        """
                        UPDATE api_keys
                        SET status = $1, rotated_to = $2, revoked_at = $3,
                            revoke_reason = $4
                        WHERE id = $5
                        """,
                        rotated_status,
                        new_key_id,
                        revoked_at,
                        reason,
                        old_key_id,
                    )
                    await conn.execute(
                        "UPDATE api_keys SET rotated_from = $1 WHERE id = $2",
                        old_key_id,
                        new_key_id,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE api_keys
                        SET status = ?, rotated_to = ?, revoked_at = ?,
                            revoke_reason = ?
                        WHERE id = ?
                        """,
                        (
                            rotated_status,
                            new_key_id,
                            revoked_at.isoformat(),
                            reason,
                            old_key_id,
                        ),
                    )
                    await conn.execute(
                        "UPDATE api_keys SET rotated_from = ? WHERE id = ?",
                        (old_key_id, new_key_id),
                    )
                    try:
                        await conn.commit()
                    except Exception:
                        pass
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.mark_rotated failed: {exc}")
            raise

    async def revoke_api_key_for_user(
        self,
        *,
        key_id: int,
        user_id: int,
        revoked_status: str,
        active_status: str,
        reason: str,
        revoked_at: datetime,
    ) -> bool:
        """
        Revoke an API key owned by the given user.

        Returns True when a row was updated (key existed and was active), False otherwise.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    result = await conn.execute(
                        """
                        UPDATE api_keys
                        SET status = $1, revoked_at = $2, revoked_by = $3,
                            revoke_reason = $4
                        WHERE id = $5 AND user_id = $6 AND status = $7
                        """,
                        revoked_status,
                        revoked_at,
                        user_id,
                        reason,
                        key_id,
                        user_id,
                        active_status,
                    )
                    try:
                        return result != "UPDATE 0"
                    except Exception:
                        return True
                cursor = await conn.execute(
                    """
                    UPDATE api_keys
                    SET status = ?, revoked_at = ?, revoked_by = ?,
                        revoke_reason = ?
                    WHERE id = ? AND user_id = ? AND status = ?
                    """,
                    (
                        revoked_status,
                        revoked_at.isoformat(),
                        user_id,
                        reason,
                        key_id,
                        user_id,
                        active_status,
                    ),
                )
                success = getattr(cursor, "rowcount", 0) > 0
                try:
                    await conn.commit()
                except Exception:
                    pass
                return success
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.revoke_api_key_for_user failed: {exc}")
            raise

    async def increment_usage(
        self,
        *,
        key_id: int,
        ip_address: Optional[str],
    ) -> None:
        """
        Increment usage_count and update last_used_at/last_used_ip for a key.

        Mirrors the behavior of APIKeyManager._update_usage while centralizing
        SQL and backend differences.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    await conn.execute(
                        """
                        UPDATE api_keys
                        SET usage_count = COALESCE(usage_count, 0) + 1,
                            last_used_at = $1,
                            last_used_ip = $2
                        WHERE id = $3
                        """,
                        datetime.utcnow(),
                        ip_address,
                        key_id,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE api_keys
                        SET usage_count = COALESCE(usage_count, 0) + 1,
                            last_used_at = ?,
                            last_used_ip = ?
                        WHERE id = ?
                        """,
                        (datetime.utcnow().isoformat(), ip_address, key_id),
                    )
                    try:
                        await conn.commit()
                    except Exception:
                        pass
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.increment_usage failed: {exc}")
            raise

    async def expire_keys_before(
        self,
        *,
        now: datetime,
        expired_status: str,
        active_status: str,
    ) -> int:
        """
        Mark keys as expired when their expires_at is before ``now``.

        This mirrors the behavior of APIKeyManager.cleanup_expired_keys while
        centralizing SQL and backend differences.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    result = await conn.execute(
                        """
                        UPDATE api_keys
                        SET status = $1
                        WHERE status = $2 AND expires_at < $3
                        """,
                        expired_status,
                        active_status,
                        now,
                    )
                    try:
                        # asyncpg returns a status string like "UPDATE 3"
                        return int(str(result).split()[-1])
                    except Exception:
                        return 0
                cursor = await conn.execute(
                    """
                    UPDATE api_keys
                    SET status = ?
                    WHERE status = ? AND expires_at < ?
                    """,
                    (expired_status, active_status, now.isoformat()),
                )
                try:
                    await conn.commit()
                except Exception:
                    pass
                return int(getattr(cursor, "rowcount", 0) or 0)
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.expire_keys_before failed: {exc}")
            raise

    async def mark_key_expired(
        self,
        *,
        key_id: int,
        expired_status: str,
    ) -> None:
        """
        Mark a key as expired by updating its status.

        Mirrors the behavior of APIKeyManager._mark_expired.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    await conn.execute(
                        "UPDATE api_keys SET status = $1 WHERE id = $2",
                        expired_status,
                        key_id,
                    )
                else:
                    await conn.execute(
                        "UPDATE api_keys SET status = ? WHERE id = ?",
                        (expired_status, key_id),
                    )
                    try:
                        await conn.commit()
                    except Exception:
                        pass
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.mark_key_expired failed: {exc}")
            raise

    async def insert_audit_log(
        self,
        *,
        key_id: int,
        action: str,
        user_id: Optional[int],
        details: Optional[Dict[str, Any]],
    ) -> None:
        """
        Insert a row into api_key_audit_log for the given key/action.

        Centralizes audit-log SQL previously embedded in APIKeyManager._log_action.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    import json as _json

                    _details = _json.dumps(details) if details is not None else None
                    await conn.execute(
                        """
                        INSERT INTO api_key_audit_log (api_key_id, action, user_id, details)
                        VALUES ($1, $2, $3, $4::jsonb)
                        """,
                        key_id,
                        action,
                        user_id,
                        _details,
                    )
                else:
                    import json

                    await conn.execute(
                        """
                        INSERT INTO api_key_audit_log (api_key_id, action, user_id, details)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            key_id,
                            action,
                            user_id,
                            json.dumps(details) if details else None,
                        ),
                    )
                    try:
                        await conn.commit()
                    except Exception:
                        pass
        except Exception as exc:  # pragma: no cover - surfaced via higher layers
            logger.error(f"AuthnzApiKeysRepo.insert_audit_log failed: {exc}")
            raise
