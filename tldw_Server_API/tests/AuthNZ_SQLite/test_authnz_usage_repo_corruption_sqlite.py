from __future__ import annotations

from datetime import date

import pytest
from loguru import logger


class _CorruptingSQLitePool:
    pool = None
    _sqlite_fs_path = "/tmp/authnz-corrupt-users.db"  # nosec B108

    async def execute(self, *args, **kwargs):  # noqa: ANN002, ANN003, D401
        raise RuntimeError("database disk image is malformed")


@pytest.mark.asyncio
async def test_aggregate_llm_usage_daily_skips_on_sqlite_corruption():
    from tldw_Server_API.app.core.AuthNZ.repos import usage_repo as usage_repo_module

    usage_repo_module._SQLITE_CORRUPTION_WARNING_KEYS.clear()
    repo = usage_repo_module.AuthnzUsageRepo(db_pool=_CorruptingSQLitePool())  # type: ignore[arg-type]

    messages: list[str] = []

    sink_id = logger.add(lambda msg: messages.append(str(msg.record.get("message") or "")), level="DEBUG")
    try:
        await repo.aggregate_llm_usage_daily_for_day(day=date(2026, 2, 8))
        await repo.aggregate_llm_usage_daily_for_day(day=date(2026, 2, 8))
    finally:
        logger.remove(sink_id)

    warning_hits = [m for m in messages if "detected sqlite corruption at" in m]
    debug_hits = [m for m in messages if "previously detected sqlite corruption" in m]
    error_hits = [m for m in messages if "aggregate_llm_usage_daily_for_day failed" in m]

    assert len(warning_hits) == 1
    assert len(debug_hits) >= 1
    assert not error_hits


@pytest.mark.asyncio
async def test_aggregate_usage_daily_skips_on_sqlite_corruption():
    from tldw_Server_API.app.core.AuthNZ.repos import usage_repo as usage_repo_module

    usage_repo_module._SQLITE_CORRUPTION_WARNING_KEYS.clear()
    repo = usage_repo_module.AuthnzUsageRepo(db_pool=_CorruptingSQLitePool())  # type: ignore[arg-type]

    messages: list[str] = []
    sink_id = logger.add(lambda msg: messages.append(str(msg.record.get("message") or "")), level="WARNING")
    try:
        await repo.aggregate_usage_daily_for_day(day=date(2026, 2, 8))
    finally:
        logger.remove(sink_id)

    assert any("aggregate_usage_daily_for_day detected sqlite corruption" in m for m in messages)
