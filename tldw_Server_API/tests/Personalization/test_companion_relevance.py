from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Personalization.companion_context import load_companion_context
from tldw_Server_API.app.core.Personalization.companion_relevance import rank_companion_candidates
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


@pytest.fixture()
def companion_relevance_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[Path]:
    base_dir = tmp_path / "user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")
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


def test_rank_companion_candidates_prefers_query_matching_goal_and_card() -> None:
    ranked = rank_companion_candidates(
        query="help me resume the backlog review",
        cards=[
            {
                "id": "card-1",
                "title": "Backlog review",
                "summary": "Weekly backlog pass",
                "evidence": [],
                "score": 0.8,
            },
            {
                "id": "card-2",
                "title": "Gardening",
                "summary": "Spring planting notes",
                "evidence": [],
                "score": 0.7,
            },
        ],
        goals=[
            {"id": "goal-1", "title": "Resume backlog review", "description": None, "status": "active"},
            {"id": "goal-2", "title": "Water garden", "description": None, "status": "active"},
        ],
        activity_rows=[
            {
                "id": "evt-1",
                "event_type": "reading_item_saved",
                "source_type": "reading_item",
                "source_id": "1",
                "tags": ["video"],
                "metadata": {"title": "Watched a video"},
            }
        ],
    )

    assert ranked["mode"] == "ranked"
    assert ranked["goal_ids"][0] == "goal-1"
    assert ranked["card_ids"][0] == "card-1"


def test_load_companion_context_falls_back_when_scores_are_weak(
    companion_relevance_env: Path,
) -> None:
    user_id = "81"
    db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))
    db.update_profile(user_id, enabled=1)
    db.upsert_companion_knowledge_card(
        user_id=user_id,
        card_type="project_focus",
        title="Current focus",
        summary="Recent explicit activity clusters around 'pytest'.",
        evidence=[{"source_id": "reading-1"}],
        score=0.9,
        status="active",
    )
    db.insert_companion_activity_event(
        user_id=user_id,
        event_type="reading_item_saved",
        source_type="reading_item",
        source_id="reading-1",
        surface="api.reading",
        dedupe_key="reading.save:reading-1",
        tags=["pytest"],
        provenance={"capture_mode": "explicit", "route": "/api/v1/reading/save"},
        metadata={"title": "Pytest Patterns"},
    )

    payload = load_companion_context(user_id=user_id, query="totally unrelated gardening note")

    assert payload["mode"] == "recent_fallback"
    assert payload["card_count"] == 1
    assert payload["activity_count"] == 1
