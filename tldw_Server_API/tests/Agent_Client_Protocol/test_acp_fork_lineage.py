"""Tests for ACP fork lineage tracking (Phase 7.2)."""
from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.ACP_Sessions_DB import ACPSessionsDB
from tldw_Server_API.app.services.admin_acp_sessions_service import (
    ACPSessionStore,
    SessionRecord,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def store(tmp_path):
    _db = ACPSessionsDB(db_path=str(tmp_path / "lineage_test.db"))
    return ACPSessionStore(db=_db)


async def _create_session(store, session_id, forked_from=None):
    """Helper to create a session record via the DB."""
    rec = await store.register_session(
        session_id=session_id,
        user_id=1,
        agent_type="claude_code",
        name=f"Session {session_id}",
        forked_from=forked_from,
    )
    if forked_from is not None:
        # Set forked_from directly in the DB
        conn = store._db._get_conn()
        conn.execute(
            "UPDATE sessions SET forked_from = ? WHERE session_id = ?",
            (forked_from, session_id),
        )
        conn.commit()
    return rec


# ---- Basic lineage ----


async def test_no_fork_empty_lineage(store):
    """Session with no fork parent has empty lineage."""
    await _create_session(store, "s1")
    lineage = await store.get_fork_lineage("s1")
    assert lineage == []


async def test_single_fork_lineage(store):
    """Session forked from one parent returns single-element lineage."""
    await _create_session(store, "parent")
    await _create_session(store, "child", forked_from="parent")
    lineage = await store.get_fork_lineage("child")
    assert lineage == ["parent"]


async def test_chain_of_three(store):
    """Three-level fork chain: grandparent -> parent -> child."""
    await _create_session(store, "gp")
    await _create_session(store, "p", forked_from="gp")
    await _create_session(store, "c", forked_from="p")

    lineage = await store.get_fork_lineage("c")
    assert lineage == ["gp", "p"]  # Oldest first


async def test_chain_of_five(store):
    """Five-level fork chain."""
    await _create_session(store, "s1")
    await _create_session(store, "s2", forked_from="s1")
    await _create_session(store, "s3", forked_from="s2")
    await _create_session(store, "s4", forked_from="s3")
    await _create_session(store, "s5", forked_from="s4")

    lineage = await store.get_fork_lineage("s5")
    assert lineage == ["s1", "s2", "s3", "s4"]


# ---- Edge cases ----


async def test_missing_parent_stops_chain(store):
    """If a parent session is missing from store, lineage includes the reference but stops."""
    await _create_session(store, "child", forked_from="missing_parent")
    lineage = await store.get_fork_lineage("child")
    assert lineage == ["missing_parent"]  # Reference preserved even if parent gone


async def test_nonexistent_session(store):
    """Getting lineage for nonexistent session returns empty."""
    lineage = await store.get_fork_lineage("nonexistent")
    assert lineage == []


async def test_cycle_guard(store):
    """Cycle in fork chain is handled gracefully."""
    await _create_session(store, "a", forked_from="b")
    await _create_session(store, "b", forked_from="a")
    lineage = await store.get_fork_lineage("a")
    # Should not infinite loop -- stops at cycle
    assert len(lineage) <= 2


async def test_max_depth_limit(store):
    """Lineage respects max_depth parameter."""
    await _create_session(store, "s0")
    for i in range(1, 10):
        await _create_session(store, f"s{i}", forked_from=f"s{i-1}")

    lineage = await store.get_fork_lineage("s9", max_depth=3)
    assert len(lineage) == 3


# ---- Integration with to_detail_dict ----


async def test_detail_dict_includes_lineage(store):
    """to_detail_dict includes fork_lineage when provided."""
    await _create_session(store, "s1")
    rec = await store.get_session("s1")
    d = rec.to_detail_dict(fork_lineage=["ancestor1", "ancestor2"])
    assert d["fork_lineage"] == ["ancestor1", "ancestor2"]


async def test_detail_dict_default_empty_lineage(store):
    """to_detail_dict defaults to empty lineage."""
    await _create_session(store, "s1")
    rec = await store.get_session("s1")
    d = rec.to_detail_dict()
    assert d["fork_lineage"] == []
