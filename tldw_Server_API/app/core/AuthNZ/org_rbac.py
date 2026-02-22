from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import build_sqlite_in_clause, get_db_pool
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


@dataclass
class ScopedPermissionsResult:
    permissions: list[str]
    active_org_id: int | None
    active_team_id: int | None


def _coerce_int_list(values: Sequence[int] | None) -> list[int]:
    if values is None:
        return []
    out: list[int] = []
    for value in values:
        try:
            out.append(int(value))
        except (TypeError, ValueError):
            continue
    return out


def _row_value(row, key: str, idx: int = 0) -> str | None:
    try:
        if isinstance(row, dict):
            return row.get(key)
        return row[key]
    except Exception:
        try:
            return row[idx]
        except Exception:
            return None


def _normalize_scope_mode(value: str | None) -> str:
    if not value:
        return "require_active"
    mode = str(value).strip().lower()
    if mode in {"union", "active_only", "require_active"}:
        return mode
    return "require_active"


def _normalize_active_id(raw: int | None, allowed_ids: Sequence[int]) -> int | None:
    if raw is None:
        return None
    try:
        candidate = int(raw)
    except (TypeError, ValueError):
        return None
    return candidate if candidate in allowed_ids else None


def _normalize_denylist(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    for raw in values:
        if raw is None:
            continue
        item = str(raw).strip().lower()
        if item:
            out.append(item)
    return out


def _is_denied(permission: str, denylist: Iterable[str]) -> bool:
    perm = str(permission).strip().lower()
    if not perm:
        return True
    for item in denylist:
        if item.endswith("*"):
            prefix = item[:-1]
            if perm.startswith(prefix):
                return True
        elif item.endswith(".") or item.endswith(":"):
            if perm.startswith(item):
                return True
        else:
            if perm == item:
                return True
    return False


def _filter_permissions(permissions: Iterable[str], denylist: Iterable[str]) -> list[str]:
    filtered: list[str] = []
    for perm in permissions:
        if perm and not _is_denied(perm, denylist):
            filtered.append(str(perm))
    return filtered


async def _fetch_org_memberships(
    *,
    user_id: int,
    org_ids: Sequence[int] | None,
) -> list[dict]:
    if org_ids is not None and not org_ids:
        return []

    params: list = [user_id]
    clause = ""
    if org_ids:
        placeholders, org_params = build_sqlite_in_clause(list(org_ids))
        clause = f" AND org_id IN ({placeholders})"
        params.extend(list(org_params))

    org_memberships_sql_template = """
        SELECT org_id, role
        FROM org_members
        WHERE user_id = ? AND status = 'active'{clause}
        """
    org_memberships_sql = org_memberships_sql_template.format_map(locals())  # nosec B608
    pool = await get_db_pool()
    rows = await pool.fetchall(
        org_memberships_sql,
        params,
    )
    results: list[dict] = []
    for row in rows or []:
        org_id = _row_value(row, "org_id", 0)
        role = _row_value(row, "role", 1)
        try:
            org_id_int = int(org_id) if org_id is not None else None
        except (TypeError, ValueError):
            org_id_int = None
        if org_id_int is None or not role:
            continue
        results.append({"org_id": org_id_int, "role": str(role).lower()})
    return results


async def _fetch_team_memberships(
    *,
    user_id: int,
    team_ids: Sequence[int] | None,
) -> list[dict]:
    if team_ids is not None and not team_ids:
        return []

    params: list = [user_id]
    clause = ""
    if team_ids:
        placeholders, team_params = build_sqlite_in_clause(list(team_ids))
        clause = f" AND tm.team_id IN ({placeholders})"
        params.extend(list(team_params))

    team_memberships_sql_template = """
        SELECT tm.team_id, tm.role, t.org_id
        FROM team_members tm
        JOIN teams t ON tm.team_id = t.id
        WHERE tm.user_id = ? AND tm.status = 'active'{clause}
        """
    team_memberships_sql = team_memberships_sql_template.format_map(locals())  # nosec B608
    pool = await get_db_pool()
    rows = await pool.fetchall(
        team_memberships_sql,
        params,
    )
    results: list[dict] = []
    for row in rows or []:
        team_id = _row_value(row, "team_id", 0)
        role = _row_value(row, "role", 1)
        org_id = _row_value(row, "org_id", 2)
        try:
            team_id_int = int(team_id) if team_id is not None else None
        except (TypeError, ValueError):
            team_id_int = None
        try:
            org_id_int = int(org_id) if org_id is not None else None
        except (TypeError, ValueError):
            org_id_int = None
        if team_id_int is None or org_id_int is None or not role:
            continue
        results.append(
            {
                "team_id": team_id_int,
                "org_id": org_id_int,
                "role": str(role).lower(),
            }
        )
    return results


async def _fetch_role_permissions(
    *,
    table: str,
    role_column: str,
    roles: Iterable[str],
) -> list[str]:
    role_list = sorted({str(role).lower() for role in roles if role})
    if not role_list:
        return []

    placeholders, params = build_sqlite_in_clause(role_list)
    role_permissions_sql_template = """
        SELECT DISTINCT p.name
        FROM {table} rp
        JOIN permissions p ON p.id = rp.permission_id
        WHERE rp.{role_column} IN ({placeholders})
        """
    role_permissions_sql = role_permissions_sql_template.format_map(locals())  # nosec B608
    pool = await get_db_pool()
    rows = await pool.fetchall(
        role_permissions_sql,
        params,
    )
    perms: list[str] = []
    for row in rows or []:
        name = _row_value(row, "name", 0)
        if name:
            perms.append(str(name))
    return perms


async def resolve_scoped_permissions(
    *,
    user_id: int | None,
    org_ids: Sequence[int] | None = None,
    team_ids: Sequence[int] | None = None,
    active_org_id: int | None = None,
    active_team_id: int | None = None,
    scope_mode: str | None = None,
) -> ScopedPermissionsResult:
    settings = get_settings()
    if not settings.ORG_RBAC_PROPAGATION_ENABLED or user_id is None:
        return ScopedPermissionsResult([], active_org_id, active_team_id)

    mode = _normalize_scope_mode(scope_mode or settings.ORG_RBAC_SCOPE_MODE)
    org_ids_list = _coerce_int_list(org_ids)
    team_ids_list = _coerce_int_list(team_ids)

    org_memberships = await _fetch_org_memberships(user_id=user_id, org_ids=org_ids)
    team_memberships = await _fetch_team_memberships(user_id=user_id, team_ids=team_ids)

    org_roles_by_id = {
        int(m["org_id"]): str(m["role"]).lower() for m in org_memberships if m.get("org_id")
    }
    team_roles_by_id = {
        int(m["team_id"]): str(m["role"]).lower() for m in team_memberships if m.get("team_id")
    }
    team_to_org = {
        int(m["team_id"]): int(m["org_id"])
        for m in team_memberships
        if m.get("team_id") is not None and m.get("org_id") is not None
    }

    # Allow None to signal "derive from memberships"; empty lists mean "no scope".
    if org_ids is None:
        org_ids_list = sorted(org_roles_by_id.keys())
    if team_ids is None:
        team_ids_list = sorted(team_roles_by_id.keys())

    active_org_id = _normalize_active_id(active_org_id, org_ids_list)
    active_team_id = _normalize_active_id(active_team_id, team_ids_list)

    if active_team_id is not None and active_org_id is None:
        derived_org = team_to_org.get(active_team_id)
        if derived_org is not None and (not org_ids_list or derived_org in org_ids_list):
            active_org_id = derived_org

    if mode == "require_active" and active_org_id is None and active_team_id is None:
        if org_ids_list:
            active_org_id = org_ids_list[0]
        elif team_ids_list:
            active_team_id = team_ids_list[0]
            active_org_id = team_to_org.get(active_team_id)

    eligible_org_ids: list[int] = []
    eligible_team_ids: list[int] = []
    if mode == "union":
        eligible_org_ids = list(org_ids_list)
        eligible_team_ids = list(team_ids_list)
    else:
        if active_org_id is not None:
            eligible_org_ids = [active_org_id]
        if active_team_id is not None:
            eligible_team_ids = [active_team_id]
        elif active_org_id is not None:
            eligible_team_ids = [
                team_id for team_id, org_id in team_to_org.items() if org_id == active_org_id
            ]

    if mode == "require_active" and not eligible_org_ids and not eligible_team_ids:
        return ScopedPermissionsResult([], active_org_id, active_team_id)

    org_roles = {
        org_roles_by_id[org_id]
        for org_id in eligible_org_ids
        if org_id in org_roles_by_id
    }
    team_roles = {
        team_roles_by_id[team_id]
        for team_id in eligible_team_ids
        if team_id in team_roles_by_id
    }

    org_permissions = await _fetch_role_permissions(
        table="org_role_permissions",
        role_column="org_role",
        roles=org_roles,
    )
    team_permissions = await _fetch_role_permissions(
        table="team_role_permissions",
        role_column="team_role",
        roles=team_roles,
    )

    denylist = _normalize_denylist(settings.ORG_RBAC_SCOPED_PERMISSION_DENYLIST or [])
    scoped_permissions = _filter_permissions(org_permissions + team_permissions, denylist)

    return ScopedPermissionsResult(
        sorted(set(scoped_permissions)),
        active_org_id,
        active_team_id,
    )


async def apply_scoped_permissions(
    *,
    user_id: int | None,
    base_permissions: Sequence[str],
    org_ids: Sequence[int] | None = None,
    team_ids: Sequence[int] | None = None,
    active_org_id: int | None = None,
    active_team_id: int | None = None,
    scope_mode: str | None = None,
) -> ScopedPermissionsResult:
    settings = get_settings()
    base_list = [str(p) for p in base_permissions or [] if p]
    if not settings.ORG_RBAC_PROPAGATION_ENABLED or user_id is None:
        return ScopedPermissionsResult(sorted(set(base_list)), active_org_id, active_team_id)

    try:
        scoped = await resolve_scoped_permissions(
            user_id=user_id,
            org_ids=org_ids,
            team_ids=team_ids,
            active_org_id=active_org_id,
            active_team_id=active_team_id,
            scope_mode=scope_mode,
        )
    except Exception as exc:
        if settings.PII_REDACT_LOGS:
            logger.warning("Scoped RBAC resolver failed (details redacted): {}", type(exc).__name__)
        else:
            logger.warning(
                "Scoped RBAC resolver failed for user_id={} ({})",
                user_id,
                type(exc).__name__,
            )
        return ScopedPermissionsResult(sorted(set(base_list)), active_org_id, active_team_id)

    merged = sorted(set(base_list) | set(scoped.permissions or []))
    return ScopedPermissionsResult(merged, scoped.active_org_id, scoped.active_team_id)
