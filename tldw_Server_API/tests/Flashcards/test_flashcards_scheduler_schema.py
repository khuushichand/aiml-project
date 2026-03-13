import json

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture
def chacha_db(tmp_path):
    db = CharactersRAGDB(str(tmp_path / "flashcards-scheduler.db"), client_id="flashcard-scheduler-tests")
    try:
        yield db
    finally:
        db.close_connection()


def test_scheduler_schema_columns_exist_on_fresh_db(chacha_db: CharactersRAGDB):
    deck_columns = {
        row["name"] for row in chacha_db.execute_query("PRAGMA table_info('decks')").fetchall()
    }
    flashcard_columns = {
        row["name"] for row in chacha_db.execute_query("PRAGMA table_info('flashcards')").fetchall()
    }
    review_columns = {
        row["name"] for row in chacha_db.execute_query("PRAGMA table_info('flashcard_reviews')").fetchall()
    }

    assert "scheduler_settings_json" in deck_columns
    assert "queue_state" in flashcard_columns
    assert "step_index" in flashcard_columns
    assert "suspended_reason" in flashcard_columns
    assert "previous_queue_state" in review_columns
    assert "next_queue_state" in review_columns
    assert "previous_due_at" in review_columns
    assert "next_due_at" in review_columns


def test_new_deck_persists_default_scheduler_settings(chacha_db: CharactersRAGDB):
    deck_id = chacha_db.add_deck("Scheduler Defaults")
    deck = chacha_db.get_deck(deck_id)

    assert deck is not None
    raw_settings = deck.get("scheduler_settings_json")
    assert isinstance(raw_settings, str)

    settings = json.loads(raw_settings)
    assert settings["new_steps_minutes"] == [1, 10]
    assert settings["relearn_steps_minutes"] == [10]
    assert settings["graduating_interval_days"] == 1
    assert settings["easy_interval_days"] == 4
    assert settings["easy_bonus"] == pytest.approx(1.3)
    assert settings["interval_modifier"] == pytest.approx(1.0)
    assert settings["max_interval_days"] == 36500
    assert settings["leech_threshold"] == 8
    assert settings["enable_fuzz"] is False
