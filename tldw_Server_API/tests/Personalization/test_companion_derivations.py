from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Personalization.companion_derivations import derive_companion_knowledge_cards
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.services.personalization_consolidation import PersonalizationConsolidationService


pytestmark = pytest.mark.unit


def _insert_event(
    db: PersonalizationDB,
    *,
    user_id: str,
    event_type: str,
    source_id: str,
    tags: list[str],
    title: str,
) -> None:
    db.insert_companion_activity_event(
        user_id=user_id,
        event_type=event_type,
        source_type="reading_item",
        source_id=source_id,
        surface="api.reading",
        dedupe_key=f"{event_type}:{source_id}",
        tags=tags,
        provenance={"capture_mode": "explicit"},
        metadata={"title": title},
    )


@pytest.fixture()
def companion_derivations_env(monkeypatch, tmp_path):
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


def test_derive_companion_knowledge_cards_builds_project_focus_card(companion_derivations_env):
    user_id = "1"
    db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))

    _insert_event(
        db,
        user_id=user_id,
        event_type="reading_item_saved",
        source_id="101",
        tags=["project-alpha", "research"],
        title="Alpha kickoff",
    )
    _insert_event(
        db,
        user_id=user_id,
        event_type="reading_item_updated",
        source_id="102",
        tags=["project-alpha"],
        title="Alpha follow-up",
    )
    _insert_event(
        db,
        user_id=user_id,
        event_type="reading_item_saved",
        source_id="103",
        tags=["project-beta"],
        title="Beta note",
    )

    cards = derive_companion_knowledge_cards(db, user_id=user_id)

    assert len(cards) == 1
    card = cards[0]
    assert card["card_type"] == "project_focus"
    assert card["title"] == "Current focus"
    assert "project-alpha" in card["summary"]
    assert len(card["evidence"]) == 2


def test_consolidation_upserts_companion_knowledge_cards(companion_derivations_env):
    user_id = "1"
    db = PersonalizationDB(str(DatabasePaths.get_personalization_db_path(user_id)))

    _insert_event(
        db,
        user_id=user_id,
        event_type="watchlist_source_created",
        source_id="201",
        tags=["security", "alerting"],
        title="Security feeds",
    )
    _insert_event(
        db,
        user_id=user_id,
        event_type="watchlist_source_created",
        source_id="202",
        tags=["security", "triage"],
        title="Second security feed",
    )

    service = PersonalizationConsolidationService()
    service._consolidate_user(user_id)

    cards = db.list_companion_knowledge_cards(user_id)
    assert len(cards) == 1
    assert cards[0]["card_type"] == "project_focus"
    assert "security" in cards[0]["summary"]
