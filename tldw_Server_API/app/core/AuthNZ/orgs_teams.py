from __future__ import annotations

from typing import Optional, Dict, Any, List

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool
from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo


async def _get_orgs_teams_repo() -> AuthnzOrgsTeamsRepo:
    """
    Resolve the shared organizations/teams repository for the current AuthNZ database.

    This helper centralizes DatabasePool acquisition so higher-level helpers do not
    need to duplicate pool wiring or imports.
    """
    pool: DatabasePool = await get_db_pool()
    return AuthnzOrgsTeamsRepo(pool)


async def create_organization(
    *,
    name: str,
    owner_user_id: Optional[int] = None,
    slug: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new organization.

    Parameters:
        name: Human-readable organization name.
        owner_user_id: Optional user id to set as the organization owner.
        slug: Optional unique slug identifier.
        metadata: Optional JSON-serializable metadata mapping.

    Returns:
        A dict containing the created organization's fields (e.g. id, name, slug).
    """
    repo = await _get_orgs_teams_repo()
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
    repo = await _get_orgs_teams_repo()
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
    """
    Create a team within an organization.

    Parameters:
        org_id: Owning organization id.
        name: Team name (unique per organization).
        slug: Optional slug identifier.
        description: Optional human-readable description.
        metadata: Optional JSON-serializable metadata mapping.

    Returns:
        A dict containing the created team's fields (e.g. id, org_id, name).
    """
    repo = await _get_orgs_teams_repo()
    return await repo.create_team(
        org_id=org_id,
        name=name,
        slug=slug,
        description=description,
        metadata=metadata,
    )


async def add_team_member(*, team_id: int, user_id: int, role: str = "member") -> Dict[str, Any]:
    """
    Add a user to a team (idempotent).

    If the user is already a member, returns the existing membership row.
    """
    repo = await _get_orgs_teams_repo()
    return await repo.add_team_member(team_id=team_id, user_id=user_id, role=role)


async def list_team_members(team_id: int) -> List[Dict[str, Any]]:
    """
    List members of a team ordered by join time.

    Returns dicts containing at least ``user_id`` and ``role``.
    """
    repo = await _get_orgs_teams_repo()
    return await repo.list_team_members(team_id)


async def list_memberships_for_user(user_id: int) -> List[Dict[str, Any]]:
    """List team memberships (and org_id) for a given user.

    Returns: list of {team_id, org_id, role}
    """
    repo = await _get_orgs_teams_repo()
    return await repo.list_memberships_for_user(user_id)


# ============================
# Organization membership APIs
# ============================

async def add_org_member(*, org_id: int, user_id: int, role: str = "member") -> Dict[str, Any]:
    """Add a user to an organization (idempotent)."""
    repo = await _get_orgs_teams_repo()
    return await repo.add_org_member(org_id=org_id, user_id=user_id, role=role)


async def list_org_members(
    *, org_id: int, limit: int = 100, offset: int = 0, role: Optional[str] = None, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List members of an organization with pagination and optional filters."""
    repo = await _get_orgs_teams_repo()
    return await repo.list_org_members(
        org_id=org_id,
        limit=limit,
        offset=offset,
        role=role,
        status=status,
    )


async def remove_org_member(*, org_id: int, user_id: int) -> Dict[str, Any]:
    """Remove a user from an organization. Returns removal status."""
    repo = await _get_orgs_teams_repo()
    return await repo.remove_org_member(org_id=org_id, user_id=user_id)


async def update_org_member_role(*, org_id: int, user_id: int, role: str) -> Optional[Dict[str, Any]]:
    """Update an org member's role; returns updated row or None if missing."""
    repo = await _get_orgs_teams_repo()
    return await repo.update_org_member_role(org_id=org_id, user_id=user_id, role=role)


async def list_org_memberships_for_user(user_id: int) -> List[Dict[str, Any]]:
    """List org memberships for a given user: [{org_id, role}]."""
    repo = await _get_orgs_teams_repo()
    return await repo.list_org_memberships_for_user(user_id)


async def remove_team_member(*, team_id: int, user_id: int) -> Dict[str, Any]:
    """Remove a user from a team. Returns a simple dict with removal status."""
    repo = await _get_orgs_teams_repo()
    return await repo.remove_team_member(team_id=team_id, user_id=user_id)
