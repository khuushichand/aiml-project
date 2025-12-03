import os
from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_add_daily_minutes_mirrors_to_resource_daily_ledger(tmp_path, monkeypatch):
    """
    Ensure add_daily_minutes continues to write to audio_usage_daily and also
    mirrors usage into the generic ResourceDailyLedger in shadow mode.
    """
    # Point AuthNZ DB to a temporary SQLite file
    db_path = tmp_path / "users_audio_ledger.db"
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.Usage import audio_quota
    from tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger import ResourceDailyLedger

    await reset_db_pool()
    pool = await get_db_pool()

    # Seed minimal audio tables
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_usage_daily (
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            minutes_used REAL NOT NULL DEFAULT 0,
            jobs_started INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, day)
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_user_tiers (
            user_id INTEGER PRIMARY KEY,
            tier TEXT NOT NULL
        )
        """
    )

    user_id = 42
    # Default tier is "free" with a nonzero daily_minutes cap; ledger is shadow-only.
    await audio_quota.add_daily_minutes(user_id, 2.5)

    # Verify audio_usage_daily was updated
    rows = await pool.fetch(
        "SELECT minutes_used FROM audio_usage_daily WHERE user_id=?",
        user_id,
    )
    assert rows, "audio_usage_daily should have a row for the user"
    minutes_used = float(rows[0][0])
    assert minutes_used == pytest.approx(2.5)

    # ResourceDailyLedger lives in the same AuthNZ DB; query totals via DAL
    ledger = ResourceDailyLedger(db_pool=pool)
    await ledger.initialize()
    today = datetime.now(timezone.utc).date().strftime("%Y-%m-%d")
    # Units are stored as whole seconds; 2.5 minutes ≈ 150 seconds
    total_units = await ledger.total_for_day("user", str(user_id), "minutes", day_utc=today)
    assert total_units >= 145  # allow small rounding differences


@pytest.mark.asyncio
async def test_can_start_stream_and_finish_stream_via_rg_integration(monkeypatch):
    """
    Verify that can_start_stream/finish_stream use the ResourceGovernor path
    when it is available, by patching the internal governor accessor with a
    lightweight fake that enforces a simple max_concurrent=2 policy.
    """
    from tldw_Server_API.app.core.Usage import audio_quota

    class _FakeGov:
        def __init__(self):
            self.stream_counts = {}

        async def reserve(self, req, op_id=None):  # noqa: ARG002
            entity = req.entity
            cats = getattr(req, "categories", {}) or {}
            if "streams" not in cats:
                return type("Dec", (), {"allowed": True, "retry_after": 0})(), "h-ignore"
            count = self.stream_counts.get(entity, 0) + 1
            self.stream_counts[entity] = count
            allowed = count <= 2
            dec = type("Dec", (), {"allowed": allowed, "retry_after": 0})()
            handle_id = f"h-{entity}-{count}" if allowed else None
            return dec, handle_id

        async def release(self, handle_id):  # noqa: ARG002
            # No-op for this test; audio_quota maintains its own handle registry.
            return None

        async def renew(self, handle_id, ttl_s):  # noqa: ARG002
            return None

    gov = _FakeGov()

    async def _fake_get_audio_rg():
        return gov

    # Force RG integration path regardless of env flags
    monkeypatch.setattr(audio_quota, "_get_audio_rg_governor", _fake_get_audio_rg)

    user_id = 123

    ok1, msg1 = await audio_quota.can_start_stream(user_id)
    assert ok1 is True
    assert msg1 in (None, "OK")

    ok2, msg2 = await audio_quota.can_start_stream(user_id)
    assert ok2 is True
    assert msg2 in (None, "OK")

    # Third concurrent stream should be denied by the fake RG policy.
    ok3, _ = await audio_quota.can_start_stream(user_id)
    assert ok3 is False

    # active_streams_count should reflect two active handles tracked by audio_quota.
    active = await audio_quota.active_streams_count(user_id)
    assert active == 2

    # Releasing one stream should reduce the active count.
    await audio_quota.finish_stream(user_id)
    active_after = await audio_quota.active_streams_count(user_id)
    assert active_after == 1


@pytest.mark.asyncio
async def test_can_start_job_fallback_when_redis_unavailable(monkeypatch):
    """
    Verify that job concurrency enforcement still succeeds when the RG path
    is unavailable and Redis is disabled, by falling back to the in-process
    counters in audio_quota.
    """
    from tldw_Server_API.app.core.Usage import audio_quota

    # Force RG path to be unavailable
    async def _rg_unavailable():
        return None

    monkeypatch.setattr(audio_quota, "_get_audio_rg_governor", _rg_unavailable)

    # Disable Redis for this test so the legacy path uses in-process counters
    async def _no_redis():
        return None

    monkeypatch.setattr(audio_quota, "_get_redis", _no_redis)

    # Ensure a deterministic per-user concurrent_jobs limit of 1
    async def _limits(_user_id: int):
        return {
            "daily_minutes": 30.0,
            "concurrent_streams": 1,
            "concurrent_jobs": 1,
            "max_file_size_mb": 25,
        }

    monkeypatch.setattr(audio_quota, "get_limits_for_user", _limits)

    # Reset in-process job counters
    audio_quota._active_jobs.clear()  # type: ignore[attr-defined]

    user_id = 99
    ok1, msg1 = await audio_quota.can_start_job(user_id)
    assert ok1 is True
    assert msg1 in (None, "OK")

    # Second job for same user should be denied by the concurrent_jobs cap
    ok2, _ = await audio_quota.can_start_job(user_id)
    assert ok2 is False

    await audio_quota.finish_job(user_id)
