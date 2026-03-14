"""Tests for workspace sub-resource API endpoints (DB-layer validation)."""
import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB, ConflictError


@pytest.fixture
def db(tmp_path):
    d = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    d.upsert_workspace("ws-1", "Test WS")
    return d


class TestSourceEndpoints:
    def test_add_and_list_sources(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "Video",
            "source_type": "video",
        })
        sources = db.list_workspace_sources("ws-1")
        assert len(sources) == 1
        assert sources[0]["title"] == "Video"

    def test_update_source_returns_409_on_stale_version(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "X",
            "source_type": "video",
        })
        db.update_workspace_source("ws-1", "src-1", {"title": "Y"}, expected_version=1)
        with pytest.raises(ConflictError):
            db.update_workspace_source("ws-1", "src-1", {"title": "Z"}, expected_version=1)


class TestArtifactEndpoints:
    def test_add_and_list_artifacts(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "Summary",
        })
        arts = db.list_workspace_artifacts("ws-1")
        assert len(arts) == 1

    def test_update_artifact_returns_409_on_stale_version(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "X",
        })
        db.update_workspace_artifact("ws-1", "art-1", {"title": "Y"}, expected_version=1)
        with pytest.raises(ConflictError):
            db.update_workspace_artifact("ws-1", "art-1", {"title": "Z"}, expected_version=1)


class TestNoteEndpoints:
    def test_add_and_list_notes(self, db):
        db.add_workspace_note("ws-1", {"title": "N1", "content": "body"})
        notes = db.list_workspace_notes("ws-1")
        assert len(notes) == 1
        assert notes[0]["title"] == "N1"

    def test_soft_delete_note_hides_from_list(self, db):
        note = db.add_workspace_note("ws-1", {"title": "N1", "content": ""})
        db.delete_workspace_note("ws-1", note["id"])
        assert db.list_workspace_notes("ws-1") == []
