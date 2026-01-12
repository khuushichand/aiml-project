import aiosqlite
import pytest

from tldw_Server_API.app.core.Audit.audit_shared_migration import migrate_to_shared_audit_db
from tldw_Server_API.app.core.Audit.unified_audit_service import (
    UnifiedAuditService,
    AuditContext,
    AuditEventType,
)


@pytest.mark.asyncio
async def test_migrate_to_shared_db(tmp_path):
    user_base = tmp_path / "user_dbs"
    user_id = "101"
    user_db_path = user_base / user_id / "audit" / "unified_audit.db"
    shared_db_path = tmp_path / "Databases" / "audit_shared.db"
    default_db_path = tmp_path / "Databases" / "unified_audit.db"
    user_db_path.parent.mkdir(parents=True, exist_ok=True)
    default_db_path.parent.mkdir(parents=True, exist_ok=True)

    svc_user = UnifiedAuditService(
        db_path=str(user_db_path),
        storage_mode="per_user",
        enable_pii_detection=False,
        enable_risk_scoring=False,
        buffer_size=1,
        flush_interval=0.1,
    )
    await svc_user.initialize(start_background_tasks=False)
    await svc_user.log_event(
        event_type=AuditEventType.DATA_READ,
        context=AuditContext(user_id=user_id),
        resource_type="doc",
        resource_id="u1",
    )
    await svc_user.flush()
    await svc_user.stop()

    svc_default = UnifiedAuditService(
        db_path=str(default_db_path),
        storage_mode="per_user",
        enable_pii_detection=False,
        enable_risk_scoring=False,
        buffer_size=1,
        flush_interval=0.1,
    )
    await svc_default.initialize(start_background_tasks=False)
    await svc_default.log_event(event_type=AuditEventType.SYSTEM_START)
    await svc_default.flush()
    await svc_default.stop()

    report = await migrate_to_shared_audit_db(
        shared_db_path=shared_db_path,
        user_db_base_dir=user_base,
        default_db_path=default_db_path,
        system_tenant_id="system",
        chunk_size=100,
    )
    assert report.total_events_inserted >= 2

    async with aiosqlite.connect(shared_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT tenant_user_id FROM audit_events") as cur:
            rows = await cur.fetchall()
        tenants = {row["tenant_user_id"] for row in rows}
        assert user_id in tenants
        assert "system" in tenants

        async with db.execute("SELECT tenant_user_id FROM audit_daily_stats") as cur:
            stats_rows = await cur.fetchall()
        stats_tenants = {row["tenant_user_id"] for row in stats_rows}
        assert user_id in stats_tenants
        assert "system" in stats_tenants

    report2 = await migrate_to_shared_audit_db(
        shared_db_path=shared_db_path,
        user_db_base_dir=user_base,
        default_db_path=default_db_path,
        system_tenant_id="system",
        chunk_size=100,
    )
    assert report2.total_events_inserted == 0
