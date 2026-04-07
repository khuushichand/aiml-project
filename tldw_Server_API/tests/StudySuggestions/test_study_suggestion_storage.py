import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    ConflictError,
    InputError,
)
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


@pytest.fixture
def db(tmp_path):
    chacha = CharactersRAGDB(str(tmp_path / "study-suggestions.db"), client_id="study-suggestion-tests")
    try:
        yield chacha
    finally:
        chacha.close_connection()


def test_create_suggestion_snapshot_defaults_to_active_status(db: CharactersRAGDB):
    snapshot_id = db.create_suggestion_snapshot(
        service="quiz",
        activity_type="quiz_attempt",
        anchor_type="quiz_attempt",
        anchor_id=101,
        suggestion_type="study_suggestions",
        payload_json={"summary": {"score": 7}, "topics": [{"display_label": "Renal basics"}]},
    )

    row = db.get_suggestion_snapshot(snapshot_id)

    assert row["service"] == "quiz"  # nosec B101
    assert row["status"] == "active"  # nosec B101
    assert row["user_selection_json"] is None  # nosec B101


def test_create_suggestion_snapshot_rejects_unknown_status(db: CharactersRAGDB):
    with pytest.raises(ValueError):
        db.create_suggestion_snapshot(
            service="quiz",
            activity_type="quiz_attempt",
            anchor_type="quiz_attempt",
            anchor_id=101,
            suggestion_type="study_suggestions",
            status="archived",
            payload_json={"summary": {"score": 7}},
        )


def test_suggestion_snapshot_payload_defaults_to_permission_safe_fields_only(db: CharactersRAGDB):
    snapshot_id = db.create_suggestion_snapshot(
        service="quiz",
        activity_type="quiz_attempt",
        anchor_type="quiz_attempt",
        anchor_id=101,
        suggestion_type="study_suggestions",
        payload_json={
            "summary": {"score": 7, "correct_count": 7},
            "topics": [
                {
                    "display_label": "Renal basics",
                    "source_type": "note",
                    "source_id": "note-7",
                    "selected": True,
                    "excerpt_text": "This long explanation should not be persisted.",
                    "quote_text": "A long quote that should not be stored by default.",
                    "rich_excerpt": {"markdown": "> quoted block"},
                    "unsafe_blob": "x" * 500,
                    "analysis_markdown": "## Detailed reasoning that should not persist",
                }
            ],
            "narrative": "A verbose explanation that is not a safe label/ref/count/flag field.",
            "quote_cache": ["remove this"],
        },
    )

    row = db.get_suggestion_snapshot(snapshot_id)
    payload = row["payload_json"]

    assert payload["summary"]["score"] == 7  # nosec B101
    assert payload["topics"][0]["display_label"] == "Renal basics"  # nosec B101
    assert payload["topics"][0]["source_id"] == "note-7"  # nosec B101
    assert payload["topics"][0]["selected"] is True  # nosec B101
    assert "excerpt_text" not in payload["topics"][0]  # nosec B101
    assert "quote_text" not in payload["topics"][0]  # nosec B101
    assert "rich_excerpt" not in payload["topics"][0]  # nosec B101
    assert "unsafe_blob" not in payload["topics"][0]  # nosec B101
    assert "analysis_markdown" not in payload["topics"][0]  # nosec B101
    assert "narrative" not in payload  # nosec B101
    assert "quote_cache" not in payload  # nosec B101


def test_suggestion_snapshot_user_selection_survives_refresh_lineage_without_resubmission(db: CharactersRAGDB):
    original_id = db.create_suggestion_snapshot(
        service="quiz",
        activity_type="quiz_attempt",
        anchor_type="quiz_attempt",
        anchor_id=101,
        suggestion_type="study_suggestions",
        payload_json={"topics": [{"display_label": "Renal basics"}]},
        user_selection_json={"selected_topic_ids": ["topic-1"]},
    )
    refreshed_id = db.create_suggestion_snapshot(
        service="quiz",
        activity_type="quiz_attempt",
        anchor_type="quiz_attempt",
        anchor_id=101,
        suggestion_type="study_suggestions",
        payload_json={"topics": [{"display_label": "Renal basics"}, {"display_label": "Electrolytes"}]},
        refreshed_from_snapshot_id=original_id,
    )

    refreshed = db.get_suggestion_snapshot(refreshed_id)
    snapshots = db.list_suggestion_snapshots_for_anchor("quiz_attempt", 101)

    assert refreshed["refreshed_from_snapshot_id"] == original_id  # nosec B101
    assert refreshed["user_selection_json"] == {"selected_topic_ids": ["topic-1"]}  # nosec B101
    assert [row["id"] for row in snapshots] == [refreshed_id, original_id]  # nosec B101


def test_suggestion_snapshot_rejects_invalid_user_selection_json_string(db: CharactersRAGDB):
    with pytest.raises(InputError, match="user_selection_json"):
        db.create_suggestion_snapshot(
            service="quiz",
            activity_type="quiz_attempt",
            anchor_type="quiz_attempt",
            anchor_id=101,
            suggestion_type="study_suggestions",
            payload_json={"topics": [{"display_label": "Renal basics"}]},
            user_selection_json="{not-valid-json",
        )


def test_suggestion_snapshot_rejects_refresh_reference_from_different_lineage(db: CharactersRAGDB):
    original_id = db.create_suggestion_snapshot(
        service="quiz",
        activity_type="quiz_attempt",
        anchor_type="quiz_attempt",
        anchor_id=101,
        suggestion_type="study_suggestions",
        payload_json={"topics": [{"display_label": "Renal basics"}]},
        user_selection_json={"selected_topic_ids": ["topic-1"]},
    )

    with pytest.raises(InputError, match="same suggestion lineage"):
        db.create_suggestion_snapshot(
            service="quiz",
            activity_type="quiz_attempt",
            anchor_type="quiz_attempt",
            anchor_id=202,
            suggestion_type="study_suggestions",
            payload_json={"topics": [{"display_label": "Electrolytes"}]},
            refreshed_from_snapshot_id=original_id,
        )


