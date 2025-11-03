import pytest
from datetime import datetime, timezone, timedelta

from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import (
    ResourceDailyLedger,
    LedgerEntry,
)


@pytest.mark.asyncio
async def test_resource_daily_ledger_postgres_peek_range(test_db_pool):
    ledger = ResourceDailyLedger(db_pool=test_db_pool)
    await ledger.initialize()

    now = datetime.now(timezone.utc)
    yday = now - timedelta(days=1)

    # Insert entries across two days
    e1 = LedgerEntry(
        entity_scope="user",
        entity_value="u_pg",
        category="minutes",
        units=7,
        op_id="pg-op-1",
        occurred_at=now,
    )
    e2 = LedgerEntry(
        entity_scope="user",
        entity_value="u_pg",
        category="minutes",
        units=5,
        op_id="pg-op-2",
        occurred_at=yday,
    )

    await ledger.add(e1)
    await ledger.add(e2)

    start_day = yday.strftime("%Y-%m-%d")
    end_day = now.strftime("%Y-%m-%d")
    peek = await ledger.peek_range("user", "u_pg", "minutes", start_day, end_day)

    assert isinstance(peek, dict)
    assert peek.get("total") == 12
    days = {d["day_utc"]: d["units"] for d in peek.get("days", [])}
    assert days.get(start_day) == 5
    assert days.get(end_day) == 7

