import os
import pytest

from tldw_Server_API.app.services.admin_usage_service import (
    fetch_usage_daily,
    export_usage_top_csv_text,
)


def _setup_env():
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-api-key"
    os.environ["USAGE_LOG_ENABLED"] = "true"


async def _seed_sqlite_usage_rows():
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    pool = await get_db_pool()
    # Ensure tables exist
    await pool.execute(
        "CREATE TABLE IF NOT EXISTS usage_daily (user_id INTEGER NOT NULL, day DATE NOT NULL, requests INTEGER DEFAULT 0, errors INTEGER DEFAULT 0, bytes_total INTEGER DEFAULT 0, latency_avg_ms REAL, PRIMARY KEY (user_id, day))"
    )
    # Backfill bytes_in_total column if missing
    cols = {row["name"] for row in await pool.fetchall("PRAGMA table_info(usage_daily)")}
    if "bytes_in_total" not in cols:
        await pool.execute("ALTER TABLE usage_daily ADD COLUMN bytes_in_total INTEGER DEFAULT 0")
    # Insert a small sample day
    await pool.execute(
        "INSERT OR REPLACE INTO usage_daily (user_id, day, requests, errors, bytes_total, bytes_in_total, latency_avg_ms) VALUES (?,?,?,?,?,?,?)",
        1,
        "2024-01-02",
        3,
        1,
        1234,
        222,
        45.5,
    )


@pytest.mark.asyncio
async def test_fetch_usage_daily_sqlite_roundtrip():
    _setup_env()
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    await reset_db_pool()
    await _seed_sqlite_usage_rows()
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    pool = await get_db_pool()
    rows, total, has_in = await fetch_usage_daily(
        pool, user_id=None, start="2024-01-01", end="2024-01-03", page=1, limit=10
    )
    assert total >= 1
    assert any(int(r["user_id"]) == 1 for r in rows)
    # Ensure presence of bytes_in_total key
    assert all("bytes_in_total" in r for r in rows)
    assert isinstance(has_in, bool)


@pytest.mark.asyncio
async def test_export_usage_top_csv_text_smoke():
    _setup_env()
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    await reset_db_pool()
    await _seed_sqlite_usage_rows()
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    pool = await get_db_pool()
    csv_text = await export_usage_top_csv_text(pool, start="2024-01-01", end="2024-01-03", limit=5, metric="requests")
    assert csv_text.startswith("user_id,requests,errors,bytes_total,bytes_in_total,latency_avg_ms")
    assert "\n" in csv_text
