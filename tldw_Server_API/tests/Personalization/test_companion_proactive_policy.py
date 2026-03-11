from __future__ import annotations

import importlib
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Personalization.companion_reflection_jobs import (
    run_companion_reflection_job,
)


pytestmark = pytest.mark.unit


@pytest.fixture()
def companion_proactive_env(monkeypatch, tmp_path):
    base_dir = tmp_path / "test_companion_proactive_policy"
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


def _seed_low_signal_duplicate_theme(user_id: str) -> tuple[PersonalizationDB, CollectionsDatabase]:
    personalization_db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))
    collections_db = CollectionsDatabase.for_user(user_id=int(user_id))
    personalization_db.update_profile(user_id, enabled=1)
    personalization_db.insert_companion_activity_event(
        user_id=user_id,
        event_type="companion_reflection_generated",
        source_type="companion_reflection",
        source_id="2026-03-09",
        surface="jobs.companion",
        dedupe_key="companion.reflection:daily:2026-03-09",
        tags=["backlog-review"],
        provenance={"capture_mode": "explicit"},
        metadata={
            "title": "Daily reflection",
            "summary": "Earlier backlog review reflection",
            "cadence": "daily",
            "delivery_decision": "delivered",
            "delivery_reason": "meaningful_signal",
            "theme_key": "backlog-review",
            "signal_strength": 0.9,
            "follow_up_prompts": [],
            "evidence": [],
        },
    )
    personalization_db.insert_companion_activity_event(
        user_id=user_id,
        event_type="note_updated",
        source_type="note",
        source_id="101",
        surface="api.notes",
        dedupe_key="note_updated:101",
        tags=["backlog-review"],
        provenance={"capture_mode": "explicit"},
        metadata={"title": "Backlog notes"},
    )
    personalization_db.insert_companion_activity_event(
        user_id=user_id,
        event_type="reading_item_saved",
        source_type="reading_item",
        source_id="102",
        surface="api.reading",
        dedupe_key="reading_item_saved:102",
        tags=["backlog-review"],
        provenance={"capture_mode": "explicit"},
        metadata={"title": "Backlog review article"},
    )
    return personalization_db, collections_db


def test_companion_proactive_policy_suppresses_low_signal_duplicate_theme() -> None:
    module_path = "tldw_Server_API.app.core.Personalization.companion_proactive"
    assert importlib.util.find_spec(module_path) is not None
    module = importlib.import_module(module_path)
    assert hasattr(module, "classify_companion_reflection_delivery")

    decision = module.classify_companion_reflection_delivery(
        cadence="daily",
        activity_count=2,
        theme_key="backlog-review",
        signal_strength=1.0,
        recent_reflections=[
            {
                "theme_key": "backlog-review",
                "signal_strength": 0.9,
                "delivery_decision": "delivered",
            }
        ],
    )

    assert decision["delivery_decision"] == "suppressed"
    assert decision["delivery_reason"] == "duplicate_weak_delta"


def test_companion_reflection_job_persists_suppressed_reflection_without_notification(
    companion_proactive_env,
) -> None:
    personalization_db, collections_db = _seed_low_signal_duplicate_theme("1")

    result = run_companion_reflection_job(
        user_id="1",
        cadence="daily",
        now=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
        personalization_db=personalization_db,
        collections_db=collections_db,
    )

    assert result["status"] == "completed"
    assert result["delivery_decision"] == "suppressed"

    notifications = collections_db.list_user_notifications(limit=20, offset=0)
    assert all(item.link_id != result["reflection_id"] for item in notifications)
