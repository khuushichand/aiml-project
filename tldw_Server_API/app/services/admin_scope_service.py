from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException, status

from tldw_Server_API.app.api.v1.API_Deps.org_deps import ROLE_HIERARCHY
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    get_team,
    list_memberships_for_user,
    list_org_memberships_for_user,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, is_single_user_principal

REQUIRED_ADMIN_RANK = ROLE_HIERARCHY.get("admin", 3)
REQUIRED_TEAM_ADMIN_RANK = ROLE_HIERARCHY.get("lead", 2)
PLATFORM_ADMIN_ROLES = {"owner", "super_admin", "admin"}


def _enterprise_admin_mode_enabled() -> bool:
    raw_value = os.getenv("ADMIN_UI_ENTERPRISE_MODE", "")
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def role_rank(role: str | None) -> int:
    if role is None:
        return 0
    return ROLE_HIERARCHY.get(str(role).strip().lower(), 0)


def is_platform_admin(principal: AuthPrincipal) -> bool:
    if is_single_user_principal(principal):
        return not _enterprise_admin_mode_enabled()
    roles = {str(role).strip().lower() for role in (principal.roles or [])}
    return bool(roles & PLATFORM_ADMIN_ROLES)


def require_platform_admin(principal: AuthPrincipal) -> None:
    if is_platform_admin(principal):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Platform admin role required",
    )


async def enforce_admin_user_scope(
    principal: AuthPrincipal,
    target_user_id: int,
    *,
    require_hierarchy: bool,
) -> None:
    """Enforce shared org/team membership and optional role hierarchy for admin actions."""
    if is_platform_admin(principal):
        return

    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage users",
        )

    admin_memberships = await list_org_memberships_for_user(principal.user_id)
    target_memberships = await list_org_memberships_for_user(target_user_id)

    admin_org_roles = {
        m.get("org_id"): str(m.get("role") or "member").strip().lower()
        for m in admin_memberships
        if m.get("org_id") is not None
    }
    target_org_roles = {
        m.get("org_id"): str(m.get("role") or "member").strip().lower()
        for m in target_memberships
        if m.get("org_id") is not None
    }

    shared_orgs = set(admin_org_roles) & set(target_org_roles)
    if shared_orgs and not require_hierarchy:
        return

    if shared_orgs:
        for org_id in shared_orgs:
            admin_role = admin_org_roles.get(org_id)
            target_role = target_org_roles.get(org_id)
            if role_rank(admin_role) >= REQUIRED_ADMIN_RANK and role_rank(admin_role) >= role_rank(target_role):
                return

    admin_team_memberships = await list_memberships_for_user(principal.user_id)
    target_team_memberships = await list_memberships_for_user(target_user_id)

    admin_team_roles = {
        m.get("team_id"): str(m.get("role") or "member").strip().lower()
        for m in admin_team_memberships
        if m.get("team_id") is not None
    }
    target_team_roles = {
        m.get("team_id"): str(m.get("role") or "member").strip().lower()
        for m in target_team_memberships
        if m.get("team_id") is not None
    }

    shared_teams = set(admin_team_roles) & set(target_team_roles)
    if shared_teams:
        for team_id in shared_teams:
            admin_role = admin_team_roles.get(team_id)
            target_role = target_team_roles.get(team_id)
            if role_rank(admin_role) < REQUIRED_TEAM_ADMIN_RANK:
                continue
            if not require_hierarchy or role_rank(admin_role) >= role_rank(target_role):
                return

    if not shared_orgs and not shared_teams:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage users outside your organization or team",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to update this user",
    )


async def get_admin_org_ids(principal: AuthPrincipal) -> list[int] | None:
    if is_platform_admin(principal):
        return None
    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access organization data",
        )
    memberships = await list_org_memberships_for_user(principal.user_id)
    return [int(m.get("org_id")) for m in memberships if m.get("org_id") is not None]


async def enforce_admin_org_access(
    principal: AuthPrincipal,
    org_id: int,
    *,
    require_admin: bool = True,
) -> None:
    if is_platform_admin(principal):
        return
    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this organization",
        )
    memberships = await list_org_memberships_for_user(principal.user_id)
    membership = next((m for m in memberships if m.get("org_id") == org_id), None)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this organization",
        )
    if require_admin and role_rank(membership.get("role")) < REQUIRED_ADMIN_RANK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin role required",
        )


async def get_scoped_team(
    team_id: int,
    principal: AuthPrincipal,
    *,
    require_admin: bool = True,
) -> dict[str, Any]:
    team = await get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team_not_found")
    await enforce_admin_org_access(
        principal,
        int(team.get("org_id")),
        require_admin=require_admin,
    )
    return team
