from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.services.companion_reflection_scheduler import (
    _CompanionReflectionScheduler,
)


pytestmark = pytest.mark.unit


@pytest.fixture()
def companion_scheduler_env(monkeypatch, tmp_path) -> Iterator[Path]:
    base_dir = tmp_path / "test_companion_reflection_scheduler"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    try:
        yield Path(base_dir)
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def _seed_profile(user_id: str, **fields: int) -> None:
    db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))
    db.update_profile(user_id, enabled=1, proactive_enabled=1, **fields)


@pytest.mark.asyncio
async def test_scheduler_skips_users_with_companion_reflections_disabled(
    companion_scheduler_env,
) -> None:
    _seed_profile("1", companion_reflections_enabled=0)
    _seed_profile("2")
    queued: list[dict[str, object]] = []
    scheduler = _CompanionReflectionScheduler()
    scheduler._jobs.create_job = lambda **kwargs: queued.append(kwargs) or {"id": 1}

    await scheduler._enqueue_all_users("daily")

    assert len(queued) == 1
    assert queued[0]["owner_user_id"] == "2"
    payload = queued[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["user_id"] == "2"
    assert payload["cadence"] == "daily"
    assert isinstance(payload["scheduled_for"], str)


@pytest.mark.asyncio
async def test_scheduler_uses_string_owner_and_honors_cadence_flags(
    companion_scheduler_env,
) -> None:
    _seed_profile(
        "user-alpha",
        companion_daily_reflections_enabled=0,
        companion_weekly_reflections_enabled=1,
    )
    queued: list[dict[str, object]] = []
    scheduler = _CompanionReflectionScheduler()
    scheduler._jobs.create_job = lambda **kwargs: queued.append(kwargs) or {"id": 1}

    await scheduler._enqueue_all_users("daily")
    assert queued == []

    await scheduler._enqueue_all_users("weekly")

    assert len(queued) == 1
    assert queued[0]["owner_user_id"] == "user-alpha"
    payload = queued[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["user_id"] == "user-alpha"
    assert payload["cadence"] == "weekly"
