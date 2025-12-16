from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import (
    AuthnzOrgsTeamsRepo,
    DEFAULT_BASE_TEAM_NAME,
)


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authnz_orgs_teams_repo_membership_postgres(test_db_pool):
    """AuthnzOrgsTeamsRepo membership helpers should work on Postgres."""
    pool = test_db_pool

    # Create two users
    now = datetime.utcnow().replace(microsecond=0)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (uuid, username, email, password_hash, role,
                               is_active, is_verified, storage_quota_mb, storage_used_mb, created_at)
            VALUES ($1, $2, $3, $4, $5, TRUE, TRUE, 5120, 0.0, $6)
            """,
            str(uuid.uuid4()),
            "owner_pg",
            "owner_pg@example.com",
            "x",
            "user",
            now,
        )
        await conn.execute(
            """
            INSERT INTO users (uuid, username, email, password_hash, role,
                               is_active, is_verified, storage_quota_mb, storage_used_mb, created_at)
            VALUES ($1, $2, $3, $4, $5, TRUE, TRUE, 5120, 0.0, $6)
            """,
            str(uuid.uuid4()),
            "member_pg",
            "member_pg@example.com",
            "x",
            "user",
            now,
        )

    owner_id = await pool.fetchval(
        "SELECT id FROM users WHERE username = $1", "owner_pg"
    )
    member_id = await pool.fetchval(
        "SELECT id FROM users WHERE username = $1", "member_pg"
    )

    repo = AuthnzOrgsTeamsRepo(pool)

    # Create organization and add members (owner + member)
    org = await repo.create_organization(name="PG Acme Corp", owner_user_id=owner_id)
    org_id = org["id"]

    owner_membership = await repo.add_org_member(
        org_id=org_id, user_id=owner_id, role="owner"
    )
    member_membership = await repo.add_org_member(
        org_id=org_id, user_id=member_id, role="member"
    )

    assert owner_membership["org_id"] == org_id
    assert owner_membership["user_id"] == owner_id
    assert owner_membership["role"].lower() == "owner"

    assert member_membership["org_id"] == org_id
    assert member_membership["user_id"] == member_id
    assert member_membership["role"].lower() == "member"

    # List org members and memberships for user
    members = await repo.list_org_members(org_id=org_id)
    roles_by_user = {m["user_id"]: m["role"] for m in members}
    assert roles_by_user[owner_id].lower() == "owner"
    assert roles_by_user[member_id].lower() == "member"

    owner_memberships = await repo.list_org_memberships_for_user(owner_id)
    assert any(
        m["org_id"] == org_id and m["role"].lower() == "owner"
        for m in owner_memberships
    )

    # Default team should be created and both users enrolled
    default_team_id = await pool.fetchval(
        "SELECT id FROM teams WHERE org_id = $1 AND name = $2",
        org_id,
        DEFAULT_BASE_TEAM_NAME,
    )
    assert default_team_id is not None

    owner_team_count = await pool.fetchval(
        "SELECT COUNT(*) FROM team_members WHERE team_id = $1 AND user_id = $2",
        default_team_id,
        owner_id,
    )
    member_team_count = await pool.fetchval(
        "SELECT COUNT(*) FROM team_members WHERE team_id = $1 AND user_id = $2",
        default_team_id,
        member_id,
    )
    assert owner_team_count == 1
    assert member_team_count == 1

    # Update non-owner role
    updated_member = await repo.update_org_member_role(
        org_id=org_id,
        user_id=member_id,
        role="admin",
    )
    assert updated_member is not None
    assert updated_member["role"].lower() == "admin"

    # Cannot demote the last owner
    demote_owner = await repo.update_org_member_role(
        org_id=org_id,
        user_id=owner_id,
        role="member",
    )
    assert demote_owner is not None
    assert demote_owner["role"].lower() == "owner"
    assert demote_owner.get("error") == "owner_required"

    # Removing a non-owner should also remove them from the default team
    remove_member = await repo.remove_org_member(org_id=org_id, user_id=member_id)
    assert remove_member["removed"] is True

    remaining_members = await repo.list_org_members(org_id=org_id)
    assert all(m["user_id"] != member_id for m in remaining_members)

    member_team_count_after = await pool.fetchval(
        "SELECT COUNT(*) FROM team_members WHERE team_id = $1 AND user_id = $2",
        default_team_id,
        member_id,
    )
    owner_team_count_after = await pool.fetchval(
        "SELECT COUNT(*) FROM team_members WHERE team_id = $1 AND user_id = $2",
        default_team_id,
        owner_id,
    )
    assert member_team_count_after == 0
    assert owner_team_count_after == 1

    # Removing the last owner should be blocked with owner_required
    remove_owner = await repo.remove_org_member(org_id=org_id, user_id=owner_id)
    assert remove_owner["removed"] is False
    assert remove_owner.get("error") == "owner_required"
