from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.org_team_schemas import (
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationWatchlistsSettingsResponse,
    OrganizationWatchlistsSettingsUpdate,
    OrgMemberAddRequest,
    OrgMemberListItem,
    OrgMemberRemoveResponse,
    OrgMemberResponse,
    OrgMemberRoleUpdateRequest,
    OrgMembershipItem,
    TeamCreateRequest,
    TeamMemberAddRequest,
    TeamMemberRemoveResponse,
    TeamMemberResponse,
    TeamResponse,
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, is_postgres_backend
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    DuplicateOrganizationError,
    DuplicateTeamError,
    UserRegistrationException,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    add_org_member as core_add_org_member,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    add_team_member as core_add_team_member,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    create_organization as core_create_organization,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    create_team as core_create_team,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    list_org_members as core_list_org_members,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    list_org_memberships_for_user as core_list_org_memberships_for_user,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    list_organizations as core_list_organizations,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    list_team_members as core_list_team_members,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    remove_org_member as core_remove_org_member,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    remove_team_member as core_remove_team_member,
)
from tldw_Server_API.app.core.AuthNZ.orgs_teams import (
    update_org_member_role as core_update_org_member_role,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.DB_Management.backends.base import (
    DatabaseError as BackendDatabaseError,
)
from tldw_Server_API.app.services import admin_scope_service

_ADMIN_ORGS_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    BackendDatabaseError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    json.JSONDecodeError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    UserRegistrationException,
    ValueError,
)


async def _list_teams_by_org_conn(db, org_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
    pg = await is_postgres_backend()
    if pg:
        rows = await db.fetch(
            "SELECT id, org_id, name, slug, description, COALESCE(is_active,TRUE) as is_active, created_at, updated_at FROM teams WHERE org_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            org_id, limit, offset,
        )
        return [dict(r) for r in rows]
    cur = await db.execute(
        "SELECT id, org_id, name, slug, description, COALESCE(is_active,1), created_at, updated_at FROM teams WHERE org_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (org_id, limit, offset),
    )
    rows = await cur.fetchall()
    return [
        {
            "id": r[0],
            "org_id": r[1],
            "name": r[2],
            "slug": r[3],
            "description": r[4],
            "is_active": bool(r[5]),
            "created_at": r[6],
            "updated_at": r[7],
        }
        for r in rows
    ]


async def list_teams_by_org(
    org_id: int,
    limit: int = 1000,
    offset: int = 0,
    db=None,
) -> list[dict[str, Any]]:
    try:
        if db is None:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                return await _list_teams_by_org_conn(conn, org_id, limit, offset)
        return await _list_teams_by_org_conn(db, org_id, limit, offset)
    except Exception as e:
        logger.error(f"admin_orgs_service.list_teams_by_org failed: {e}")
        raise


async def _emit_membership_audit_event(
    request,
    *,
    resource_type: str,
    resource_id: str,
    action: str,
    event_type_name: str,
    metadata: dict[str, Any],
) -> None:
    try:
        actor_id = getattr(request.state, "user_id", None)
        if not isinstance(actor_id, int):
            return
        from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
            get_audit_service_for_user,
            get_or_create_audit_service_for_user_id,
        )
        from tldw_Server_API.app.core.Audit.unified_audit_service import (
            AuditContext,
            AuditEventCategory,
            AuditEventType,
        )
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User as _User
        from tldw_Server_API.app.core.DB_Management.Users_DB import get_user_by_id as _get_user

        _ud = await _get_user(actor_id)
        _svc = None
        if _ud:
            _user = _User(**_ud)
            _svc = await get_audit_service_for_user(_user)
        if _svc is None:
            _svc = await get_or_create_audit_service_for_user_id(int(actor_id))

        _ctx = AuditContext(
            user_id=str(actor_id),
            ip_address=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
            endpoint=str(request.url.path),
            method=request.method,
        )

        event_type = getattr(AuditEventType, event_type_name, AuditEventType.DATA_WRITE)
        await _svc.log_event(
            event_type=event_type,
            category=AuditEventCategory.AUTHORIZATION,
            context=_ctx,
            resource_type=resource_type,
            resource_id=str(resource_id),
            action=action,
            metadata=metadata,
        )
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"Audit ({action}) skipped/failed: {exc}")


