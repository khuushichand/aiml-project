from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Personalization.companion_lifecycle import (
    purge_companion_scope,
    rebuild_companion_scope,
)
from tldw_Server_API.app.core.Personalization.companion_reflection_jobs import run_companion_reflection_job


pytestmark = pytest.mark.unit


@pytest.fixture()
def companion_lifecycle_env(monkeypatch, tmp_path) -> Iterator[SimpleNamespace]:
    base_dir = tmp_path / "test_companion_lifecycle"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    user_id = "1"
    personalization_db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))
    collections_db = CollectionsDatabase.for_user(user_id=int(user_id))
    personalization_db.update_profile(user_id, enabled=1)

    try:
        yield SimpleNamespace(
            user_id=user_id,
            personalization_db=personalization_db,
            collections_db=collections_db,
        )
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def _seed_explicit_activity(env) -> None:
    env.personalization_db.insert_companion_activity_event(
        user_id=env.user_id,
        event_type="reading_item_saved",
        source_type="reading_item",
        source_id="101",
        surface="api.reading",
        dedupe_key="reading_item_saved:101",
        tags=["project-alpha", "backlog"],
        provenance={"capture_mode": "explicit"},
        metadata={"title": "Alpha kickoff"},
    )
    env.personalization_db.insert_companion_activity_event(
        user_id=env.user_id,
        event_type="note_updated",
        source_type="note",
        source_id="202",
        surface="api.notes",
        dedupe_key="note_updated:202",
        tags=["project-alpha", "backlog"],
        provenance={"capture_mode": "explicit"},
        metadata={"title": "Backlog review notes"},
    )


def _seed_reflection(env) -> str:
    _seed_explicit_activity(env)
    env.personalization_db.upsert_companion_knowledge_card(
        user_id=env.user_id,
        card_type="project_focus",
        title="Current focus",
        summary="Recent explicit activity clusters around 'project-alpha'.",
        evidence=[{"source_id": "101"}, {"source_id": "202"}],
        score=0.9,
    )
    result = run_companion_reflection_job(
        user_id=env.user_id,
        cadence="daily",
        personalization_db=env.personalization_db,
        collections_db=env.collections_db,
    )
    assert result["status"] == "completed"
    return str(result["reflection_id"])


def _seed_manual_goal(env) -> str:
    return env.personalization_db.create_companion_goal(
        user_id=env.user_id,
        title="Follow up on backlog",
        description=None,
        goal_type="manual",
        config={},
        progress={"completed_count": 0},
        origin_kind="manual",
        progress_mode="manual",
        evidence=[],
        status="active",
    )


def test_purge_reflections_removes_activity_and_linked_notifications(companion_lifecycle_env) -> None:
    reflection_id = _seed_reflection(companion_lifecycle_env)

    result = purge_companion_scope(
        user_id=companion_lifecycle_env.user_id,
        scope="reflections",
        personalization_db=companion_lifecycle_env.personalization_db,
        collections_db=companion_lifecycle_env.collections_db,
    )

    assert result["status"] == "completed"
    assert result["deleted_counts"]["reflections"] == 1
    assert result["deleted_counts"]["notifications"] == 1

    rows, _ = companion_lifecycle_env.personalization_db.list_companion_activity_events(
        companion_lifecycle_env.user_id,
        limit=50,
        offset=0,
    )
    assert all(row["id"] != reflection_id for row in rows)
    assert companion_lifecycle_env.collections_db.list_user_notifications(limit=10, offset=0) == []


def test_rebuild_knowledge_recomputes_cards_without_touching_manual_goals(companion_lifecycle_env) -> None:
    manual_goal_id = _seed_manual_goal(companion_lifecycle_env)
    _seed_explicit_activity(companion_lifecycle_env)

    result = rebuild_companion_scope(
        user_id=companion_lifecycle_env.user_id,
        scope="knowledge",
        personalization_db=companion_lifecycle_env.personalization_db,
    )

    assert result["status"] == "completed"
    assert result["rebuilt_counts"]["knowledge"] >= 1
    goals = companion_lifecycle_env.personalization_db.list_companion_goals(companion_lifecycle_env.user_id)
    assert any(goal["id"] == manual_goal_id and goal["origin_kind"] == "manual" for goal in goals)

    cards = companion_lifecycle_env.personalization_db.list_companion_knowledge_cards(
        companion_lifecycle_env.user_id,
        status="active",
    )
    assert cards


def test_rebuild_goal_progress_is_non_destructive_without_derivation_logic(companion_lifecycle_env) -> None:
    goal_id = companion_lifecycle_env.personalization_db.create_companion_goal(
        user_id=companion_lifecycle_env.user_id,
        title="Computed backlog progress",
        description=None,
        goal_type="manual",
        config={},
        progress={"completed_count": 2},
        origin_kind="manual",
        progress_mode="computed",
        evidence=[],
        status="active",
    )

    result = rebuild_companion_scope(
        user_id=companion_lifecycle_env.user_id,
        scope="goal_progress",
        personalization_db=companion_lifecycle_env.personalization_db,
    )

    assert result["status"] == "completed"
    assert result["deleted_counts"]["goal_progress"] == 0
    goal = next(
        goal
        for goal in companion_lifecycle_env.personalization_db.list_companion_goals(
            companion_lifecycle_env.user_id
        )
        if goal["id"] == goal_id
    )
    assert goal["progress"] == {"completed_count": 2}


def test_rebuild_derived_goals_is_non_destructive_without_derivation_logic(companion_lifecycle_env) -> None:
    goal_id = companion_lifecycle_env.personalization_db.create_companion_goal(
        user_id=companion_lifecycle_env.user_id,
        title="Derived focus goal",
        description=None,
        goal_type="derived_focus",
        config={},
        progress={},
        origin_kind="derived",
        progress_mode="computed",
        evidence=[],
        status="active",
    )

    result = rebuild_companion_scope(
        user_id=companion_lifecycle_env.user_id,
        scope="derived_goals",
        personalization_db=companion_lifecycle_env.personalization_db,
    )

    assert result["status"] == "completed"
    assert result["deleted_counts"]["derived_goals"] == 0
    goals = companion_lifecycle_env.personalization_db.list_companion_goals(
        companion_lifecycle_env.user_id
    )
    assert any(goal["id"] == goal_id for goal in goals)
