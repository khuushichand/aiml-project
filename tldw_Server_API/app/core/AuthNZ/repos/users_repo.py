from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB, UserNotFoundError, DatabaseError


@dataclass
class AuthnzUsersRepo:
    """
    Repository for AuthNZ user records.

    This thin wrapper centralizes read access to the ``users`` table so that
    AuthNZ code paths can depend on a small, well-defined surface rather than
    calling ad-hoc helpers. It builds on the existing ``UsersDB`` abstraction
    and shares the same ``DatabasePool`` instance.
    """

    db_pool: DatabasePool

    @classmethod
    async def from_pool(cls) -> "AuthnzUsersRepo":
        """Construct a repository bound to the global AuthNZ DatabasePool."""
        pool = await get_db_pool()
        return cls(db_pool=pool)

    async def _users_db(self) -> UsersDB:
        db = UsersDB(self.db_pool)
        await db.initialize()
        return db

    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a user row by integer id.

        Returns ``None`` when the user does not exist. All other errors are
        surfaced to callers so they can apply appropriate HTTP semantics.
        """
        db = await self._users_db()
        try:
            return await db.get_user_by_id(user_id)
        except UserNotFoundError:
            return None
        except DatabaseError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"AuthnzUsersRepo.get_user_by_id failed: {exc}")
            raise

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch a user row by username."""
        db = await self._users_db()
        try:
            return await db.get_user_by_username(username)
        except DatabaseError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"AuthnzUsersRepo.get_user_by_username failed: {exc}")
            raise

    async def get_user_by_uuid(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        """Fetch a user row by UUID string."""
        db = await self._users_db()
        try:
            return await db.get_user_by_uuid(user_uuid)
        except DatabaseError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"AuthnzUsersRepo.get_user_by_uuid failed: {exc}")
            raise

    async def list_users(
        self,
        *,
        offset: int,
        limit: int,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Return a window of users and the total count matching the filters.

        This mirrors the admin list endpoint semantics (role, is_active,
        username/email search) while encapsulating backend-specific SQL.
        """
        db = await self._users_db()
        # Reuse the underlying DatabasePool directly for count + projection
        is_pg = db._using_postgres_backend()

        conditions: list[str] = []
        params: list[Any] = []
        param_count = 0

        if role:
            param_count += 1
            conditions.append(f"role = ${param_count}" if is_pg else "role = ?")
            params.append(role)

        if is_active is not None:
            param_count += 1
            conditions.append(f"is_active = ${param_count}" if is_pg else "is_active = ?")
            params.append(is_active)

        if search:
            param_count += 1
            search_pattern = f"%{search}%"
            if is_pg:
                conditions.append(f"(username ILIKE ${param_count} OR email ILIKE ${param_count})")
            else:
                conditions.append("(username LIKE ? OR email LIKE ?)")
                params.append(search_pattern)
            params.append(search_pattern)

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""

        try:
            # Total count
            if is_pg:
                count_query = f"SELECT COUNT(*) FROM users{where_clause}"
                total = await db.db_pool.fetchval(count_query, *params)
            else:
                count_query = f"SELECT COUNT(*) FROM users{where_clause}"
                cursor = await db.db_pool.execute(count_query, params)
                row = await cursor.fetchone()
                total = row[0] if row else 0

            # Page of users
            if is_pg:
                query = f"""
                    SELECT id, uuid, username, email, role, is_active, is_verified,
                           created_at, last_login, storage_quota_mb, storage_used_mb
                    FROM users{where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${param_count + 1} OFFSET ${param_count + 2}
                """
                q_params = [*params, limit, offset]
                rows = await db.db_pool.fetch(query, *q_params)
            else:
                query = f"""
                    SELECT id, uuid, username, email, role, is_active, is_verified,
                           created_at, last_login, storage_quota_mb, storage_used_mb
                    FROM users{where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                q_params = [*params, limit, offset]
                cursor = await db.db_pool.execute(query, q_params)
                rows = await cursor.fetchall()

            users: list[Dict[str, Any]] = []
            for row in rows:
                if hasattr(row, "keys") or isinstance(row, dict):
                    r = dict(row)
                    user_dict = {
                        "id": int(r.get("id")),
                        "uuid": str(r.get("uuid")) if r.get("uuid") is not None else None,
                        "username": r.get("username"),
                        "email": r.get("email"),
                        "role": r.get("role"),
                        "is_active": bool(r.get("is_active")),
                        "is_verified": bool(r.get("is_verified")),
                        "created_at": r.get("created_at"),
                        "last_login": r.get("last_login"),
                        "storage_quota_mb": int(r.get("storage_quota_mb") or 0),
                        "storage_used_mb": float(r.get("storage_used_mb") or 0.0),
                    }
                else:
                    user_dict = {
                        "id": int(row[0]),
                        "uuid": str(row[1]) if row[1] is not None else None,
                        "username": row[2],
                        "email": row[3],
                        "role": row[4],
                        "is_active": bool(row[5]),
                        "is_verified": bool(row[6]),
                        "created_at": row[7],
                        "last_login": row[8],
                        "storage_quota_mb": int(row[9] or 0),
                        "storage_used_mb": float(row[10] or 0.0),
                    }
                users.append(user_dict)

            return users, int(total or 0)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"AuthnzUsersRepo.list_users failed: {exc}")
            raise
