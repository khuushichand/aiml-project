from __future__ import annotations

from typing import Optional, Dict, Any, List

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


async def create_organization(
    *,
    name: str,
    owner_user_id: Optional[int] = None,
    slug: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pool: DatabasePool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    return await repo.create_organization(
        name=name,
        owner_user_id=owner_user_id,
        slug=slug,
        metadata=metadata,
    )


async def list_organizations(
    limit: int = 100,
    offset: int = 0,
    q: Optional[str] = None,
    *,
    with_total: bool = False,
) -> List[Dict[str, Any]] | tuple[List[Dict[str, Any]], int]:
    """List organizations with optional server-side filtering and total count.

    When with_total=True, returns a tuple of (rows, total). Otherwise returns rows only.
    """
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    rows, total = await repo.list_organizations(limit=limit, offset=offset, q=q, with_total=with_total)
    return (rows, total) if with_total else rows


async def create_team(
    *,
    org_id: int,
    name: str,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    return await repo.create_team(
        org_id=org_id,
        name=name,
        slug=slug,
        description=description,
        metadata=metadata,
    )


async def add_team_member(*, team_id: int, user_id: int, role: str = "member") -> Dict[str, Any]:
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    return await repo.add_team_member(team_id=team_id, user_id=user_id, role=role)


async def list_team_members(team_id: int) -> List[Dict[str, Any]]:
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    return await repo.list_team_members(team_id)


async def list_memberships_for_user(user_id: int) -> List[Dict[str, Any]]:
    """List team memberships (and org_id) for a given user.

    Returns: list of {team_id, org_id, role}
    """
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    return await repo.list_memberships_for_user(user_id)


# ============================
# Organization membership APIs
# ============================

async def add_org_member(*, org_id: int, user_id: int, role: str = "member") -> Dict[str, Any]:
    """Add a user to an organization (idempotent)."""
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    return await repo.add_org_member(org_id=org_id, user_id=user_id, role=role)


async def list_org_members(
    *, org_id: int, limit: int = 100, offset: int = 0, role: Optional[str] = None, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List members of an organization with pagination and optional filters."""
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    return await repo.list_org_members(
        org_id=org_id,
        limit=limit,
        offset=offset,
        role=role,
        status=status,
    )


async def remove_org_member(*, org_id: int, user_id: int) -> Dict[str, Any]:
    """Remove a user from an organization. Returns removal status."""
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    return await repo.remove_org_member(org_id=org_id, user_id=user_id)


async def update_org_member_role(*, org_id: int, user_id: int, role: str) -> Optional[Dict[str, Any]]:
    """Update an org member's role; returns updated row or None if missing."""
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    return await repo.update_org_member_role(org_id=org_id, user_id=user_id, role=role)


async def list_org_memberships_for_user(user_id: int) -> List[Dict[str, Any]]:
    """List org memberships for a given user: [{org_id, role}]."""
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    repo = AuthnzOrgsTeamsRepo(pool)
    return await repo.list_org_memberships_for_user(user_id)


async def remove_team_member(*, team_id: int, user_id: int) -> Dict[str, Any]:
    """Remove a user from a team. Returns a simple dict with removal status."""
    pool = await get_db_pool()
    from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

    try:
        repo = AuthnzOrgsTeamsRepo(pool)
        return await repo.remove_team_member(team_id=team_id, user_id=user_id)
    except Exception as e:  # pragma: no cover - defensive logging wrapper
        redact_logs = False
        try:
            redact_logs = get_settings().PII_REDACT_LOGS
        except Exception as settings_err:
            logger.debug(f"Failed to get settings for PII redaction: {settings_err}")
        if redact_logs:
            logger.error(
                f"Failed to remove team member (details redacted) from team_id={team_id}: {e}"
            )
        else:
            logger.error(
                f"Failed to remove team member user_id={user_id} from team_id={team_id}: {e}"
            )
        return {"team_id": int(team_id), "user_id": int(user_id), "removed": False}