async def create_org(
    payload: OrganizationCreateRequest,
    principal: AuthPrincipal,
) -> OrganizationResponse:
    try:
        admin_scope_service.require_platform_admin(principal)
        row = await core_create_organization(
            name=payload.name,
            owner_user_id=payload.owner_user_id,
            slug=payload.slug,
        )
        return OrganizationResponse(**row)
    except DuplicateOrganizationError as dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with {dup.field} '{dup.value}' already exists",
        )
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to create organization: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create organization")


async def list_orgs(
    *,
    principal: AuthPrincipal,
    limit: int,
    offset: int,
    q: str | None,
    org_id: int | None,
    wants_wrapper: bool,
) -> Any:
    try:
        org_ids = await admin_scope_service.get_admin_org_ids(principal)
        if org_id is not None:
            org_ids = [org_id] if org_ids is None else [org_id] if org_id in org_ids else []

        result = await core_list_organizations(
            limit=limit,
            offset=offset,
            q=q,
            org_ids=org_ids,
            with_total=wants_wrapper,
        )
        if wants_wrapper:
            if not isinstance(result, tuple) or len(result) != 2:
                logger.error(
                    f"list_organizations returned unexpected format: {type(result).__name__}"
                )
                raise HTTPException(
                    status_code=500,
                    detail="Failed to list organizations",
                )
            rows, total = result
        else:
            rows = result[0] if isinstance(result, tuple) else result
            total = 0
        items = [OrganizationResponse(**r).model_dump() for r in rows]

        if wants_wrapper:
            has_more = (offset + len(items)) < int(total or 0)
            return {
                "items": items,
                "total": int(total or 0),
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
            }
        return items
    except HTTPException:
        raise
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to list organizations: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list organizations")


async def create_team(
    org_id: int,
    payload: TeamCreateRequest,
    principal: AuthPrincipal,
) -> TeamResponse:
    try:
        await admin_scope_service.enforce_admin_org_access(principal, org_id, require_admin=True)
        row = await core_create_team(
            org_id=org_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )
        return TeamResponse(**row)
    except DuplicateTeamError as dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Team with {dup.field} '{dup.value}' already exists in org {org_id}",
        )
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to create team: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create team")


async def list_teams(
    org_id: int,
    *,
    principal: AuthPrincipal,
    limit: int,
    offset: int,
    db,
) -> list[TeamResponse]:
    try:
        await admin_scope_service.enforce_admin_org_access(principal, org_id, require_admin=True)
        rows = await list_teams_by_org(org_id, limit=limit, offset=offset, db=db)
        return [TeamResponse(**r) for r in rows]
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to list teams: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list teams")


