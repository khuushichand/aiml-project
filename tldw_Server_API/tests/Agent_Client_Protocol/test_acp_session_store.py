from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.ACP_Sessions_DB import ACPSessionsDB
from tldw_Server_API.app.services.admin_acp_sessions_service import ACPSessionStore


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_register_and_record_prompt_preserve_creation_config_and_bootstrap_ready_transcript(tmp_path):
    _db = ACPSessionsDB(db_path=str(tmp_path / "store_test.db"))
    store = ACPSessionStore(db=_db)

    await store.register_session(
        session_id="session-1",
        user_id=7,
        agent_type="codex",
        name="Seed Session",
        cwd="/tmp/project",
        tags=["alpha"],
        mcp_servers=[{"name": "filesystem", "command": "fs-server"}],
        persona_id="persona-1",
        workspace_id="workspace-1",
        workspace_group_id="group-1",
        scope_snapshot_id="scope-1",
    )

    usage = await store.record_prompt(
        "session-1",
        [{"role": "user", "content": "Hello"}],
        {"content": "World", "usage": {"prompt_tokens": 3, "completion_tokens": 5}},
    )

    record = await store.get_session("session-1")
    assert record is not None
    assert usage is not None
    assert record.mcp_servers == [{"name": "filesystem", "command": "fs-server"}]
    assert record.bootstrap_ready is True
    assert record.needs_bootstrap is False
    assert [msg["content"] for msg in record.messages] == ["Hello", "World"]
    assert record.message_count == 2
    assert record.to_info_dict()["persona_id"] == "persona-1"


@pytest.mark.asyncio
async def test_record_prompt_marks_session_non_bootstrappable_when_assistant_text_cannot_be_normalized(tmp_path):
    _db = ACPSessionsDB(db_path=str(tmp_path / "store_test.db"))
    store = ACPSessionStore(db=_db)
    await store.register_session(
        session_id="session-2",
        user_id=7,
        agent_type="codex",
        name="Opaque Session",
        cwd="/tmp/project",
        mcp_servers=[{"name": "filesystem"}],
    )

    await store.record_prompt(
        "session-2",
        [{"role": "user", "content": "Hello"}],
        {"detail": {"structured": True}},
    )

    record = await store.get_session("session-2")
    assert record is not None
    assert record.bootstrap_ready is False
    assert record.messages[-1]["role"] == "assistant"
    assert record.messages[-1]["content"] is None
    assert record.messages[-1]["raw_result"] == {"detail": {"structured": True}}


@pytest.mark.asyncio
async def test_fork_session_copies_lineage_config_and_bootstrap_state(tmp_path):
    _db = ACPSessionsDB(db_path=str(tmp_path / "store_test.db"))
    store = ACPSessionStore(db=_db)
    await store.register_session(
        session_id="session-source",
        user_id=7,
        agent_type="codex",
        name="Seed Session",
        cwd="/tmp/project",
        tags=["alpha"],
        mcp_servers=[{"name": "filesystem"}],
        persona_id="persona-1",
        workspace_id="workspace-1",
        workspace_group_id="group-1",
        scope_snapshot_id="scope-1",
    )
    await store.record_prompt(
        "session-source",
        [{"role": "user", "content": "Hello"}],
        {"content": "World"},
    )

    forked = await store.fork_session(
        source_session_id="session-source",
        new_session_id="session-fork",
        message_index=1,
        user_id=7,
        name="Forked Session",
    )

    assert forked is not None
    assert forked.forked_from == "session-source"
    assert forked.mcp_servers == [{"name": "filesystem"}]
    assert forked.bootstrap_ready is True
    assert forked.needs_bootstrap is True
    assert forked.message_count == 2
