from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Audit.unified_audit_service import UnifiedAuditService


async def _async_sqlite_pragma_map(conn) -> dict[str, int | str]:
    async def _value(pragma: str):
        row = await (await conn.execute(f"PRAGMA {pragma}")).fetchone()
        return row[0]

    return {
        "journal_mode": str(await _value("journal_mode")).lower(),
        "synchronous": int(await _value("synchronous")),
        "foreign_keys": int(await _value("foreign_keys")),
        "busy_timeout": int(await _value("busy_timeout")),
        "temp_store": int(await _value("temp_store")),
    }


@pytest.mark.asyncio
async def test_audit_pooled_connection_uses_standard_sqlite_pragmas(tmp_path):
    service = UnifiedAuditService(
        db_path=str(tmp_path / "audit.db"),
        enable_pii_detection=False,
        enable_risk_scoring=False,
        buffer_size=2,
        flush_interval=60.0,
    )
    await service.initialize()
    try:
        conn = await service._ensure_db_pool()
        pragmas = await _async_sqlite_pragma_map(conn)
    finally:
        await service.stop()

    assert pragmas == {
        "journal_mode": "wal",
        "synchronous": 1,
        "foreign_keys": 1,
        "busy_timeout": 5000,
        "temp_store": 2,
    }


@pytest.mark.asyncio
async def test_audit_read_connection_uses_standard_sqlite_pragmas_and_query_only(tmp_path):
    service = UnifiedAuditService(
        db_path=str(tmp_path / "audit.db"),
        enable_pii_detection=False,
        enable_risk_scoring=False,
        buffer_size=2,
        flush_interval=60.0,
    )
    await service.initialize()
    try:
        async with service._read_db() as conn:
            pragmas = await _async_sqlite_pragma_map(conn)
            row = await (await conn.execute("PRAGMA query_only")).fetchone()
            query_only = int(row[0])
    finally:
        await service.stop()

    assert pragmas == {
        "journal_mode": "wal",
        "synchronous": 1,
        "foreign_keys": 1,
        "busy_timeout": 5000,
        "temp_store": 2,
    }
    assert query_only == 1
