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
        self._feature_flag_map = {flag.id: flag for flag in self.catalog.feature_flags}
        self._scope_lookup = {scope.id: scope for scope in self.catalog.scopes}

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

        trends: List[Dict[str, Any]] = []
        if include_trends:
            trends = self._build_trends_placeholder(group_by=group_by, since=since)

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
            "trends": trends,
            "metadata": {
                "filters": {
                    "group_by": group_by,
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
        *, team_id: str, group_by: str, include_trends: bool, since: Optional[datetime]
    ) -> Dict[str, Any]:
        users = await self._fetch_users()
        team_users = await self._filter_users_for_team(users, team_id=team_id)
        generated_at = datetime.now(timezone.utc)
        if group_by == "resource":
            buckets = self._group_by_resource(team_users)
        else:
            buckets = self._group_by_member(team_users)

        trends: List[Dict[str, Any]] = []
        if include_trends:
            trends = self._build_trends_placeholder(group_by=group_by, since=since, team_id=team_id)

        return {
            "catalog_version": self.catalog.version,
            "generated_at": generated_at,
            "group_by": group_by,
            "buckets": buckets,
            "trends": trends,
            "metadata": {
                "filters": {
                    "team_id": team_id,
                    "group_by": group_by,
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

    async def get_self_map(
        self,
        *,
        user_id: str,
        resource: Optional[str],
    ) -> Dict[str, Any]:
        users = await self._fetch_users()
        filtered = [u for u in users if str(u["id"]) == str(user_id)]
        items = self._build_detail_items(filtered, resource_filter=resource)
        condensed_items = [
            {
                "endpoint": item["endpoint"],
                "method": item["method"],
                "privilege_scope_id": item["privilege_scope_id"],
                "feature_flag_id": item["feature_flag_id"],
                "sensitivity_tier": item["sensitivity_tier"],
                "ownership_predicates": item["ownership_predicates"],
                "status": item["status"],
                "blocked_reason": item["blocked_reason"],
            }
            for item in items
        ]
        recommended_actions = self._build_recommended_actions(items)
        return {
            "catalog_version": self.catalog.version,
            "generated_at": datetime.now(timezone.utc),
            "items": condensed_items,
            "recommended_actions": recommended_actions,
        }

    async def build_snapshot_summary(
        self,
        *,
        target_scope: str,
        org_id: Optional[str],
        team_id: Optional[str],
        user_ids: Optional[Sequence[str]],
    ) -> Dict[str, Any]:
        users = await self._fetch_users()
        if target_scope == "team":
            if not team_id:
                raise ValueError("team_id required for team scope snapshot")
            users = await self._filter_users_for_team(users, team_id=team_id)
        elif target_scope == "org":
            if not org_id:
                raise ValueError("org_id required for org scope snapshot")
            users = await self._filter_users_for_org(users, org_id=org_id)
        elif target_scope == "user":
            target_ids = {str(uid) for uid in (user_ids or []) if uid}
            if not target_ids:
                raise ValueError("user_ids required for user scope snapshot")
            users = [user for user in users if str(user.get("id")) in target_ids]

        scope_ids: Set[str] = set()
        sensitivity_breakdown: Dict[str, int] = defaultdict(int)
        for user in users:
            for scope_id in user.get("allowed_scopes", set()):
                scope_ids.add(scope_id)

        for scope_id in scope_ids:
            scope = self._scope_lookup.get(scope_id)
            if scope:
                sensitivity_breakdown[scope.sensitivity_tier] += 1

        summary = {
            "users": len(users),
            "scopes": len(scope_ids),
            "endpoints": len(scope_ids),
            "scope_ids": sorted(scope_ids),
            "sensitivity_breakdown": dict(sensitivity_breakdown),
        }
        return summary

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
            if not rows:
                raise ValueError("No users returned")

            base_users: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                record = self._row_to_dict(row)
                if not record or not record.get("is_active", 1):
                    continue
                user_id = str(record.get("id"))
                base_users[user_id] = {
                    "id": record.get("id"),
                    "username": record.get("username", ""),
                    "primary_role": (record.get("role") or "user"),
                    "roles": [],
                    "permissions": set(),
                }

            if not base_users:
                raise ValueError("No active users found")

            await self._hydrate_roles_and_permissions(pool, base_users)
            users: List[Dict[str, Any]] = []
            for payload in base_users.values():
                roles = payload.get("roles") or [payload.get("primary_role")]
                roles = sorted({role for role in roles if role})
                permissions = {perm for perm in payload.get("permissions", set()) if perm}
                feature_flags = self._feature_flags_for_user(roles, permissions)
                allowed_scopes = self._resolve_scopes_for_user(roles, permissions)
                primary_role = roles[0] if roles else payload.get("primary_role", "user")
                users.append(
                    {
                        "id": payload["id"],
                        "username": payload["username"],
                        "primary_role": primary_role,
                        "roles": roles,
                        "permissions": sorted(permissions),
                        "feature_flags": feature_flags,
                        "allowed_scopes": allowed_scopes,
                    }
                )
            return users
        except Exception as exc:
            logger.debug("Falling back to single-user privilege dataset: %s", exc)

        # Fallback: single-user mode or empty DB
        single_user = get_single_user_instance()
        default_role = "admin" if is_single_user_mode() else (single_user.roles[0] if single_user.roles else "admin")
        feature_flags = self._feature_flags_for_user([default_role], set())
        allowed_scopes = self._resolve_scopes_for_user([default_role], [])
        if not allowed_scopes:
            allowed_scopes = {scope.id for scope in self.catalog.scopes}
        return [
            {
                "id": single_user.id,
                "username": single_user.username,
                "primary_role": default_role or "admin",
                "roles": [default_role or "admin"],
                "permissions": [],
                "feature_flags": feature_flags,
                "allowed_scopes": allowed_scopes,
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

    async def _filter_users_for_org(
        self,
        users: List[Dict[str, Any]],
        *,
        org_id: str,
    ) -> List[Dict[str, Any]]:
        memberships = await self._fetch_team_memberships()
        user_ids = {
            str(m["user_id"])
            for m in memberships
            if str(m.get("org_id")) == str(org_id)
        }
        if not user_ids:
            return users
        return [user for user in users if str(user["id"]) in user_ids]

    async def _hydrate_roles_and_permissions(
        self,
        pool: DatabasePool,
        base_users: Dict[str, Dict[str, Any]],
    ) -> None:
        role_assignments: Dict[str, Set[str]] = defaultdict(set)
        try:
            rows = await pool.fetchall(
                """
                SELECT ur.user_id, r.name AS role_name
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.id
                """
            )
            for row in rows:
                record = self._row_to_dict(row)
                if not record:
                    continue
                user_id = str(record.get("user_id"))
                role_name = record.get("role_name")
                if user_id in base_users and role_name:
                    role_assignments[user_id].add(role_name)
        except Exception as exc:
            logger.debug("Unable to load role assignments: %s", exc)

        role_permissions: Dict[str, Set[str]] = defaultdict(set)
        try:
            rows = await pool.fetchall(
                """
                SELECT r.name AS role_name, p.name AS permission_name
                FROM role_permissions rp
                JOIN roles r ON rp.role_id = r.id
                JOIN permissions p ON rp.permission_id = p.id
                """
            )
            for row in rows:
                record = self._row_to_dict(row)
                if not record:
                    continue
                role_name = record.get("role_name")
                permission_name = record.get("permission_name")
                if role_name and permission_name:
                    role_permissions[role_name].add(permission_name)
        except Exception as exc:
            logger.debug("Unable to load role permissions: %s", exc)

        user_permissions_direct: Dict[str, Set[str]] = defaultdict(set)
        try:
            rows = await pool.fetchall(
                """
                SELECT up.user_id, p.name AS permission_name, up.granted
                FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                """
            )
            for row in rows:
                record = self._row_to_dict(row)
                if not record:
                    continue
                granted = record.get("granted")
                if granted is not None and not bool(granted):
                    continue
                user_id = str(record.get("user_id"))
                permission_name = record.get("permission_name")
                if user_id in base_users and permission_name:
                    user_permissions_direct[user_id].add(permission_name)
        except Exception as exc:
            logger.debug("Unable to load direct user permissions: %s", exc)

        for user_id, payload in base_users.items():
            roles = sorted(role_assignments.get(user_id, set())) or [payload.get("primary_role")]
            payload["roles"] = roles
            perms: Set[str] = set(user_permissions_direct.get(user_id, set()))
            for role in roles:
                perms.update(role_permissions.get(role, set()))
            payload["permissions"] = perms

    def _feature_flags_for_user(
        self,
        roles: Sequence[str],
        permissions: Sequence[str],
    ) -> Set[str]:
        enabled: Set[str] = set()
        role_set = {role.lower() for role in roles if role}
        perm_set = {perm.lower() for perm in permissions if perm}
        is_admin = bool(role_set & self._admin_roles)

        for flag_id, flag in self._feature_flag_map.items():
            if is_admin:
                enabled.add(flag_id)
                continue
            if getattr(flag, "default_state", "disabled") == "enabled":
                enabled.add(flag_id)
                continue
            allowed_roles = {r.lower() for r in getattr(flag, "allowed_roles", []) or []}
            if role_set & allowed_roles:
                enabled.add(flag_id)
                continue
            candidate_permissions = {
                flag_id.lower(),
                f"feature_flag:{flag_id}".lower(),
                f"feature_flag.{flag_id}".lower(),
            }
            if perm_set & candidate_permissions:
                enabled.add(flag_id)
        return enabled

    def _resolve_scopes_for_user(
        self,
        roles: Sequence[str],
        permissions: Sequence[str],
    ) -> Set[str]:
        role_set = {role.lower() for role in roles if role}
        perm_set = {perm.lower() for perm in permissions if perm}

        if role_set & self._admin_roles:
            return {scope.id for scope in self.catalog.scopes}

        allowed: Set[str] = set()
        for scope in self.catalog.scopes:
            granted = False
            for role in roles:
                for mapped_scope in self._role_scope_map.get(role, []):
                    if mapped_scope.id == scope.id:
                        granted = True
                        break
                if granted:
                    break

            if not granted:
                candidate_permissions = {
                    scope.id.lower(),
                    scope.id.replace(".", "_").lower(),
                    f"scope:{scope.id}".lower(),
                    f"scope.{scope.id}".lower(),
                    f"{scope.id}:read".lower(),
                    f"{scope.id}:write".lower(),
                }
                if perm_set & candidate_permissions:
                    granted = True

            if granted:
                allowed.add(scope.id)
        return allowed

    def _scopes_from_ids(self, scope_ids: Sequence[str]) -> List[ScopeEntry]:
        return [self._scope_lookup[sid] for sid in scope_ids if sid in self._scope_lookup]

    def _group_by_role(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets: Dict[str, Dict[str, Any]] = {}
        for user in users:
            role = user.get("primary_role") or "user"
            scopes = user.get("allowed_scopes", set())
            bucket = buckets.setdefault(
                role,
                {"key": role, "users": 0, "scopes": set()},
            )
            bucket["users"] += 1
            bucket["scopes"].update(scopes)

        results: List[Dict[str, Any]] = []
        for role, payload in buckets.items():
            scope_count = len(payload["scopes"])
            results.append(
                {
                    "key": role,
                    "users": payload["users"],
                    "endpoints": scope_count,
                    "scopes": scope_count,
                }
            )
        return results

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
                team["scopes"].update(user.get("allowed_scopes", set()))

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

    def _group_by_member(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets: List[Dict[str, Any]] = []
        for user in users:
            scopes = user.get("allowed_scopes", set())
            buckets.append(
                {
                    "key": str(user.get("id")),
                    "users": 1,
                    "endpoints": len(scopes),
                    "scopes": len(scopes),
                    "metadata": {
                        "username": user.get("username"),
                        "primary_role": user.get("primary_role"),
                        "roles": user.get("roles"),
                    },
                }
            )
        return buckets

    def _group_by_resource(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        resource_access: Dict[str, Dict[str, Any]] = {}
        for user in users:
            for scope in self._scopes_from_ids(user.get("allowed_scopes", set())):
                tags = scope.resource_tags or [RESOURCE_FALLBACK]
                for tag in tags:
                    bucket = resource_access.setdefault(
                        tag,
                        {"key": tag, "users": set(), "scopes": set()},
                    )
                    bucket["users"].add(str(user["id"]))
                    bucket["scopes"].add(scope.id)

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
            role = user.get("primary_role") or "user"
            if role_filter and role != role_filter:
                continue
            allowed_scopes = user.get("allowed_scopes", set())
            feature_flags = user.get("feature_flags", set())
            for scope in self.catalog.scopes:
                tags = [tag.lower() for tag in (scope.resource_tags or [RESOURCE_FALLBACK])]
                if resource_filter_lower and resource_filter_lower not in tags:
                    continue
                status = "allowed"
                blocked_reason = None
                if scope.feature_flag_id and scope.feature_flag_id not in feature_flags:
                    status = "blocked"
                    blocked_reason = "feature_flag_disabled"
                elif scope.id not in allowed_scopes:
                    status = "blocked"
                    blocked_reason = "missing_scope"
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
                        "blocked_reason": blocked_reason,
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

    def _build_trends_placeholder(
        self,
        *,
        group_by: str,
        since: Optional[datetime],
        team_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return []

    def _build_recommended_actions(
        self, items: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        actions: Dict[str, Dict[str, Any]] = {}
        for item in items:
            if item.get("status") != "blocked":
                continue
            scope_id = item.get("privilege_scope_id")
            reason = item.get("blocked_reason")
            if reason == "feature_flag_disabled":
                action_text = "Request org upgrade"
                reason_text = "Feature flag disabled"
            elif reason == "missing_scope":
                action_text = "Request scope assignment"
                reason_text = "Scope not assigned"
            else:
                continue
            key = f"{scope_id}:{reason}"
            actions[key] = {
                "scope_id": scope_id,
                "action": action_text,
                "reason": reason_text,
            }
        return list(actions.values())

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