async def get_team(
    team_id: int,
    principal: AuthPrincipal,
) -> TeamResponse:
    try:
        team = await admin_scope_service.get_scoped_team(team_id, principal, require_admin=True)
        return TeamResponse(**team)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to fetch team {team_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch team") from exc


async def update_org_watchlists_settings(
    org_id: int,
    payload: OrganizationWatchlistsSettingsUpdate,
    *,
    principal: AuthPrincipal,
    db,
) -> OrganizationWatchlistsSettingsResponse:
    try:
        await admin_scope_service.enforce_admin_org_access(principal, org_id, require_admin=True)
        if hasattr(db, "fetchrow"):
            row = await db.fetchrow("SELECT metadata FROM organizations WHERE id = $1", org_id)
            meta_raw = row.get("metadata") if row else None
        else:
            cur = await db.execute("SELECT metadata FROM organizations WHERE id = ?", (org_id,))
            row = await cur.fetchone()
            meta_raw = row[0] if row else None
        if not row:
            raise HTTPException(status_code=404, detail="organization_not_found")
        meta: dict[str, Any]
        try:
            meta = json.loads(meta_raw) if meta_raw else {}
            if not isinstance(meta, dict):
                meta = {}
        except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS:
            meta = {}

        wl = meta.get("watchlists") if isinstance(meta.get("watchlists"), dict) else {}
        changed = False
        if payload.require_include_default is not None:
            wl["require_include_default"] = bool(payload.require_include_default)
            changed = True
        if changed:
            meta["watchlists"] = wl
            if hasattr(db, "fetchrow"):
                await db.execute(
                    "UPDATE organizations SET metadata = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                    json.dumps(meta), org_id,
                )
            else:
                await db.execute(
                    "UPDATE organizations SET metadata = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(meta), org_id),
                )
        return OrganizationWatchlistsSettingsResponse(
            org_id=org_id,
            require_include_default=wl.get("require_include_default"),
        )
    except HTTPException:
        raise
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to update org watchlists settings for org {org_id}: {exc}")
        raise HTTPException(status_code=500, detail="failed_to_update_org_watchlists_settings")


async def get_org_watchlists_settings(
    org_id: int,
    *,
    principal: AuthPrincipal,
    db,
) -> OrganizationWatchlistsSettingsResponse:
    try:
        await admin_scope_service.enforce_admin_org_access(principal, org_id, require_admin=True)
        if hasattr(db, "fetchrow"):
            row = await db.fetchrow("SELECT metadata FROM organizations WHERE id = $1", org_id)
            meta_raw = row.get("metadata") if row else None
        else:
            cur = await db.execute("SELECT metadata FROM organizations WHERE id = ?", (org_id,))
            row = await cur.fetchone()
            meta_raw = row[0] if row else None
        if not row:
            raise HTTPException(status_code=404, detail="organization_not_found")
        require_include_default = None
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                if isinstance(meta, dict):
                    wl = meta.get("watchlists") if isinstance(meta.get("watchlists"), dict) else None
                    if isinstance(wl, dict) and isinstance(wl.get("require_include_default"), bool):
                        require_include_default = bool(wl.get("require_include_default"))
                    elif isinstance(meta.get("watchlists_require_include_default"), bool):
                        require_include_default = bool(meta.get("watchlists_require_include_default"))
            except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS:
                pass
        return OrganizationWatchlistsSettingsResponse(org_id=org_id, require_include_default=require_include_default)
    except HTTPException:
        raise
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to fetch org watchlists settings for org {org_id}: {exc}")
        raise HTTPException(status_code=500, detail="failed_to_fetch_org_watchlists_settings")


async def add_team_member(
    team_id: int,
    payload: TeamMemberAddRequest,
    request,
    principal: AuthPrincipal,
) -> TeamMemberResponse:
    try:
        await admin_scope_service.get_scoped_team(team_id, principal, require_admin=True)
        row = await core_add_team_member(
            team_id=team_id,
            user_id=payload.user_id,
            role=payload.role or "member",
        )
        await _emit_membership_audit_event(
            request,
            resource_type="team",
            resource_id=str(team_id),
            action="team_member.add",
            event_type_name="DATA_WRITE",
            metadata={"target_user_id": payload.user_id, "role": payload.role or "member"},
        )
        return TeamMemberResponse(**row)
    except HTTPException:
        raise
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to add team member: {exc}")
        raise HTTPException(status_code=500, detail="Failed to add team member")


async def list_team_members(
    team_id: int,
    *,
    principal: AuthPrincipal,
) -> list[TeamMemberResponse]:
    try:
        team = await admin_scope_service.get_scoped_team(team_id, principal, require_admin=True)
        rows = await core_list_team_members(team_id)
        org_id = team.get("org_id") if isinstance(team, dict) else None
        items: list[TeamMemberResponse] = []
        for row in rows:
            payload = dict(row)
            payload["team_id"] = team_id
            if org_id is not None:
                payload["org_id"] = org_id
            items.append(TeamMemberResponse(**payload))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to list team members: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list team members") from exc
    return items


async def remove_team_member(
    team_id: int,
    user_id: int,
    request,
    principal: AuthPrincipal,
) -> TeamMemberRemoveResponse:
    try:
        await admin_scope_service.get_scoped_team(team_id, principal, require_admin=True)
        res = await core_remove_team_member(team_id=team_id, user_id=user_id)
        removed = bool(res.get("removed"))
        if not removed:
            return TeamMemberRemoveResponse(
                message="No membership found",
                team_id=int(res.get("team_id", team_id)),
                user_id=int(res.get("user_id", user_id)),
                removed=False,
            )
        await _emit_membership_audit_event(
            request,
            resource_type="team",
            resource_id=str(team_id),
            action="team_member.remove",
            event_type_name="DATA_DELETE",
            metadata={"target_user_id": user_id},
        )
        return TeamMemberRemoveResponse(
            message="Team member removed",
            team_id=int(res.get("team_id", team_id)),
            user_id=int(res.get("user_id", user_id)),
            removed=True,
        )
    except HTTPException:
        raise
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to remove team member user_id={user_id} from team_id={team_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to remove team member")


async def add_org_member(
    org_id: int,
    payload: OrgMemberAddRequest,
    request,
    principal: AuthPrincipal,
) -> OrgMemberResponse:
    try:
        await admin_scope_service.enforce_admin_org_access(principal, org_id, require_admin=True)
        row = await core_add_org_member(
            org_id=org_id,
            user_id=payload.user_id,
            role=payload.role or "member",
        )
        await _emit_membership_audit_event(
            request,
            resource_type="organization",
            resource_id=str(org_id),
            action="org_member.add",
            event_type_name="DATA_WRITE",
            metadata={"target_user_id": payload.user_id, "role": payload.role or "member"},
        )
        return OrgMemberResponse(**row)
    except HTTPException:
        raise
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to add org member: {exc}")
        raise HTTPException(status_code=500, detail="Failed to add org member")


async def list_org_members(
    org_id: int,
    *,
    limit: int,
    offset: int,
    role: str | None,
    status_filter: str | None,
    principal: AuthPrincipal,
) -> list[OrgMemberListItem]:
    try:
        await admin_scope_service.enforce_admin_org_access(principal, org_id, require_admin=True)
        rows = await core_list_org_members(org_id=org_id, limit=limit, offset=offset, role=role, status=status_filter)
        out: list[OrgMemberListItem] = []
        for r in rows:
            d = dict(r)
            try:
                from datetime import datetime as _dt
                if isinstance(d.get("added_at"), _dt):
                    d["added_at"] = d["added_at"].isoformat()
            except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS:
                pass
            out.append(OrgMemberListItem(**d))
        return out
    except HTTPException:
        raise
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to list org members: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list org members")


async def remove_org_member(
    org_id: int,
    user_id: int,
    request,
    principal: AuthPrincipal,
) -> OrgMemberRemoveResponse:
    try:
        await admin_scope_service.enforce_admin_org_access(principal, org_id, require_admin=True)
        res = await core_remove_org_member(org_id=org_id, user_id=user_id)
        if res.get("error") == "owner_required":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization must retain at least one owner",
            )
        removed = bool(res.get("removed"))
        if not removed:
            return OrgMemberRemoveResponse(
                message="No membership found",
                org_id=int(res.get("org_id", org_id)),
                user_id=int(res.get("user_id", user_id)),
                removed=False,
            )
        await _emit_membership_audit_event(
            request,
            resource_type="organization",
            resource_id=str(org_id),
            action="org_member.remove",
            event_type_name="DATA_DELETE",
            metadata={"target_user_id": user_id},
        )
        return OrgMemberRemoveResponse(
            message="Org member removed",
            org_id=int(res.get("org_id", org_id)),
            user_id=int(res.get("user_id", user_id)),
            removed=True,
        )
    except HTTPException:
        raise
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to remove org member user_id={user_id} from org_id={org_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to remove org member")


async def update_org_member_role(
    org_id: int,
    user_id: int,
    payload: OrgMemberRoleUpdateRequest,
    request,
    principal: AuthPrincipal,
) -> OrgMemberResponse:
    try:
        await admin_scope_service.enforce_admin_org_access(principal, org_id, require_admin=True)
        row = await core_update_org_member_role(org_id=org_id, user_id=user_id, role=payload.role)
        if not row:
            raise HTTPException(status_code=404, detail="Org membership not found")
        if row.get("error") == "owner_required":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization must retain at least one owner",
            )
        await _emit_membership_audit_event(
            request,
            resource_type="organization",
            resource_id=str(org_id),
            action="org_member.update",
            event_type_name="DATA_UPDATE",
            metadata={"target_user_id": user_id, "new_role": payload.role},
        )
        return OrgMemberResponse(**row)
    except HTTPException:
        raise
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to update org member role user_id={user_id} org_id={org_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update org member role")


async def list_user_org_memberships(
    user_id: int,
    principal: AuthPrincipal,
) -> list[OrgMembershipItem]:
    try:
        await admin_scope_service.enforce_admin_user_scope(principal, user_id, require_hierarchy=False)
        rows = await core_list_org_memberships_for_user(user_id)
        return [OrgMembershipItem(**r) for r in rows]
    except _ADMIN_ORGS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Failed to list org memberships for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list org memberships")
