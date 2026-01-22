import json
from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    AuditContext,
    AuditEvent,
    AuditEventCategory,
    AuditEventType,
    UnifiedAuditService,
)


@pytest.mark.asyncio
async def test_export_keyset_avoids_duplicates_on_midstream_insert(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    db_path = tmp_path / "audit.db"
    service = UnifiedAuditService(
        db_path=str(db_path),
        enable_pii_detection=False,
        enable_risk_scoring=False,
        buffer_size=10,
        flush_interval=60.0,
    )
    await service.initialize(start_background_tasks=False)
    try:
        base = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        events = [
            AuditEvent(
                event_id="evt-1",
                timestamp=base + timedelta(seconds=4),
                category=AuditEventCategory.API_CALL,
                event_type=AuditEventType.API_REQUEST,
                context=AuditContext(user_id="export-user"),
                resource_id="r1",
            ),
            AuditEvent(
                event_id="evt-2",
                timestamp=base + timedelta(seconds=3),
                category=AuditEventCategory.API_CALL,
                event_type=AuditEventType.API_REQUEST,
                context=AuditContext(user_id="export-user"),
                resource_id="r2",
            ),
            AuditEvent(
                event_id="evt-3",
                timestamp=base + timedelta(seconds=2),
                category=AuditEventCategory.API_CALL,
                event_type=AuditEventType.API_REQUEST,
                context=AuditContext(user_id="export-user"),
                resource_id="r3",
            ),
            AuditEvent(
                event_id="evt-4",
                timestamp=base + timedelta(seconds=1),
                category=AuditEventCategory.API_CALL,
                event_type=AuditEventType.API_REQUEST,
                context=AuditContext(user_id="export-user"),
                resource_id="r4",
            ),
        ]
        async with service.buffer_lock:
            service.event_buffer.extend(events)
        await service.flush()

        gen = await service.export_events(format="jsonl", stream=True, chunk_size=2)
        aiter = gen.__aiter__()
        lines = []
        for _ in range(2):
            lines.append(await aiter.__anext__())

        # Insert a new event that would have sorted between the first and second chunk.
        insert_event = AuditEvent(
            event_id="evt-insert",
            timestamp=base + timedelta(seconds=3, milliseconds=500),
            category=AuditEventCategory.API_CALL,
            event_type=AuditEventType.API_REQUEST,
            context=AuditContext(user_id="export-user"),
            resource_id="inserted",
        )
        async with service.buffer_lock:
            service.event_buffer.append(insert_event)
        await service.flush()

        async for line in aiter:
            lines.append(line)

        rows = [json.loads(line) for line in lines if line and line.strip()]
        resource_ids = [row.get("resource_id") for row in rows]
        assert set(resource_ids) == {"r1", "r2", "r3", "r4"}
        assert len(resource_ids) == 4
    finally:
        await service.stop()
