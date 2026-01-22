import asyncio
from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    AuditContext,
    AuditEvent,
    AuditEventCategory,
    AuditEventType,
    UnifiedAuditService,
    audit_operation,
)


@pytest.mark.asyncio
async def test_started_result_not_counted_as_failure_in_daily_stats(tmp_path):
    db_path = tmp_path / "audit.db"
    service = UnifiedAuditService(
        db_path=str(db_path),
        enable_pii_detection=False,
        enable_risk_scoring=False,
        buffer_size=100,
        flush_interval=60.0,
    )
    await service.initialize()
    try:
        ctx = AuditContext(user_id="result-semantics-user")
        async with audit_operation(
            service,
            AuditEventType.DATA_READ,
            ctx,
            start_event_type=AuditEventType.API_REQUEST,
            completed_event_type=AuditEventType.API_RESPONSE,
            resource_type="document",
            resource_id="doc-1",
        ):
            await asyncio.sleep(0)

        await service.flush()

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT total_events, failed_events FROM audit_daily_stats WHERE category = ?",
                (AuditEventCategory.API_CALL.value,),
            )
            row = await cursor.fetchone()

        assert row is not None
        assert row["total_events"] == 2
        assert row["failed_events"] == 0
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_security_summary_does_not_count_started_as_failure(tmp_path):
    db_path = tmp_path / "audit.db"
    service = UnifiedAuditService(
        db_path=str(db_path),
        enable_pii_detection=False,
        enable_risk_scoring=False,
        buffer_size=10,
        flush_interval=60.0,
    )
    await service.initialize()
    try:
        await service.log_event(
            event_type=AuditEventType.SECURITY_SCAN,
            context=AuditContext(user_id="security-summary-user"),
            result="started",
        )
        await service.flush()

        summary = await service.get_security_summary(hours=24)
        assert summary["total_events"] == 1
        assert summary["failure_events"] == 0
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_daily_stats_bucket_uses_utc_date(tmp_path):
    db_path = tmp_path / "audit.db"
    service = UnifiedAuditService(
        db_path=str(db_path),
        enable_pii_detection=False,
        enable_risk_scoring=False,
        buffer_size=10,
        flush_interval=60.0,
    )
    await service.initialize()
    try:
        # 2025-01-02 00:30:00+05:00 == 2025-01-01 19:30:00Z
        ts = datetime(2025, 1, 2, 0, 30, 0, tzinfo=timezone(timedelta(hours=5)))
        event = AuditEvent(
            event_type=AuditEventType.API_REQUEST,
            category=AuditEventCategory.API_CALL,
            timestamp=ts,
            context=AuditContext(user_id="tz-user"),
        )
        async with service.buffer_lock:
            service.event_buffer.append(event)
        await service.flush()

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT date FROM audit_daily_stats WHERE category = ?",
                (AuditEventCategory.API_CALL.value,),
            )
            row = await cursor.fetchone()
        assert row is not None
        expected_date = datetime(2025, 1, 1, tzinfo=timezone.utc).date()
        date_val = row["date"]
        if isinstance(date_val, str):
            assert date_val == expected_date.isoformat()
        else:
            assert date_val == expected_date
    finally:
        await service.stop()
