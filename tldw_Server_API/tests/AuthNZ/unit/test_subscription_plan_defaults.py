from __future__ import annotations

import sqlite3

import pytest

from tldw_Server_API.app.core.AuthNZ import migrations
from tldw_Server_API.app.core.AuthNZ import pg_migrations_extra as pg_migrations


pytestmark = pytest.mark.unit


def test_sqlite_migration_030_seeds_only_neutral_free_plan() -> None:
    """Fresh OSS SQLite migrations should retire billing tables entirely."""

    conn = sqlite3.connect(":memory:")
    try:
        migrations.migration_030_create_subscription_plans(conn)

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        assert "subscription_plans" not in tables
        assert "org_subscriptions" not in tables
        assert "stripe_webhook_events" not in tables
        assert "payment_history" not in tables
        assert "billing_audit_log" not in tables
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
    """Postgres OSS bootstrap should only ensure budget storage compatibility."""

    async def _noop_ensure_authnz_core_tables_pg(_pool) -> None:
        return None

    monkeypatch.setattr(pg_migrations, "ensure_authnz_core_tables_pg", _noop_ensure_authnz_core_tables_pg)

    pool = _FakeBillingPool()
    ok = await pg_migrations.ensure_billing_tables_pg(pool, run_backfill=False)

    assert ok is True
    ddl = " ".join(sql.strip().lower() for sql, _params in pool.executed)
    assert "create table if not exists org_budgets" in ddl
    assert "create table if not exists subscription_plans" not in ddl
    assert "create table if not exists org_subscriptions" not in ddl
    assert "create table if not exists stripe_webhook_events" not in ddl
    assert "create table if not exists payment_history" not in ddl
    assert "create table if not exists billing_audit_log" not in ddl


def test_retired_billing_migrations_use_non_destructive_rollback() -> None:
    billing_rollbacks = {
        migration.version: migration.down
        for migration in migrations.get_authnz_migrations()
        if migration.version in {30, 31, 32, 33, 34}
    }

    assert billing_rollbacks
    assert all(
        rollback is migrations.rollback_retired_billing_schema_noop
        for rollback in billing_rollbacks.values()
    )
