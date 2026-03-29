"""Unit tests for Notes Studio service orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    InputError,
)
from tldw_Server_API.app.core.Notes.studio_service import NotesStudioService


pytestmark = pytest.mark.unit


@pytest.fixture()
def studio_db(tmp_path: Path):
    db = CharactersRAGDB(str(tmp_path / "notes_studio_unit.db"), client_id="notes_studio_unit")
    yield db


def _derive_note(
    service: NotesStudioService,
    *,
    source_note_id: str,
    excerpt_text: str,
    template_type: str = "lined",
    handwriting_mode: str = "accented",
) -> dict:
    return asyncio.run(
        service.derive_from_excerpt(
            source_note_id=source_note_id,
            excerpt_text=excerpt_text,
            template_type=template_type,
            handwriting_mode=handwriting_mode,
        )
    )


def test_derive_creates_derived_note_and_sidecar(studio_db):
    db = studio_db
    source_note_id = db.add_note(
        title="Source Note",
        content=(
            "Cells need energy to function.\n"
            "The mitochondrion is the powerhouse of the cell.\n"
            "ATP stores usable energy."
        ),
    )
    assert source_note_id is not None

    service = NotesStudioService(db=db)
    excerpt = "The mitochondrion is the powerhouse of the cell."

    result = _derive_note(
        service,
        source_note_id=str(source_note_id),
        excerpt_text=excerpt,
    )

    note = result["note"]
    studio_document = result["studio_document"]

    assert note["id"] != str(source_note_id)
    assert note["title"] == "Source Note Study Notes"
    assert note["content"].startswith("# Source Note Study Notes")
    assert "## Key Questions" in note["content"]
    assert "## Notes" in note["content"]
    assert "## Summary" in note["content"]
    assert "Template:" not in note["content"]
    assert "handwriting_mode" not in note["content"]
    assert result["is_stale"] is False
    assert result["stale_reason"] is None

    assert studio_document["source_note_id"] == str(source_note_id)
    assert studio_document["excerpt_snapshot"] == excerpt
    assert studio_document["excerpt_hash"].startswith("sha256:")
    assert studio_document["companion_content_hash"].startswith("sha256:")
    assert studio_document["payload_json"]["meta"]["source_note_id"] == str(source_note_id)
    assert studio_document["payload_json"]["layout"] == {
        "template_type": "lined",
        "handwriting_mode": "accented",
        "render_version": 1,
    }


def test_cornell_generation_includes_explicit_recall_prompt(studio_db):
    db = studio_db
    source_note_id = db.add_note(
        title="Biology",
        content="Photosynthesis converts light energy into chemical energy for plants.",
    )
    assert source_note_id is not None

    service = NotesStudioService(db=db)
    result = _derive_note(
        service,
        source_note_id=str(source_note_id),
        excerpt_text="Photosynthesis converts light energy into chemical energy for plants.",
        template_type="cornell",
    )

    note_content = result["note"]["content"]
    cue_section = result["studio_document"]["payload_json"]["sections"][0]

    assert cue_section["kind"] == "cue"
    assert any(
        "Recall prompt:" in item or "Fill in the blank:" in item
        for item in cue_section["items"]
    )
    assert "Recall prompt:" in note_content or "Fill in the blank:" in note_content


def test_derive_rolls_back_note_when_sidecar_persistence_fails(studio_db, monkeypatch: pytest.MonkeyPatch):
    db = studio_db
    source_note_id = db.add_note(
        title="Physics",
        content="Velocity describes speed with direction.",
    )
    assert source_note_id is not None

    service = NotesStudioService(db=db)
    original_note_ids = [note["id"] for note in db.list_notes()]

    def _raise_sidecar_failure(**_kwargs):
        raise CharactersRAGDBError("sidecar write failed")

    monkeypatch.setattr(db, "create_note_studio_document", _raise_sidecar_failure)

    with pytest.raises(CharactersRAGDBError, match="sidecar write failed"):
        _derive_note(
            service,
            source_note_id=str(source_note_id),
            excerpt_text="Velocity describes speed with direction.",
        )

    assert [note["id"] for note in db.list_notes()] == original_note_ids


def test_get_state_detects_markdown_drift_and_regenerate_rebuilds_payload_from_current_markdown(studio_db):
    db = studio_db
    source_note_id = db.add_note(
        title="Chemistry",
        content="Atoms form bonds by sharing or transferring electrons.",
    )
    assert source_note_id is not None

    service = NotesStudioService(db=db)
    result = _derive_note(
        service,
        source_note_id=str(source_note_id),
        excerpt_text="Atoms form bonds by sharing or transferring electrons.",
    )
    note_id = result["note"]["id"]

    initial_state = asyncio.run(service.get_note_studio_state(note_id=note_id))
    assert initial_state["is_stale"] is False

    current_note = db.get_note_by_id(note_id=note_id)
    assert current_note is not None
    manual_markdown = (
        "# Chemistry Refined Study Notes\n\n"
        "## Key Questions\n\n"
        "- Which particles are shared in covalent bonds?\n"
        "- What changes during electron transfer?\n\n"
        "## Notes\n\n"
        "Atoms form bonds by sharing or transferring electrons.\n"
        "Electron transfer can create ions.\n\n"
        "## Summary\n\n"
        "Bonding changes electron stability."
    )
    db.update_note(
        note_id=note_id,
        update_data={"content": manual_markdown},
        expected_version=int(current_note["version"]),
    )

    stale_state = asyncio.run(service.get_note_studio_state(note_id=note_id))
    assert stale_state["is_stale"] is True
    assert stale_state["stale_reason"] == "companion_content_hash_mismatch"

    regenerated = asyncio.run(service.regenerate_note_markdown(note_id=note_id))
    assert regenerated["is_stale"] is False
    assert regenerated["stale_reason"] is None
    assert regenerated["note"]["title"] == "Chemistry Refined Study Notes"
    assert regenerated["note"]["content"] == manual_markdown
    assert regenerated["studio_document"]["companion_content_hash"].startswith("sha256:")
    assert regenerated["studio_document"]["payload_json"]["meta"]["title"] == "Chemistry Refined Study Notes"
    assert regenerated["studio_document"]["payload_json"]["layout"] == {
        "template_type": "lined",
        "handwriting_mode": "accented",
        "render_version": 1,
    }
    assert regenerated["studio_document"]["payload_json"]["sections"] == [
        {
            "id": "cue-1",
            "kind": "cue",
            "title": "Key Questions",
            "items": [
                "Which particles are shared in covalent bonds?",
                "What changes during electron transfer?",
            ],
        },
        {
            "id": "notes-1",
            "kind": "notes",
            "title": "Notes",
            "content": "Atoms form bonds by sharing or transferring electrons.\nElectron transfer can create ions.",
        },
        {
            "id": "summary-1",
            "kind": "summary",
            "title": "Summary",
            "content": "Bonding changes electron stability.",
        },
    ]
    persisted_note = db.get_note_by_id(note_id=note_id)
    assert persisted_note is not None
    assert persisted_note["title"] == "Chemistry Refined Study Notes"


def test_regenerate_rolls_back_note_update_when_sidecar_upsert_fails(studio_db, monkeypatch: pytest.MonkeyPatch):
    db = studio_db
    source_note_id = db.add_note(
        title="Astronomy",
        content="Stars form inside dense molecular clouds.",
    )
    assert source_note_id is not None

    service = NotesStudioService(db=db)
    result = _derive_note(
        service,
        source_note_id=str(source_note_id),
        excerpt_text="Stars form inside dense molecular clouds.",
    )
    note_id = result["note"]["id"]

    current_note = db.get_note_by_id(note_id=note_id)
    assert current_note is not None
    draft_markdown = (
        "# Astronomy Refined Study Notes\n\n"
        "## Key Questions\n\n"
        "* Where do stars form?\n"
        "* What is dense inside the cloud?\n\n"
        "## Notes\n\n"
        "Stars form inside dense molecular clouds.\n"
        "Gravity compresses the gas over time.\n\n"
        "## Summary\n\n"
        "Dense clouds can collapse into new stars."
    )
    db.update_note(
        note_id=note_id,
        update_data={"content": draft_markdown},
        expected_version=int(current_note["version"]),
    )

    def _raise_sidecar_failure(**_kwargs):
        raise CharactersRAGDBError("sidecar upsert failed")

    monkeypatch.setattr(db, "upsert_note_studio_document", _raise_sidecar_failure)

    with pytest.raises(CharactersRAGDBError, match="sidecar upsert failed"):
        asyncio.run(service.regenerate_note_markdown(note_id=note_id))

    note_after_failure = db.get_note_by_id(note_id=note_id)
    assert note_after_failure is not None
    assert note_after_failure["title"] == "Astronomy Study Notes"
    assert note_after_failure["content"] == draft_markdown


def test_update_diagram_manifest_persists_notebook_diagram_metadata(studio_db):
    db = studio_db
    source_note_id = db.add_note(
        title="History",
        content="The printing press accelerated the spread of written knowledge.",
    )
    assert source_note_id is not None

    service = NotesStudioService(db=db)
    result = _derive_note(
        service,
        source_note_id=str(source_note_id),
        excerpt_text="The printing press accelerated the spread of written knowledge.",
    )
    note_id = result["note"]["id"]
    section_ids = [section["id"] for section in result["studio_document"]["payload_json"]["sections"]]

    updated = asyncio.run(
        service.update_diagram_manifest(
            note_id=note_id,
            diagram_type="flowchart",
            source_section_ids=section_ids[:2],
        )
    )
    manifest = updated["studio_document"]["diagram_manifest_json"]

    assert manifest["diagram_type"] == "flowchart"
    assert manifest["source_section_ids"] == section_ids[:2]
    assert manifest["source_graph"]
    assert manifest["cached_svg"].startswith("<svg")
    assert manifest["render_hash"].startswith("sha256:")
    assert manifest["generation_status"] == "ready"


@pytest.mark.parametrize(
    ("excerpt_text", "expected_message"),
    [
        ("   ", "excerpt_text cannot be empty."),
        ("Not present in source note", "excerpt_text must match content from the source note."),
    ],
)
def test_derive_rejects_invalid_excerpt_requests(studio_db, excerpt_text, expected_message):
    db = studio_db
    source_note_id = db.add_note(
        title="Source",
        content="Useful content for excerpt validation.",
    )
    assert source_note_id is not None

    service = NotesStudioService(db=db)

    with pytest.raises(InputError, match=expected_message):
        _derive_note(
            service,
            source_note_id=str(source_note_id),
            excerpt_text=excerpt_text,
        )
