from __future__ import annotations

import sqlite3

import pytest

from tldw_Server_API.app.core.AuthNZ import migrations
from tldw_Server_API.app.core.AuthNZ import pg_migrations_extra as pg_migrations


pytestmark = pytest.mark.unit


def test_sqlite_migration_030_seeds_only_neutral_free_plan() -> None:
    """Fresh OSS SQLite migrations should not seed a public paid catalog."""

    conn = sqlite3.connect(":memory:")
    try:
        migrations.migration_030_create_subscription_plans(conn)

        rows = conn.execute(
            """
            SELECT name, display_name, price_usd_monthly, price_usd_yearly, is_public
            FROM subscription_plans
            ORDER BY sort_order ASC, id ASC
            """
        ).fetchall()

        assert [row[0] for row in rows] == ["free"]
        assert rows[0][1] == "Free"
        assert rows[0][2] == 0
        assert rows[0][3] == 0
        assert rows[0][4] == 0
    finally:
        conn.close()


class _FakeBillingPool:
    def __init__(self) -> None:
        self.pool = object()
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, sql: str, *params: object) -> None:
        self.executed.append((sql, params))


@pytest.mark.asyncio
async def test_postgres_billing_ensure_seeds_only_neutral_free_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Postgres billing bootstrap should only seed the neutral free plan."""

    async def _noop_ensure_authnz_core_tables_pg(_pool) -> None:
        return None

    monkeypatch.setattr(pg_migrations, "ensure_authnz_core_tables_pg", _noop_ensure_authnz_core_tables_pg)

    pool = _FakeBillingPool()
    ok = await pg_migrations.ensure_billing_tables_pg(pool, run_backfill=False)

    assert ok is True
    inserts = [
        params
        for sql, params in pool.executed
        if sql.strip().lower().startswith("insert into subscription_plans")
    ]
    assert len(inserts) == 1
    assert inserts[0][0] == "free"
    assert inserts[0][3] == 0
    assert inserts[0][4] == 0
