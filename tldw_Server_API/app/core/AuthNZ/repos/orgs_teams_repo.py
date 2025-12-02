from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    DuplicateOrganizationError,
    DuplicateTeamError,
)


DEFAULT_BASE_TEAM_NAME = "Default-Base"
DEFAULT_BASE_TEAM_SLUG = "default-base"
DEFAULT_BASE_TEAM_DESCRIPTION = (
    "Automatically managed base team for organization-wide membership."
)


@dataclass
class AuthnzOrgsTeamsRepo:
    """
    Repository for organizations, teams, and membership.

    This repo encapsulates common read/write paths so higher-level orgs/teams
    helpers do not need to embed backend-specific SQL for Postgres vs SQLite.
    """

    db_pool: DatabasePool

    async def create_organization(
        self,
        *,
        name: str,
        owner_user_id: Optional[int] = None,
        slug: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create an organization row with basic duplicate checks.

        Mirrors the behavior of ``create_organization`` in ``orgs_teams`` but
        centralizes the dialect-specific SQL.
        """
        import json

        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    # PostgreSQL path
                    if slug is not None and slug != "":
                        exists_slug = await conn.fetchrow(
                            "SELECT 1 FROM organizations WHERE LOWER(slug) = LOWER($1)",
                            slug,
                        )
                        if exists_slug:
                            raise DuplicateOrganizationError("slug", str(slug))
                    exists_name = await conn.fetchrow(
                        "SELECT 1 FROM organizations WHERE LOWER(name) = LOWER($1)",
                        name,
                    )
                    if exists_name:
                        raise DuplicateOrganizationError("name", str(name))
                    row = await conn.fetchrow(
                        """
                        INSERT INTO organizations (name, slug, owner_user_id, metadata)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id, name, slug, owner_user_id, is_active, created_at, updated_at
                        """,
                        name,
                        slug,
                        owner_user_id,
                        (metadata if metadata is not None else None),
                    )
                    d = dict(row)
                    try:
                        from datetime import datetime

                        if isinstance(d.get("created_at"), datetime):
                            d["created_at"] = d["created_at"].isoformat()
                        if isinstance(d.get("updated_at"), datetime):
                            d["updated_at"] = d["updated_at"].isoformat()
                    except (TypeError, ValueError, AttributeError) as exc:
                        logger.debug(f"Skipping datetime normalization for org row: {exc}")
                    return d

                # SQLite / aiosqlite path
                if slug is not None and slug != "":
                    cur_chk = await conn.execute(
                        "SELECT 1 FROM organizations WHERE LOWER(slug) = LOWER(?)",
                        (slug,),
                    )
                    if await cur_chk.fetchone():
                        raise DuplicateOrganizationError("slug", str(slug))
                cur_chk2 = await conn.execute(
                    "SELECT 1 FROM organizations WHERE LOWER(name) = LOWER(?)",
                    (name,),
                )
                if await cur_chk2.fetchone():
                    raise DuplicateOrganizationError("name", str(name))
                cur = await conn.execute(
                    "INSERT INTO organizations (name, slug, owner_user_id, metadata) VALUES (?, ?, ?, ?)",
                    (
                        name,
                        slug,
                        owner_user_id,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                org_id = cur.lastrowid
                cur2 = await conn.execute(
                    """
                    SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at
                    FROM organizations
                    WHERE id = ?
                    """,
                    (org_id,),
                )
                row = await cur2.fetchone()
                return {
                    "id": row[0],
                    "name": row[1],
                    "slug": row[2],
                    "owner_user_id": row[3],
                    "is_active": bool(row[4]),
                    "created_at": row[5],
                    "updated_at": row[6],
                }
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzOrgsTeamsRepo.create_organization failed: {exc}")
            raise

    async def create_team(
        self,
        *,
        org_id: int,
        name: str,
        slug: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a team row with per-organization duplicate checks.

        Mirrors the behavior of ``create_team`` in ``orgs_teams``.
        """
        import json

        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    exists = await conn.fetchrow(
                        "SELECT 1 FROM teams WHERE org_id = $1 AND LOWER(name) = LOWER($2)",
                        org_id,
                        name,
                    )
                    if exists:
                        raise DuplicateTeamError(org_id, "name", str(name))
                    row = await conn.fetchrow(
                        """
                        INSERT INTO teams (org_id, name, slug, description, metadata)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING id, org_id, name, slug, description, is_active, created_at, updated_at
                        """,
                        org_id,
                        name,
                        slug,
                        description,
                        (metadata if metadata is not None else None),
                    )
                    d = dict(row)
                    try:
                        from datetime import datetime

                        if isinstance(d.get("created_at"), datetime):
                            d["created_at"] = d["created_at"].isoformat()
                        if isinstance(d.get("updated_at"), datetime):
                            d["updated_at"] = d["updated_at"].isoformat()
                    except (TypeError, ValueError, AttributeError) as exc:
                        logger.debug(f"Skipping datetime normalization for team row: {exc}")
                    return d

                # SQLite path
                curx = await conn.execute(
                    "SELECT 1 FROM teams WHERE org_id = ? AND LOWER(name) = LOWER(?)",
                    (org_id, name),
                )
                if await curx.fetchone():
                    raise DuplicateTeamError(org_id, "name", str(name))
                cur = await conn.execute(
                    "INSERT INTO teams (org_id, name, slug, description, metadata) VALUES (?, ?, ?, ?, ?)",
                    (
                        org_id,
                        name,
                        slug,
                        description,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                team_id = cur.lastrowid
                cur2 = await conn.execute(
                    """
                    SELECT id, org_id, name, slug, description, is_active, created_at, updated_at
                    FROM teams
                    WHERE id = ?
                    """,
                    (team_id,),
                )
                row = await cur2.fetchone()
                return {
                    "id": row[0],
                    "org_id": row[1],
                    "name": row[2],
                    "slug": row[3],
                    "description": row[4],
                    "is_active": bool(row[5]),
                    "created_at": row[6],
                    "updated_at": row[7],
                }
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzOrgsTeamsRepo.create_team failed: {exc}")
            raise

    async def list_organizations(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        q: Optional[str] = None,
        with_total: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List organizations with optional server-side filtering and total count.

        Returns (rows, total).
        """
        try:
            if self.db_pool.pool:
                # Postgres path
                if q:
                    like = f"%{str(q).lower()}%"
                    rows = await self.db_pool.fetchall(
                        """
                        SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at
                        FROM organizations
                        WHERE LOWER(name) LIKE $1
                           OR LOWER(COALESCE(slug, '')) LIKE $1
                           OR CAST(id AS TEXT) LIKE $1
                        ORDER BY created_at DESC
                        LIMIT $2 OFFSET $3
                        """,
                        like,
                        limit,
                        offset,
                    )
                    total = (
                        await self.db_pool.fetchval(
                            """
                            SELECT COUNT(*) FROM organizations
                            WHERE LOWER(name) LIKE $1
                               OR LOWER(COALESCE(slug, '')) LIKE $1
                               OR CAST(id AS TEXT) LIKE $1
                            """,
                            like,
                        )
                        if with_total
                        else 0
                    )
                else:
                    rows = await self.db_pool.fetchall(
                        """
                        SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at
                        FROM organizations
                        ORDER BY created_at DESC
                        LIMIT $1 OFFSET $2
                        """,
                        limit,
                        offset,
                    )
                    total = (
                        await self.db_pool.fetchval(
                            "SELECT COUNT(*) FROM organizations",
                        )
                        if with_total
                        else 0
                    )

                normalized: List[Dict[str, Any]] = []
                for r in rows:
                    d = dict(r)
                    d["is_active"] = bool(d.get("is_active", True))
                    normalized.append(d)
                return normalized, int(total or 0)

            # SQLite / aiosqlite path
            async with self.db_pool.acquire() as conn:
                if q:
                    like = f"%{str(q).lower()}%"
                    cursor = await conn.execute(
                        """
                        SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at
                        FROM organizations
                        WHERE LOWER(name) LIKE ?
                           OR LOWER(COALESCE(slug, '')) LIKE ?
                           OR CAST(id AS TEXT) LIKE ?
                        ORDER BY created_at DESC
                        LIMIT ? OFFSET ?
                        """,
                        (like, like, like, limit, offset),
                    )
                    rows_raw = await cursor.fetchall()
                    rows = [
                        {
                            "id": r[0],
                            "name": r[1],
                            "slug": r[2],
                            "owner_user_id": r[3],
                            "is_active": bool(r[4]),
                            "created_at": r[5],
                            "updated_at": r[6],
                        }
                        for r in rows_raw
                    ]
                    if with_total:
                        cur2 = await conn.execute(
                            """
                            SELECT COUNT(*) FROM organizations
                            WHERE LOWER(name) LIKE ?
                               OR LOWER(COALESCE(slug, '')) LIKE ?
                               OR CAST(id AS TEXT) LIKE ?
                            """,
                            (like, like, like),
                        )
                        total_row = await cur2.fetchone()
                        total = int(total_row[0]) if total_row else 0
                    else:
                        total = 0
                else:
                    cursor = await conn.execute(
                        """
                        SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at
                        FROM organizations
                        ORDER BY created_at DESC
                        LIMIT ? OFFSET ?
                        """,
                        (limit, offset),
                    )
                    rows_raw = await cursor.fetchall()
                    rows = [
                        {
                            "id": r[0],
                            "name": r[1],
                            "slug": r[2],
                            "owner_user_id": r[3],
                            "is_active": bool(r[4]),
                            "created_at": r[5],
                            "updated_at": r[6],
                        }
                        for r in rows_raw
                    ]
                    if with_total:
                        cur2 = await conn.execute("SELECT COUNT(*) FROM organizations")
                        total_row = await cur2.fetchone()
                        total = int(total_row[0]) if total_row else 0
                    else:
                        total = 0

                return rows, int(total or 0)
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzOrgsTeamsRepo.list_organizations failed: {exc}")
            raise

    # -------------------------------------------------------------------------
    # Team membership helpers
    # -------------------------------------------------------------------------

    async def add_team_member(
        self,
        *,
        team_id: int,
        user_id: int,
        role: str = "member",
    ) -> Dict[str, Any]:
        """
        Add a user to a team (idempotent).

        Returns a dict with ``team_id``, ``user_id``, ``role``, and ``org_id``.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    await conn.execute(
                        """
                        INSERT INTO team_members (team_id, user_id, role)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (team_id, user_id) DO NOTHING
                        """,
                        team_id,
                        user_id,
                        role,
                    )
                    row = await conn.fetchrow(
                        """
                        SELECT tm.team_id, tm.user_id, tm.role, t.org_id
                        FROM team_members tm
                        JOIN teams t ON tm.team_id = t.id
                        WHERE tm.team_id = $1 AND tm.user_id = $2
                        """,
                        team_id,
                        user_id,
                    )
                    if row:
                        return dict(row)
                    return {"team_id": int(team_id), "user_id": int(user_id), "role": role}

                # SQLite / aiosqlite path
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO team_members (team_id, user_id, role)
                    VALUES (?, ?, ?)
                    """,
                    (team_id, user_id, role),
                )
                try:
                    await conn.commit()
                except Exception as exc:
                    logger.debug(f"AuthnzOrgsTeamsRepo SQLite commit failed during add_team_member: {exc}")
                cur = await conn.execute(
                    """
                    SELECT tm.team_id, tm.user_id, tm.role, t.org_id
                    FROM team_members tm
                    JOIN teams t ON tm.team_id = t.id
                    WHERE tm.team_id = ? AND tm.user_id = ?
                    """,
                    (team_id, user_id),
                )
                row = await cur.fetchone()
                if row:
                    return {
                        "team_id": row[0],
                        "user_id": row[1],
                        "role": row[2],
                        "org_id": row[3],
                    }
                return {"team_id": int(team_id), "user_id": int(user_id), "role": role}
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzOrgsTeamsRepo.add_team_member failed: {exc}")
            raise

    async def list_team_members(self, team_id: int) -> List[Dict[str, Any]]:
        """
        List members of a team ordered by ``added_at`` descending.
        """
        try:
            if self.db_pool.pool:
                rows = await self.db_pool.fetchall(
                    """
                    SELECT user_id, role, status, added_at
                    FROM team_members
                    WHERE team_id = $1
                    ORDER BY added_at DESC
                    """,
                    team_id,
                )
                # Postgres rows are already dict-like
                return [dict(r) for r in rows]

            async with self.db_pool.acquire() as conn:
                cursor = await conn.execute(
                    """
                    SELECT user_id, role, status, added_at
                    FROM team_members
                    WHERE team_id = ?
                    ORDER BY added_at DESC
                    """,
                    (team_id,),
                )
                rows = await cursor.fetchall()
                return [
                    {
                        "user_id": r[0],
                        "role": r[1],
                        "status": r[2],
                        "added_at": r[3],
                    }
                    for r in rows
                ]
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzOrgsTeamsRepo.list_team_members failed: {exc}")
            raise

    async def list_memberships_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """
        List team memberships (including org_id) for a user.

        Returns dicts with ``team_id``, ``user_id``, ``role``, ``org_id``.
        """
        try:
            if self.db_pool.pool:
                rows = await self.db_pool.fetchall(
                    """
                    SELECT tm.team_id, tm.user_id, tm.role, t.org_id
                    FROM team_members tm
                    JOIN teams t ON tm.team_id = t.id
                    WHERE tm.user_id = $1
                    ORDER BY tm.team_id
                    """,
                    user_id,
                )
                return [dict(r) for r in rows]

            async with self.db_pool.acquire() as conn:
                cur = await conn.execute(
                    """
                    SELECT tm.team_id, tm.user_id, tm.role, t.org_id
                    FROM team_members tm
                    JOIN teams t ON tm.team_id = t.id
                    WHERE tm.user_id = ?
                    ORDER BY tm.team_id
                    """,
                    (user_id,),
                )
                rows = await cur.fetchall()
                return [
                    {
                        "team_id": r[0],
                        "user_id": r[1],
                        "role": r[2],
                        "org_id": r[3],
                    }
                    for r in rows
                ]
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzOrgsTeamsRepo.list_memberships_for_user failed: {exc}"
            )
            raise

    async def remove_team_member(
        self,
        *,
        team_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Remove a user from a team.

        Returns ``{\"team_id\", \"user_id\", \"removed\"}``.
        """
        try:
            async with self.db_pool.transaction() as conn:
                removed = False
                if hasattr(conn, "fetchrow"):
                    row = await conn.fetchrow(
                        """
                        DELETE FROM team_members
                        WHERE team_id = $1 AND user_id = $2
                        RETURNING team_id, user_id
                        """,
                        team_id,
                        user_id,
                    )
                    removed = row is not None
                else:
                    cur = await conn.execute(
                        """
                        DELETE FROM team_members
                        WHERE team_id = ? AND user_id = ?
                        """,
                        (team_id, user_id),
                    )
                    removed = bool((getattr(cur, "rowcount", 0) or 0) > 0)

            return {
                "team_id": int(team_id),
                "user_id": int(user_id),
                "removed": bool(removed),
            }
        except Exception:  # pragma: no cover - surfaced via callers
            logger.exception(
                "AuthnzOrgsTeamsRepo.remove_team_member failed for team_id=%s user_id=%s",
                team_id,
                user_id,
            )
            raise

    # -------------------------------------------------------------------------
    # Default team helpers (internal)
    # -------------------------------------------------------------------------

    async def _get_or_create_default_team_id(
        self,
        conn: Any,
        org_id: int,
        *,
        create: bool = True,
    ) -> Optional[int]:
        """Fetch (and optionally create) the Default-Base team for an organization."""
        if hasattr(conn, "fetchrow"):
            row = await conn.fetchrow(
                """
                SELECT id
                FROM teams
                WHERE org_id = $1 AND name = $2
                """,
                org_id,
                DEFAULT_BASE_TEAM_NAME,
            )
            if row:
                return int(row["id"])
            if not create:
                return None
            new_row = await conn.fetchrow(
                """
                INSERT INTO teams (org_id, name, slug, description, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                org_id,
                DEFAULT_BASE_TEAM_NAME,
                DEFAULT_BASE_TEAM_SLUG,
                DEFAULT_BASE_TEAM_DESCRIPTION,
                None,
            )
            return int(new_row["id"])

        # SQLite / aiosqlite connection
        cur = await conn.execute(
            "SELECT id FROM teams WHERE org_id = ? AND name = ?",
            (org_id, DEFAULT_BASE_TEAM_NAME),
        )
        row = await cur.fetchone()
        if row:
            return int(row[0])
        if not create:
            return None
        await conn.execute(
            """
            INSERT INTO teams (org_id, name, slug, description, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                org_id,
                DEFAULT_BASE_TEAM_NAME,
                DEFAULT_BASE_TEAM_SLUG,
                DEFAULT_BASE_TEAM_DESCRIPTION,
                None,
            ),
        )
        cur = await conn.execute(
            "SELECT id FROM teams WHERE org_id = ? AND name = ?",
            (org_id, DEFAULT_BASE_TEAM_NAME),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else None

    async def _ensure_user_in_default_team(
        self,
        conn: Any,
        org_id: int,
        user_id: int,
    ) -> None:
        """Ensure the user is enrolled in the organization's Default-Base team."""
        team_id = await self._get_or_create_default_team_id(conn, org_id, create=True)
        if team_id is None:
            return
        if hasattr(conn, "execute") and hasattr(conn, "fetchrow"):
            await conn.execute(
                """
                INSERT INTO team_members (team_id, user_id, role)
                VALUES ($1, $2, $3)
                ON CONFLICT (team_id, user_id) DO NOTHING
                """,
                team_id,
                user_id,
                "member",
            )
        else:
            await conn.execute(
                """
                INSERT OR IGNORE INTO team_members (team_id, user_id, role)
                VALUES (?, ?, ?)
                """,
                (team_id, user_id, "member"),
            )

    async def _remove_user_from_default_team(
        self,
        conn: Any,
        org_id: int,
        user_id: int,
    ) -> None:
        """Remove the user from the organization's Default-Base team if present."""
        team_id = await self._get_or_create_default_team_id(conn, org_id, create=False)
        if team_id is None:
            return
        if hasattr(conn, "execute") and hasattr(conn, "fetchrow"):
            await conn.execute(
                """
                DELETE FROM team_members
                WHERE team_id = $1 AND user_id = $2
                """,
                team_id,
                user_id,
            )
        else:
            await conn.execute(
                """
                DELETE FROM team_members
                WHERE team_id = ? AND user_id = ?
                """,
                (team_id, user_id),
            )

    # -------------------------------------------------------------------------
    # Organization membership helpers
    # -------------------------------------------------------------------------

    async def add_org_member(
        self,
        *,
        org_id: int,
        user_id: int,
        role: str = "member",
    ) -> Dict[str, Any]:
        """
        Add a user to an organization (idempotent) and ensure default-team membership.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    await conn.execute(
                        """
                        INSERT INTO org_members (org_id, user_id, role)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (org_id, user_id) DO NOTHING
                        """,
                        org_id,
                        user_id,
                        role,
                    )
                    row = await conn.fetchrow(
                        """
                        SELECT org_id, user_id, role
                        FROM org_members
                        WHERE org_id = $1 AND user_id = $2
                        """,
                        org_id,
                        user_id,
                    )
                    result = (
                        dict(row)
                        if row
                        else {"org_id": int(org_id), "user_id": int(user_id), "role": role}
                    )
                else:
                    await conn.execute(
                        """
                        INSERT OR IGNORE INTO org_members (org_id, user_id, role)
                        VALUES (?, ?, ?)
                        """,
                        (org_id, user_id, role),
                    )
                try:
                    await conn.commit()
                except Exception as exc:
                    logger.debug(f"AuthnzOrgsTeamsRepo SQLite commit failed during org_member role update: {exc}")
                    cur = await conn.execute(
                        """
                        SELECT org_id, user_id, role
                        FROM org_members
                        WHERE org_id = ? AND user_id = ?
                        """,
                        (org_id, user_id),
                    )
                    row = await cur.fetchone()
                    if row:
                        try:
                            result = {
                                "org_id": row[0],
                                "user_id": row[1],
                                "role": row[2],
                            }
                        except Exception as exc:
                            logger.debug(f"Could not unpack org member row; falling back to dict: {exc}")
                            try:
                                result = dict(row)
                            except Exception as inner_exc:
                                logger.debug(
                                    f"dict() fallback failed for org member row; using defaults: {inner_exc}"
                                )
                                result = {
                                    "org_id": int(org_id),
                                    "user_id": int(user_id),
                                    "role": role,
                                }
                    else:
                        result = {
                            "org_id": int(org_id),
                            "user_id": int(user_id),
                            "role": role,
                        }

                try:
                    await self._ensure_user_in_default_team(conn, org_id, user_id)
                except Exception as exc:
                    logger.warning(
                        "Default team auto-enroll failed for org_id=%s, user_id=%s: %s",
                        org_id,
                        user_id,
                        exc,
                    )
                return result
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzOrgsTeamsRepo.add_org_member failed: {exc}")
            raise

    async def list_org_members(
        self,
        *,
        org_id: int,
        limit: int = 100,
        offset: int = 0,
        role: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List members of an organization with pagination and optional filters.
        """
        try:
            if self.db_pool.pool:
                conditions = ["org_id = $1"]
                params: List[Any] = [org_id]
                p = 1
                if role:
                    p += 1
                    conditions.append(f"role = ${p}")
                    params.append(role)
                if status:
                    p += 1
                    conditions.append(f"status = ${p}")
                    params.append(status)
                where_clause = " AND ".join(conditions)
                p += 1
                params.append(limit)
                p += 1
                params.append(offset)
                sql = (
                    f"SELECT user_id, role, status, added_at FROM org_members WHERE {where_clause} "
                    f"ORDER BY added_at DESC LIMIT ${p-1} OFFSET ${p}"
                )
                rows = await self.db_pool.fetchall(sql, *params)
                return [dict(r) for r in rows]

            async with self.db_pool.acquire() as conn:
                conditions = ["org_id = ?"]
                params2: List[Any] = [org_id]
                if role:
                    conditions.append("role = ?")
                    params2.append(role)
                if status:
                    conditions.append("status = ?")
                    params2.append(status)
                where_clause = " AND ".join(conditions)
                sql = (
                    f"SELECT user_id, role, status, added_at FROM org_members WHERE {where_clause} "
                    f"ORDER BY added_at DESC LIMIT ? OFFSET ?"
                )
                params2.extend([limit, offset])
                cur = await conn.execute(sql, tuple(params2))
                rows = await cur.fetchall()
                return [
                    {
                        "user_id": r[0],
                        "role": r[1],
                        "status": r[2],
                        "added_at": r[3],
                    }
                    for r in rows
                ]
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzOrgsTeamsRepo.list_org_members failed: {exc}")
            raise

    async def remove_org_member(
        self,
        *,
        org_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Remove a user from an organization, enforcing at least one owner.
        """
        try:
            async with self.db_pool.transaction() as conn:
                removed = False
                if hasattr(conn, "fetchrow"):
                    current_role = await conn.fetchval(
                        """
                        SELECT role
                        FROM org_members
                        WHERE org_id = $1 AND user_id = $2
                        """,
                        org_id,
                        user_id,
                    )
                    if (current_role or "").lower() == "owner":
                        owner_count = await conn.fetchval(
                            """
                            SELECT COUNT(*) FROM org_members
                            WHERE org_id = $1 AND role = 'owner'
                            """,
                            org_id,
                        )
                        if owner_count is not None and int(owner_count) <= 1:
                            return {
                                "org_id": int(org_id),
                                "user_id": int(user_id),
                                "removed": False,
                                "error": "owner_required",
                            }
                    row = await conn.fetchrow(
                        """
                        DELETE FROM org_members
                        WHERE org_id = $1 AND user_id = $2
                        RETURNING org_id, user_id
                        """,
                        org_id,
                        user_id,
                    )
                    removed = row is not None
                    if removed:
                        try:
                            await self._remove_user_from_default_team(conn, org_id, user_id)
                        except Exception as exc:
                            logger.warning(
                                "Default team removal failed for org_id=%s, user_id=%s: %s",
                                org_id,
                                user_id,
                                exc,
                            )
                else:
                    cur_role = await conn.execute(
                        """
                        SELECT role
                        FROM org_members
                        WHERE org_id = ? AND user_id = ?
                        """,
                        (org_id, user_id),
                    )
                    role_row = await cur_role.fetchone()
                    if role_row and (role_row[0] or "").lower() == "owner":
                        owner_count_row = await conn.execute(
                            """
                            SELECT COUNT(*) FROM org_members
                            WHERE org_id = ? AND role = 'owner'
                            """,
                            (org_id,),
                        )
                        owner_count = await owner_count_row.fetchone()
                        if owner_count and int(owner_count[0]) <= 1:
                            return {
                                "org_id": int(org_id),
                                "user_id": int(user_id),
                                "removed": False,
                                "error": "owner_required",
                            }
                    cur = await conn.execute(
                        """
                        DELETE FROM org_members
                        WHERE org_id = ? AND user_id = ?
                        """,
                        (org_id, user_id),
                    )
                    try:
                        await conn.commit()
                    except Exception:
                        pass
                    try:
                        removed = (cur.rowcount or 0) > 0
                    except Exception:
                        removed = True
                    if removed:
                        try:
                            await self._remove_user_from_default_team(conn, org_id, user_id)
                        except Exception as exc:
                            logger.warning(
                                "Default team removal failed for org_id=%s, user_id=%s: %s",
                                org_id,
                                user_id,
                                exc,
                            )

            return {
                "org_id": int(org_id),
                "user_id": int(user_id),
                "removed": bool(removed),
            }
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(f"AuthnzOrgsTeamsRepo.remove_org_member failed: {exc}")
            raise

    async def update_org_member_role(
        self,
        *,
        org_id: int,
        user_id: int,
        role: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Update an org member's role, enforcing at least one owner.
        """
        target_role = (role or "").lower()
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, "fetchrow"):
                    current_role = await conn.fetchval(
                        """
                        SELECT role
                        FROM org_members
                        WHERE org_id = $1 AND user_id = $2
                        """,
                        org_id,
                        user_id,
                    )
                    if current_role is None:
                        return None
                    if (current_role or "").lower() == "owner" and target_role != "owner":
                        owner_count = await conn.fetchval(
                            """
                            SELECT COUNT(*) FROM org_members
                            WHERE org_id = $1 AND role = 'owner'
                            """,
                            org_id,
                        )
                        if owner_count is not None and int(owner_count) <= 1:
                            return {
                                "org_id": int(org_id),
                                "user_id": int(user_id),
                                "role": current_role,
                                "error": "owner_required",
                            }
                    row = await conn.fetchrow(
                        """
                        UPDATE org_members
                        SET role = $3
                        WHERE org_id = $1 AND user_id = $2
                        RETURNING org_id, user_id, role
                        """,
                        org_id,
                        user_id,
                        role,
                    )
                    return dict(row) if row else None

                cur = await conn.execute(
                    """
                    SELECT role
                    FROM org_members
                    WHERE org_id = ? AND user_id = ?
                    """,
                    (org_id, user_id),
                )
                row = await cur.fetchone()
                if not row:
                    return None
                current_role = row[0] if not hasattr(row, "keys") else row["role"]
                if (current_role or "").lower() == "owner" and target_role != "owner":
                    owner_count_cur = await conn.execute(
                        """
                        SELECT COUNT(*) FROM org_members
                        WHERE org_id = ? AND role = 'owner'
                        """,
                        (org_id,),
                    )
                    owner_count_row = await owner_count_cur.fetchone()
                    if owner_count_row and int(owner_count_row[0]) <= 1:
                        return {
                            "org_id": int(org_id),
                            "user_id": int(user_id),
                            "role": current_role,
                            "error": "owner_required",
                        }
                await conn.execute(
                    """
                    UPDATE org_members
                    SET role = ?
                    WHERE org_id = ? AND user_id = ?
                    """,
                    (role, org_id, user_id),
                )
                try:
                    await conn.commit()
                except Exception as exc:
                    logger.debug(f"AuthnzOrgsTeamsRepo SQLite commit failed during org member insert: {exc}")
                cur2 = await conn.execute(
                    """
                    SELECT org_id, user_id, role
                    FROM org_members
                    WHERE org_id = ? AND user_id = ?
                    """,
                    (org_id, user_id),
                )
                row2 = await cur2.fetchone()
                if row2:
                    try:
                        return {
                            "org_id": row2[0],
                            "user_id": row2[1],
                            "role": row2[2],
                        }
                    except Exception as exc:
                        logger.debug(f"Could not unpack updated org member row; falling back to dict: {exc}")
                        try:
                            return dict(row2)
                        except Exception as inner_exc:
                            logger.debug(
                                f"dict() fallback failed for updated org member row; using defaults: {inner_exc}"
                            )
                            return {
                                "org_id": int(org_id),
                                "user_id": int(user_id),
                                "role": role,
                            }
                return None
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzOrgsTeamsRepo.update_org_member_role failed: {exc}"
            )
            raise

    async def list_org_memberships_for_user(
        self,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """
        List org memberships for a user: ``[{org_id, role}]``.
        """
        try:
            if self.db_pool.pool:
                rows = await self.db_pool.fetchall(
                    """
                    SELECT org_id, role
                    FROM org_members
                    WHERE user_id = $1
                    ORDER BY org_id
                    """,
                    user_id,
                )
                return [dict(r) for r in rows]

            async with self.db_pool.acquire() as conn:
                cur = await conn.execute(
                    """
                    SELECT org_id, role
                    FROM org_members
                    WHERE user_id = ?
                    ORDER BY org_id
                    """,
                    (user_id,),
                )
                rows = await cur.fetchall()
                return [{"org_id": r[0], "role": r[1]} for r in rows]
        except Exception as exc:  # pragma: no cover - surfaced via callers
            logger.error(
                f"AuthnzOrgsTeamsRepo.list_org_memberships_for_user failed: {exc}"
            )
            raise
