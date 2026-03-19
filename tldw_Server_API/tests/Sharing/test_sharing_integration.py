"""Integration tests for the sharing lifecycle: share -> list -> proxy -> clone -> revoke."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_share_then_list_shared_with_me(repo):
    """Owner shares a workspace; accessor sees it in shared-with-me list."""
    share = await repo.create_share(
        workspace_id="ws-int-1",
        owner_user_id=1,
        share_scope_type="team",
        share_scope_id=100,
        access_level="view_chat",
        allow_clone=True,
        created_by=1,
    )
    assert share["id"] > 0

    # Accessor is in team 100
    shares = await repo.list_shares_for_scope("team", 100)
    assert len(shares) == 1
    assert shares[0]["workspace_id"] == "ws-int-1"
    assert shares[0]["allow_clone"] is True


@pytest.mark.asyncio
async def test_revoke_then_share_not_visible(repo):
    """After revocation, the share should not appear in active lists."""
    share = await repo.create_share(
        workspace_id="ws-int-2",
        owner_user_id=1,
        share_scope_type="team",
        share_scope_id=200,
        created_by=1,
    )
    result = await repo.revoke_share(share["id"])
    assert result is True

    active = await repo.list_shares_for_scope("team", 200)
    assert len(active) == 0

    # Revoked share still exists when including revoked
    all_shares = await repo.list_shares_for_workspace("ws-int-2", 1, include_revoked=True)
    assert len(all_shares) == 1
    assert all_shares[0]["is_revoked"] is True


@pytest.mark.asyncio
async def test_token_with_password_hash_is_protected(repo):
    """Tokens with password_hash should report is_password_protected=True."""
    token = await repo.create_token(
        token_hash="pw-hash-1",
        token_prefix="pw-pfx",
        resource_type="workspace",
        resource_id="ws-int-3",
        owner_user_id=1,
        password_hash="bcrypt$hash$here",
    )
    assert token["is_password_protected"] is True


@pytest.mark.asyncio
async def test_token_use_count_increments(repo):
    """Use count should increment on each call."""
    token = await repo.create_token(
        token_hash="uc-hash",
        token_prefix="uc-pfx",
        resource_type="workspace",
        resource_id="ws-int-4",
        owner_user_id=1,
    )
    for _ in range(3):
        await repo.increment_token_use_count(token["id"])

    fetched = await repo.get_token(token["id"])
    assert fetched["use_count"] == 3


@pytest.mark.asyncio
async def test_revoke_token_then_not_found_by_prefix(repo):
    """Revoked tokens should not appear in find_tokens_by_prefix."""
    token = await repo.create_token(
        token_hash="rev-hash",
        token_prefix="rev-pfx",
        resource_type="workspace",
        resource_id="ws-int-5",
        owner_user_id=1,
    )
    result = await repo.revoke_token(token["id"])
    assert result is True

    found = await repo.find_tokens_by_prefix("rev-pfx")
    assert len(found) == 0


@pytest.mark.asyncio
async def test_audit_log_captures_events(repo):
    """Audit log should record events with metadata."""
    share = await repo.create_share(
        workspace_id="ws-int-6",
        owner_user_id=1,
        share_scope_type="org",
        share_scope_id=300,
        created_by=1,
    )

    await repo.log_audit_event(
        event_type="share.created",
        resource_type="workspace",
        resource_id="ws-int-6",
        owner_user_id=1,
        actor_user_id=1,
        share_id=share["id"],
        metadata={"scope_type": "org", "scope_id": 300},
    )

    await repo.log_audit_event(
        event_type="share.cloned",
        resource_type="workspace",
        resource_id="ws-int-6",
        owner_user_id=1,
        actor_user_id=2,
        share_id=share["id"],
        metadata={"cloner": 2},
    )

    events = await repo.list_audit_events(resource_id="ws-int-6")
    assert len(events) == 2
    event_types = {e["event_type"] for e in events}
    assert "share.created" in event_types
    assert "share.cloned" in event_types


@pytest.mark.asyncio
async def test_revoke_all_shares_for_workspace(repo):
    """Revoking all shares for a workspace should return the count of revoked."""
    await repo.create_share(
        workspace_id="ws-int-7", owner_user_id=1,
        share_scope_type="team", share_scope_id=10, created_by=1,
    )
    await repo.create_share(
        workspace_id="ws-int-7", owner_user_id=1,
        share_scope_type="org", share_scope_id=20, created_by=1,
    )
    count = await repo.revoke_shares_for_workspace("ws-int-7", 1)
    assert count == 2

    active = await repo.list_shares_for_workspace("ws-int-7", 1)
    assert len(active) == 0


@pytest.mark.asyncio
async def test_config_scoped_isolation(repo):
    """Global config and org-scoped config should be independent."""
    await repo.set_config("max_shares", "100")
    await repo.set_config("max_shares", "5", scope_type="org", scope_id=1)

    global_cfg = await repo.get_config()
    org_cfg = await repo.get_config(scope_type="org", scope_id=1)

    assert global_cfg["max_shares"] == "100"
    assert org_cfg["max_shares"] == "5"
