import os
from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import (
    ResourceDailyLedger,
)
from tldw_Server_API.app.core.Resource_Governance.cost_units import (
    compute_cost_units,
    record_cost_units_for_entity,
    remaining_daily_cost_units,
)


@pytest.mark.asyncio
async def test_compute_cost_units_uses_env_weights(monkeypatch):
    # Configure small, deterministic weights so test math is simple.
    monkeypatch.setenv("RG_COST_UNITS_TOKENS_PER_UNIT", "100")
    monkeypatch.setenv("RG_COST_UNITS_MINUTES_PER_UNIT", "1")
    monkeypatch.setenv("RG_COST_UNITS_REQUESTS_PER_UNIT", "10")

    units = compute_cost_units(tokens=250, minutes=2.5, requests=3)
    # tokens: ceil(250/100)=3, minutes: ceil(2.5/1)=3, requests: ceil(3/10)=1 → total=7
    assert units == 7


@pytest.mark.asyncio
async def test_record_and_remaining_cost_units_round_trip(tmp_path, monkeypatch):
    # Point AuthNZ DB to a temporary SQLite file
    db_path = tmp_path / "users_cost_units.db"
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    # Deterministic weights: 100 tokens per unit, 1 minute per unit, 10 requests per unit
    monkeypatch.setenv("RG_COST_UNITS_TOKENS_PER_UNIT", "100")
    monkeypatch.setenv("RG_COST_UNITS_MINUTES_PER_UNIT", "1")
    monkeypatch.setenv("RG_COST_UNITS_REQUESTS_PER_UNIT", "10")

    await reset_db_pool()
    pool = await get_db_pool()
    try:
        # Seed ledger via the helper
        scope = "user"
        value = "7"
        now = datetime.now(timezone.utc)
        op_id = "test-cost-units-op"

        units = await record_cost_units_for_entity(
            entity_scope=scope,
            entity_value=value,
            tokens=250,
            minutes=2.0,
            requests=3,
            op_id=op_id,
            occurred_at=now,
        )
        assert units > 0

        ledger = ResourceDailyLedger(db_pool=pool)
        await ledger.initialize()
        today = now.astimezone(timezone.utc).date().strftime("%Y-%m-%d")
        total_units = await ledger.total_for_day(scope, value, "cost_units", day_utc=today)

        # Compute expected units with the same weights
        expected_units = compute_cost_units(tokens=250, minutes=2.0, requests=3)
        assert total_units == expected_units

        # Remaining helper should reflect the cap minus today's usage.
        cap = expected_units + 5
        remaining = await remaining_daily_cost_units(
            entity_scope=scope,
            entity_value=value,
            daily_cap_units=cap,
            day_utc=today,
        )
        assert remaining == 5
    finally:
        await pool.close()
        # Clean up env for subsequent tests
        for key in (
            "AUTH_MODE",
            "DATABASE_URL",
            "RG_COST_UNITS_TOKENS_PER_UNIT",
            "RG_COST_UNITS_MINUTES_PER_UNIT",
            "RG_COST_UNITS_REQUESTS_PER_UNIT",
        ):
            os.environ.pop(key, None)

