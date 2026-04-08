"""Unit tests for the unified Sharing audit boundary."""
from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Sharing.unified_share_audit import UnifiedShareAuditWriter

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_share_audit_writer_keeps_owner_and_actor_distinct(tmp_path):
    writer = UnifiedShareAuditWriter(db_path=str(tmp_path / "audit_shared.db"))
    await writer.initialize()
    try:
        await writer.log_event(
            event_type="share.created",
            resource_type="workspace",
            resource_id="ws-1",
            owner_user_id=7,
            actor_user_id=11,
            share_id=42,
            metadata={"scope_type": "team"},
        )
        rows = await writer.query_events(owner_user_id=7)
    finally:
        await writer.stop()

    assert len(rows) == 1
    assert rows[0]["id"] == 1
    assert rows[0]["event_type"] == "share.created"
    assert rows[0]["owner_user_id"] == 7
    assert rows[0]["actor_user_id"] == 11
    assert rows[0]["share_id"] == 42
    assert rows[0]["metadata"] == {"scope_type": "team"}
