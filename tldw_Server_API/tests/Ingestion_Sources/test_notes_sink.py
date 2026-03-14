from __future__ import annotations

import pytest


class FakeNotesDB:
    def __init__(self) -> None:
        self.updated_calls: list[dict[str, object]] = []
        self.added_calls: list[dict[str, object]] = []
        self.soft_deleted_calls: list[dict[str, object]] = []
        self.source_folder_calls: list[dict[str, object]] = []

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

    def soft_delete_note(self, note_id: str, expected_version: int):
        self.soft_deleted_calls.append(
            {
                "note_id": note_id,
                "expected_version": expected_version,
            }
        )
        return True

    def sync_note_source_folders(self, note_id: str, source_id: int, folder_paths: list[str]):
        self.source_folder_calls.append(
            {
                "note_id": note_id,
                "source_id": source_id,
                "folder_paths": folder_paths,
            }
        )
        return [
            {
                "id": idx + 1,
                "name": path.split("/")[-1],
                "path": path,
                "parent_id": None if "/" not in path else idx,
            }
            for idx, path in enumerate(folder_paths)
        ]


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


@pytest.mark.unit
def test_notes_sink_soft_deletes_note_for_canonical_upstream_delete(fake_notes_db):
    from tldw_Server_API.app.core.Ingestion_Sources.sinks.notes_sink import apply_notes_change

    result = apply_notes_change(
        fake_notes_db,
        binding={"note_id": "n-1", "current_version": 3, "sync_status": "sync_managed"},
        change={"event_type": "deleted", "relative_path": "notes/a.md"},
        policy="canonical",
    )

    assert result["action"] == "archived"
    assert result["note_id"] == "n-1"
    assert result["sync_status"] == "archived_upstream_removed"
    assert fake_notes_db.soft_deleted_calls == [
        {
            "note_id": "n-1",
            "expected_version": 3,
        }
    ]


@pytest.mark.unit
def test_notes_sink_syncs_source_managed_folders_from_relative_path(fake_notes_db):
    from tldw_Server_API.app.core.Ingestion_Sources.sinks.notes_sink import apply_notes_change

    result = apply_notes_change(
        fake_notes_db,
        binding=None,
        change={
            "event_type": "created",
            "relative_path": "docs/api/a.md",
            "text": "# A\n\nBody",
            "source_id": 91,
        },
        policy="canonical",
    )

    assert result["action"] == "created"
    assert fake_notes_db.source_folder_calls == [
        {
            "note_id": "n-2",
            "source_id": 91,
            "folder_paths": ["docs", "docs/api"],
        }
    ]
