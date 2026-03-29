"""Tests for Notes Studio sidecar storage and shared schema models."""

from __future__ import annotations

import sqlite3

import pytest

from tldw_Server_API.app.api.v1.schemas.notes_studio import (
    NoteStudioDocumentCreateRequest,
    NoteStudioDocumentResponse,
)
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture
def db(tmp_path: pytest.TempPathFactory) -> CharactersRAGDB:
    database = CharactersRAGDB(db_path=str(tmp_path / "chacha_studio.db"), client_id="studio-user")
    yield database
    database.close_connection()


def test_note_studio_schema_models_validate_core_fields() -> None:
    request = NoteStudioDocumentCreateRequest(
        note_id="note-1",
        payload_json={"meta": {"source_note_id": "note-1"}, "sections": []},
        template_type="lined",
        handwriting_mode="accented",
        source_note_id="note-1",
        excerpt_snapshot="beta",
        excerpt_hash="sha256:demo",
        companion_content_hash="sha256:markdown",
        render_version=1,
    )

    assert request.note_id == "note-1"  # nosec B101
    assert request.template_type == "lined"  # nosec B101
    assert request.handwriting_mode == "accented"  # nosec B101
    assert request.render_version == 1  # nosec B101

    response = NoteStudioDocumentResponse.model_validate(
        {
            **request.model_dump(),
            "created_at": "2026-03-28T00:00:00Z",
            "last_modified": "2026-03-28T00:00:00Z",
        }
    )
    assert response.note_id == "note-1"  # nosec B101
    assert response.payload_json["meta"]["source_note_id"] == "note-1"  # nosec B101


def test_notes_db_creates_note_studio_documents_table(db: CharactersRAGDB) -> None:
    conn = db.get_connection()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        ("note_studio_documents",),
    ).fetchone()

    assert row is not None  # nosec B101
    assert row["name"] == "note_studio_documents"  # nosec B101


def test_create_and_fetch_note_studio_document_by_note_id(db: CharactersRAGDB) -> None:
    note_id = db.add_note(title="Source", content="Alpha beta gamma")

    created = db.create_note_studio_document(
        note_id=note_id,
        payload_json={"meta": {"source_note_id": note_id}, "sections": []},
        template_type="lined",
        handwriting_mode="accented",
        source_note_id=note_id,
        excerpt_snapshot="beta",
        excerpt_hash="sha256:demo",
        companion_content_hash="sha256:markdown",
        render_version=1,
    )

    assert created["note_id"] == note_id  # nosec B101
    assert created["template_type"] == "lined"  # nosec B101
    assert created["handwriting_mode"] == "accented"  # nosec B101

    studio = db.get_note_studio_document(note_id)
    assert studio is not None  # nosec B101
    assert studio["note_id"] == note_id  # nosec B101
    assert studio["template_type"] == "lined"  # nosec B101
    assert studio["handwriting_mode"] == "accented"  # nosec B101
    assert studio["payload_json"]["meta"]["source_note_id"] == note_id  # nosec B101


def test_soft_delete_preserves_sidecar_and_restore_reuses_same_row(db: CharactersRAGDB) -> None:
    note_id = db.add_note(title="Source", content="Alpha beta gamma")
    db.create_note_studio_document(
        note_id=note_id,
        payload_json={"meta": {"source_note_id": note_id}, "sections": []},
        template_type="cornell",
        handwriting_mode="accented",
        source_note_id=note_id,
        excerpt_snapshot="beta",
        excerpt_hash="sha256:demo",
        companion_content_hash="sha256:markdown",
        render_version=1,
    )

    before_delete = db.get_note_studio_document(note_id)
    assert before_delete is not None  # nosec B101

    deleted = db.soft_delete_note(note_id, expected_version=1)
    assert deleted is True  # nosec B101

    after_delete = db.get_note_studio_document(note_id)
    assert after_delete is not None  # nosec B101
    assert after_delete == before_delete  # nosec B101

    restored = db.restore_note(note_id, expected_version=2)
    assert restored is True  # nosec B101

    after_restore = db.get_note_studio_document(note_id)
    assert after_restore is not None  # nosec B101
    assert after_restore == before_delete  # nosec B101


def test_hard_delete_removes_sidecar(db: CharactersRAGDB) -> None:
    note_id = db.add_note(title="Source", content="Alpha beta gamma")
    db.create_note_studio_document(
        note_id=note_id,
        payload_json={"meta": {"source_note_id": note_id}, "sections": []},
        template_type="grid",
        handwriting_mode="off",
        source_note_id=note_id,
        excerpt_snapshot="beta",
        excerpt_hash="sha256:demo",
        companion_content_hash="sha256:markdown",
        render_version=1,
    )

    deleted = db.delete_note(note_id, hard_delete=True)
    assert deleted is True  # nosec B101
    assert db.get_note_studio_document(note_id) is None  # nosec B101

    conn = db.get_connection()
    row = conn.execute(
        "SELECT note_id FROM note_studio_documents WHERE note_id = ?",
        (note_id,),
    ).fetchone()
    assert row is None  # nosec B101


def test_stale_state_hashes_are_persisted_and_compared_explicitly(db: CharactersRAGDB) -> None:
    note_id = db.add_note(title="Source", content="Alpha beta gamma")
    db.create_note_studio_document(
        note_id=note_id,
        payload_json={"meta": {"source_note_id": note_id}, "sections": []},
        template_type="lined",
        handwriting_mode="accented",
        source_note_id=note_id,
        excerpt_snapshot="beta",
        excerpt_hash="sha256:excerpt",
        companion_content_hash="sha256:markdown",
        render_version=1,
    )

    studio = db.get_note_studio_document(note_id)
    assert studio is not None  # nosec B101
    assert studio["excerpt_hash"] == "sha256:excerpt"  # nosec B101
    assert studio["companion_content_hash"] == "sha256:markdown"  # nosec B101
    assert studio["companion_content_hash"] != "sha256:changed-markdown"  # nosec B101


def test_note_fetch_can_include_lightweight_studio_summary(db: CharactersRAGDB) -> None:
    note_id = db.add_note(title="Source", content="Alpha beta gamma")
    db.create_note_studio_document(
        note_id=note_id,
        payload_json={"meta": {"source_note_id": note_id}, "sections": []},
        template_type="grid",
        handwriting_mode="off",
        source_note_id=note_id,
        excerpt_snapshot="beta",
        excerpt_hash="sha256:excerpt",
        companion_content_hash="sha256:markdown",
        render_version=1,
    )

    note = db.get_note_by_id(note_id, include_studio_summary=True)
    assert note is not None  # nosec B101
    assert note["studio"]["note_id"] == note_id  # nosec B101
    assert note["studio"]["template_type"] == "grid"  # nosec B101
    assert "payload_json" not in note["studio"]  # nosec B101
