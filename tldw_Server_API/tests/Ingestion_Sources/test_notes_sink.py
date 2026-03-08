from __future__ import annotations

import pytest


class FakeNotesDB:
    def __init__(self) -> None:
        self.updated_calls: list[dict[str, object]] = []
        self.added_calls: list[dict[str, object]] = []

    def update_note(self, note_id: str, update_data: dict[str, object], expected_version: int):
        self.updated_calls.append(
            {
                "note_id": note_id,
                "update_data": update_data,
                "expected_version": expected_version,
            }
        )
        return True

    def add_note(self, *, title: str, content: str):
        self.added_calls.append({"title": title, "content": content})
        return "n-2"


@pytest.fixture
def fake_notes_db() -> FakeNotesDB:
    return FakeNotesDB()


@pytest.mark.unit
def test_notes_sink_does_not_overwrite_detached_note(fake_notes_db):
    from tldw_Server_API.app.core.Ingestion_Sources.sinks.notes_sink import apply_notes_change

    result = apply_notes_change(
        fake_notes_db,
        binding={"note_id": "n-1", "sync_status": "conflict_detached"},
        change={"event_type": "changed", "relative_path": "notes/a.md", "text": "# A\n\nNew body"},
        policy="canonical",
    )

    assert result["action"] == "skipped_detached"
    assert result["sync_status"] == "conflict_detached"
    assert fake_notes_db.updated_calls == []


@pytest.mark.unit
def test_notes_sink_creates_note_with_heading_title(fake_notes_db):
    from tldw_Server_API.app.core.Ingestion_Sources.sinks.notes_sink import apply_notes_change

    result = apply_notes_change(
        fake_notes_db,
        binding=None,
        change={"event_type": "created", "relative_path": "notes/a.md", "text": "# A\n\nBody"},
        policy="canonical",
    )

    assert result["action"] == "created"
    assert result["note_id"] == "n-2"
    assert fake_notes_db.added_calls[0]["title"] == "A"
