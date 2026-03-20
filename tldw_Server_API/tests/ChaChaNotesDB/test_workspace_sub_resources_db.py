"""Tests for workspace sub-resource tables: sources, artifacts, notes."""
import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB, ConflictError


@pytest.fixture
def db(tmp_path):
    d = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    d.upsert_workspace("ws-1", "Test WS")
    return d


class TestWorkspaceSources:
    def test_add_source(self, db):
        src = db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 42, "title": "My Video",
            "source_type": "video",
        })
        assert src["id"] == "src-1"
        assert src["media_id"] == 42
        assert src["version"] == 1

    def test_list_sources_ordered_by_position(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-a", "media_id": 1, "title": "A",
            "source_type": "video", "position": 2,
        })
        db.add_workspace_source("ws-1", {
            "id": "src-b", "media_id": 2, "title": "B",
            "source_type": "pdf", "position": 1,
        })
        sources = db.list_workspace_sources("ws-1")
        assert sources[0]["id"] == "src-b"
        assert sources[1]["id"] == "src-a"

    def test_update_source_with_version_check(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "Old",
            "source_type": "video",
        })
        updated = db.update_workspace_source("ws-1", "src-1", {"title": "New"}, expected_version=1)
        assert updated["title"] == "New"
        assert updated["version"] == 2

    def test_update_source_stale_version_raises(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "X",
            "source_type": "video",
        })
        db.update_workspace_source("ws-1", "src-1", {"title": "Y"}, expected_version=1)
        with pytest.raises(ConflictError):
            db.update_workspace_source("ws-1", "src-1", {"title": "Z"}, expected_version=1)

    def test_delete_source(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "X",
            "source_type": "video",
        })
        db.delete_workspace_source("ws-1", "src-1")
        assert db.list_workspace_sources("ws-1") == []

    def test_batch_update_selection(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-a", "media_id": 1, "title": "A",
            "source_type": "video",
        })
        db.add_workspace_source("ws-1", {
            "id": "src-b", "media_id": 2, "title": "B",
            "source_type": "pdf",
        })
        db.update_workspace_source_selection("ws-1", selected_ids=["src-a"])
        sources = db.list_workspace_sources("ws-1")
        sel = {s["id"]: s["selected"] for s in sources}
        assert sel["src-a"] in (True, 1)
        assert sel["src-b"] in (False, 0)

    def test_batch_reorder(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-a", "media_id": 1, "title": "A",
            "source_type": "video",
        })
        db.add_workspace_source("ws-1", {
            "id": "src-b", "media_id": 2, "title": "B",
            "source_type": "pdf",
        })
        db.reorder_workspace_sources("ws-1", ["src-b", "src-a"])
        sources = db.list_workspace_sources("ws-1")
        assert sources[0]["id"] == "src-b"
        assert sources[0]["position"] == 0
        assert sources[1]["id"] == "src-a"
        assert sources[1]["position"] == 1


class TestWorkspaceArtifacts:
    def test_add_artifact(self, db):
        art = db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "Summary",
        })
        assert art["id"] == "art-1"
        assert art["artifact_type"] == "summary"

    def test_list_artifacts(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "S1",
        })
        db.add_workspace_artifact("ws-1", {
            "id": "art-2", "artifact_type": "podcast", "title": "P1",
        })
        arts = db.list_workspace_artifacts("ws-1")
        assert len(arts) == 2

    def test_update_artifact_with_version_check(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "Old",
        })
        updated = db.update_workspace_artifact("ws-1", "art-1", {"title": "New"}, expected_version=1)
        assert updated["title"] == "New"
        assert updated["version"] == 2

    def test_update_artifact_stale_version_raises(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "X",
        })
        db.update_workspace_artifact("ws-1", "art-1", {"title": "Y"}, expected_version=1)
        with pytest.raises(ConflictError):
            db.update_workspace_artifact("ws-1", "art-1", {"title": "Z"}, expected_version=1)

    def test_delete_artifact(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "X",
        })
        db.delete_workspace_artifact("ws-1", "art-1")
        assert db.list_workspace_artifacts("ws-1") == []


class TestWorkspaceNotes:
    def test_add_note(self, db):
        note = db.add_workspace_note("ws-1", {
            "title": "My Note", "content": "Hello",
        })
        assert note["title"] == "My Note"
        assert note["version"] == 1

    def test_list_notes_excludes_deleted(self, db):
        db.add_workspace_note("ws-1", {"title": "N1", "content": ""})
        n2 = db.add_workspace_note("ws-1", {"title": "N2", "content": ""})
        db.delete_workspace_note("ws-1", n2["id"])
        notes = db.list_workspace_notes("ws-1")
        assert len(notes) == 1
        assert notes[0]["title"] == "N1"

    def test_update_note_with_version_check(self, db):
        note = db.add_workspace_note("ws-1", {"title": "Old", "content": ""})
        updated = db.update_workspace_note("ws-1", note["id"], {"title": "New"}, expected_version=1)
        assert updated["title"] == "New"
        assert updated["version"] == 2


class TestWorkspaceSettings:
    def test_update_workspace_banner_settings(self, db):
        ws = db.update_workspace("ws-1", {
            "banner_title": "My Project",
            "banner_subtitle": "Research notes",
        }, expected_version=1)
        assert ws["banner_title"] == "My Project"
        assert ws["banner_subtitle"] == "Research notes"

    def test_update_workspace_audio_settings(self, db):
        ws = db.update_workspace("ws-1", {
            "audio_provider": "openai",
            "audio_model": "tts-1",
            "audio_voice": "alloy",
        }, expected_version=1)
        assert ws["audio_provider"] == "openai"
        assert ws["audio_model"] == "tts-1"


class TestFKCascadeOnHardDelete:
    def test_hard_delete_workspace_cascades_to_sources(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "X",
            "source_type": "video",
        })
        db.hard_delete_workspace("ws-1")
        assert db.list_workspace_sources("ws-1") == []

    def test_hard_delete_workspace_cascades_to_artifacts(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "X",
        })
        db.hard_delete_workspace("ws-1")
        assert db.list_workspace_artifacts("ws-1") == []

    def test_hard_delete_workspace_cascades_to_notes(self, db):
        db.add_workspace_note("ws-1", {"title": "N", "content": ""})
        db.hard_delete_workspace("ws-1")
        assert db.list_workspace_notes("ws-1") == []
