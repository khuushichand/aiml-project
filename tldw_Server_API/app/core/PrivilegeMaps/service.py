from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Set

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_single_user_instance
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.privilege_catalog import PrivilegeCatalog, ScopeEntry, load_catalog
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode


RESOURCE_FALLBACK = "uncategorized"
MAX_DETAIL_ROWS = 50_000


class PrivilegeMapService:
    """Aggregates privilege information for organization, team, and user views."""

    def __init__(self) -> None:
        self._catalog: PrivilegeCatalog = load_catalog()
        self._role_scope_map: Dict[str, List[ScopeEntry]] = self._build_role_scope_map()
        self._admin_roles: Set[str] = {"admin", "owner", "platform_admin"}

    @property
    def catalog(self) -> PrivilegeCatalog:
        return self._catalog

    async def get_org_summary(
        self,
        *,
        group_by: str,
        include_trends: bool,
        since: Optional[datetime],
    ) -> Dict[str, Any]:
        users = await self._fetch_users()
        generated_at = datetime.now(timezone.utc)
        buckets: List[Dict[str, Any]] = []

        if group_by == "resource":
            buckets = self._group_by_resource(users)
        elif group_by == "team":
            buckets = await self._group_by_team(users)
        else:  # default to role
            buckets = self._group_by_role(users)

        return {
            "catalog_version": self.catalog.version,
            "generated_at": generated_at,
            "group_by": group_by,
            "buckets": buckets,
            "metadata": {
                "filters": {
                    "include_trends": include_trends,
                    "since": since.isoformat() if since else None,
                }
            },
        }

    async def get_org_detail(
        self,
        *,
        page: int,
        page_size: int,
        resource: Optional[str],
        role_filter: Optional[str],
    ) -> Dict[str, Any]:
        users = await self._fetch_users()
        items = self._build_detail_items(users, resource_filter=resource, role_filter=role_filter)
        return self._paginate_detail(items, page=page, page_size=page_size)

    async def get_team_summary(
        self,
        *,
        team_id: str,
        include_trends: bool,
        since: Optional[datetime],
    ) -> Dict[str, Any]:
        users = await self._fetch_users()
        team_users = await self._filter_users_for_team(users, team_id=team_id)
        generated_at = datetime.now(timezone.utc)
        buckets = self._group_by_role(team_users)
        return {
            "catalog_version": self.catalog.version,
            "generated_at": generated_at,
            "group_by": "role",
            "buckets": buckets,
            "metadata": {
                "filters": {
                    "team_id": team_id,
                    "include_trends": include_trends,
                    "since": since.isoformat() if since else None,
                }
            },
        }

    async def get_team_detail(
        self,
        *,
        team_id: str,
        page: int,
        page_size: int,
        resource: Optional[str],
        role_filter: Optional[str],
    ) -> Dict[str, Any]:
        users = await self._fetch_users()
        team_users = await self._filter_users_for_team(users, team_id=team_id)
        items = self._build_detail_items(
            team_users,
            resource_filter=resource,
            role_filter=role_filter,
            restrict_to_team=team_id,
        )
        return self._paginate_detail(items, page=page, page_size=page_size)

    async def get_user_detail(
        self,
        *,
        user_id: str,
        page: int,
        page_size: int,
        resource: Optional[str],
    ) -> Dict[str, Any]:
        users = await self._fetch_users()
        filtered = [u for u in users if str(u["id"]) == str(user_id)]
        if not filtered:
            logger.debug("Privilege detail requested for unknown user_id=%s", user_id)
        items = self._build_detail_items(filtered, resource_filter=resource)
        return self._paginate_detail(items, page=page, page_size=page_size)

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _build_role_scope_map(self) -> Dict[str, List[ScopeEntry]]:
        mapping: Dict[str, Dict[str, ScopeEntry]] = defaultdict(dict)
        for scope in self.catalog.scopes:
            for role in scope.default_roles or []:
                mapping[role][scope.id] = scope

        # Admin roles automatically get access to all scopes
        for admin_role in ("admin", "owner", "platform_admin"):
            mapping[admin_role] = {scope.id: scope for scope in self.catalog.scopes}
        return {role: list(scopes.values()) for role, scopes in mapping.items()}

    async def _fetch_users(self) -> List[Dict[str, Any]]:
        try:
            pool: DatabasePool = await get_db_pool()
            rows = await pool.fetchall(
                "SELECT id, username, role, is_active FROM users ORDER BY id"
            )
            users: List[Dict[str, Any]] = []
            for row in rows:
                record = self._row_to_dict(row)
                if record and record.get("is_active", 1):
                    users.append(
                        {
                            "id": record.get("id"),
                            "username": record.get("username", ""),
                            "role": record.get("role") or "user",
                        }
                    )
            if users:
                return users
        except Exception as exc:
            logger.debug("Falling back to single-user privilege dataset: %s", exc)

        # Fallback: single-user mode or empty DB
        single_user = get_single_user_instance()
        default_role = "admin" if is_single_user_mode() else (single_user.roles[0] if single_user.roles else "admin")
        return [
            {
                "id": single_user.id,
                "username": single_user.username,
                "role": default_role or "admin",
            }
        ]

    async def _fetch_team_memberships(self) -> List[Dict[str, Any]]:
        try:
            pool: DatabasePool = await get_db_pool()
            rows = await pool.fetchall(
                """
                SELECT tm.team_id, tm.user_id, tm.role AS membership_role,
                       t.name AS team_name, t.org_id
                FROM team_members tm
                JOIN teams t ON tm.team_id = t.id
                """
            )
            memberships: List[Dict[str, Any]] = []
            for row in rows:
                record = self._row_to_dict(row)
                if record:
                    memberships.append(record)
            return memberships
        except Exception as exc:
            logger.debug("Unable to load team memberships: %s", exc)
            return []

    async def _filter_users_for_team(
        self,
        users: List[Dict[str, Any]],
        *,
        team_id: str,
    ) -> List[Dict[str, Any]]:
        memberships = await self._fetch_team_memberships()
        user_ids = {
            str(m["user_id"])
            for m in memberships
            if str(m.get("team_id")) == str(team_id)
        }
        if not user_ids:
            return []
        return [user for user in users if str(user["id"]) in user_ids]

    def _group_by_role(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets: Dict[str, Dict[str, Any]] = {}
        for user in users:
            role = user.get("role") or "user"
            scopes = self._scopes_for_role(role)
            bucket = buckets.setdefault(
                role,
                {"key": role, "users": 0, "endpoints": 0, "scopes": 0},
            )
            bucket["users"] += 1
            bucket["scopes"] = len(scopes)
            bucket["endpoints"] = len(scopes)
        return list(buckets.values())

    async def _group_by_team(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        memberships = await self._fetch_team_memberships()
        by_team: Dict[str, Dict[str, Any]] = {}
        for entry in memberships:
            team_id = str(entry.get("team_id"))
            team = by_team.setdefault(
                team_id,
                {
                    "key": team_id,
                    "team_name": entry.get("team_name"),
                    "org_id": entry.get("org_id"),
                    "users": set(),
                    "scopes": set(),
                },
            )
            team["users"].add(str(entry.get("user_id")))
            user = next((u for u in users if str(u["id"]) == str(entry.get("user_id"))), None)
            if user:
                for scope in self._scopes_for_role(user.get("role")):
                    team["scopes"].add(scope.id)

        buckets: List[Dict[str, Any]] = []
        for team in by_team.values():
            buckets.append(
                {
                    "key": team["key"],
                    "users": len(team["users"]),
                    "endpoints": len(team["scopes"]),
                    "scopes": len(team["scopes"]),
                    "metadata": {
                        "team_name": team.get("team_name"),
                        "org_id": team.get("org_id"),
                    },
                }
            )
        return buckets

    def _group_by_resource(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        resource_access: Dict[str, Dict[str, Any]] = {}
        for user in users:
            scopes = self._scopes_for_role(user.get("role"))
            seen_scopes: Dict[str, Set[str]] = defaultdict(set)
            for scope in scopes:
                tags = scope.resource_tags or [RESOURCE_FALLBACK]
                for tag in tags:
                    bucket = resource_access.setdefault(
                        tag,
                        {"key": tag, "users": set(), "scopes": set()},
                    )
                    bucket["users"].add(str(user["id"]))
                    bucket["scopes"].add(scope.id)
                    seen_scopes[tag].add(scope.id)

        results: List[Dict[str, Any]] = []
        for tag, payload in resource_access.items():
            results.append(
                {
                    "key": tag,
                    "users": len(payload["users"]),
                    "endpoints": len(payload["scopes"]),
                    "scopes": len(payload["scopes"]),
                }
            )
        return results

    def _scopes_for_role(self, role: Optional[str]) -> List[ScopeEntry]:
        normalized = (role or "user").lower()
        if normalized in self._admin_roles:
            return list(self.catalog.scopes)
        if normalized in self._role_scope_map:
            return self._role_scope_map[normalized]
        return []

    def _build_detail_items(
        self,
        users: Sequence[Dict[str, Any]],
        *,
        resource_filter: Optional[str],
        role_filter: Optional[str] = None,
        restrict_to_team: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        resource_filter_lower = resource_filter.lower() if resource_filter else None
        for user in users:
            role = user.get("role") or "user"
            if role_filter and role != role_filter:
                continue
            allowed_scopes = {scope.id for scope in self._scopes_for_role(role)}
            for scope in self.catalog.scopes:
                tags = [tag.lower() for tag in (scope.resource_tags or [RESOURCE_FALLBACK])]
                if resource_filter_lower and resource_filter_lower not in tags:
                    continue
                status = "allowed" if scope.id in allowed_scopes else "blocked"
                items.append(
                    {
                        "user_id": str(user.get("id")),
                        "user_name": user.get("username") or "",
                        "role": role,
                        "endpoint": self._scope_to_endpoint(scope),
                        "method": "ANY",
                        "privilege_scope_id": scope.id,
                        "feature_flag_id": scope.feature_flag_id,
                        "sensitivity_tier": scope.sensitivity_tier,
                        "ownership_predicates": scope.ownership_predicates or [],
                        "status": status,
                        "blocked_reason": None if status == "allowed" else "missing_scope",
                    }
                )
        return items

    def _paginate_detail(
        self,
        items: Sequence[Dict[str, Any]],
        *,
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        total_items = len(items)
        if page_size > MAX_DETAIL_ROWS:
            raise ValueError("Requested page_size exceeds maximum allowed rows.")
        if page_size <= 0:
            page_size = 1
        if page <= 0:
            page = 1
        start = (page - 1) * page_size
        if start >= MAX_DETAIL_ROWS:
            raise ValueError("Requested pagination exceeds allowed result window.")
        end = min(start + page_size, len(items))
        paginated = items[start:end]
        return {
            "catalog_version": self.catalog.version,
            "generated_at": datetime.now(timezone.utc),
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "items": paginated,
        }

    @staticmethod
    def _scope_to_endpoint(scope: ScopeEntry) -> str:
        # Translate scope identifier to a placeholder endpoint path.
        path = scope.id.replace(".", "/")
        if not path.startswith("/"):
            path = f"/api/v1/{path}"
        return path

    @staticmethod
    def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        if hasattr(row, "_mapping"):
            return dict(row._mapping)  # type: ignore[attr-defined]
        return None


@lru_cache
def get_privilege_map_service() -> PrivilegeMapService:
    """Return a singleton privilege map service instance."""
    return PrivilegeMapService()