def test_generation_links_persist_one_row_per_snapshot_action_result(db: CharactersRAGDB):
    snapshot_id = db.create_suggestion_snapshot(
        service="quiz",
        activity_type="quiz_attempt",
        anchor_type="quiz_attempt",
        anchor_id=101,
        suggestion_type="study_suggestions",
        payload_json={"topics": [{"display_label": "Renal basics"}]},
    )

    first_link_id = db.create_suggestion_generation_link(
        snapshot_id=snapshot_id,
        target_service="quiz",
        target_type="quiz",
        target_id="quiz-55",
        selection_fingerprint="sel-1",
    )
    second_link_id = db.create_suggestion_generation_link(
        snapshot_id=snapshot_id,
        target_service="flashcards",
        target_type="deck",
        target_id="deck-8",
        selection_fingerprint="sel-2",
    )

    first_row = db.find_suggestion_generation_link(
        snapshot_id=snapshot_id,
        target_service="quiz",
        target_type="quiz",
        target_id="quiz-55",
        selection_fingerprint="sel-1",
    )
    second_row = db.find_suggestion_generation_link(
        snapshot_id=snapshot_id,
        target_service="flashcards",
        target_type="deck",
        target_id="deck-8",
        selection_fingerprint="sel-2",
    )
    count_row = db.execute_query(
        "SELECT COUNT(*) AS count FROM suggestion_generation_links WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()

    assert first_link_id != second_link_id  # nosec B101
    assert first_row["target_service"] == "quiz"  # nosec B101
    assert second_row["target_service"] == "flashcards"  # nosec B101
    assert count_row["count"] == 2  # nosec B101


def test_suggestion_generation_link_duplicate_is_conflict_but_fk_failure_is_not(db: CharactersRAGDB):
    snapshot_id = db.create_suggestion_snapshot(
        service="quiz",
        activity_type="quiz_attempt",
        anchor_type="quiz_attempt",
        anchor_id=101,
        suggestion_type="study_suggestions",
        payload_json={"topics": [{"display_label": "Renal basics"}]},
    )

    db.create_suggestion_generation_link(
        snapshot_id=snapshot_id,
        target_service="quiz",
        target_type="quiz",
        target_id="quiz-55",
        selection_fingerprint="sel-1",
    )

    with pytest.raises(ConflictError, match="already exists"):
        db.create_suggestion_generation_link(
            snapshot_id=snapshot_id,
            target_service="quiz",
            target_type="quiz",
            target_id="quiz-55",
            selection_fingerprint="sel-1",
        )

    with pytest.raises(Exception) as exc_info:
        db.create_suggestion_generation_link(
            snapshot_id=999999,
            target_service="quiz",
            target_type="quiz",
            target_id="quiz-56",
            selection_fingerprint="sel-fk",
        )

    assert not isinstance(exc_info.value, ConflictError)  # nosec B101


def test_suggestion_storage_tables_include_sync_and_version_fields(db: CharactersRAGDB):
    snapshot_columns = {
        column["name"]
        for column in db.backend.get_table_info("suggestion_snapshots")
    }
    link_columns = {
        column["name"]
        for column in db.backend.get_table_info("suggestion_generation_links")
    }

    assert {"created_at", "last_modified", "deleted", "client_id", "version"} <= snapshot_columns  # nosec B101
    assert {"created_at", "last_modified", "deleted", "client_id", "version"} <= link_columns  # nosec B101


@pytest.mark.integration
def test_suggestion_storage_postgres_round_trip_and_integrity(pg_database_config: DatabaseConfig):
    backend = DatabaseBackendFactory.create_backend(pg_database_config)
    db = CharactersRAGDB(db_path=":memory:", client_id="study-suggestion-pg", backend=backend)

    try:
        snapshot_id = db.create_suggestion_snapshot(
            service="quiz",
            activity_type="quiz_attempt",
            anchor_type="quiz_attempt",
            anchor_id=101,
            suggestion_type="study_suggestions",
            payload_json={"topics": [{"display_label": "Renal basics", "source_id": "note-1"}]},
            user_selection_json={"selected_topic_ids": ["topic-1"]},
        )

        row = db.get_suggestion_snapshot(snapshot_id)
        assert row is not None  # nosec B101
        assert row["user_selection_json"] == {"selected_topic_ids": ["topic-1"]}  # nosec B101

        db.create_suggestion_generation_link(
            snapshot_id=snapshot_id,
            target_service="quiz",
            target_type="quiz",
            target_id="quiz-55",
            selection_fingerprint="sel-1",
        )

        with pytest.raises(ConflictError, match="already exists"):
            db.create_suggestion_generation_link(
                snapshot_id=snapshot_id,
                target_service="quiz",
                target_type="quiz",
                target_id="quiz-55",
                selection_fingerprint="sel-1",
            )

        with pytest.raises(Exception) as exc_info:
            db.create_suggestion_generation_link(
                snapshot_id=999999,
                target_service="quiz",
                target_type="quiz",
                target_id="quiz-56",
                selection_fingerprint="sel-fk",
            )

        assert not isinstance(exc_info.value, ConflictError)  # nosec B101
    finally:
        try:
            db.close_connection()
            if db.backend_type.name == "POSTGRESQL":
                db.backend.get_pool().close_all()
        except Exception:
            _ = None
