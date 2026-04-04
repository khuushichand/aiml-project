# test_manuscript_analysis_db.py
# Tests for manuscript AI analysis CRUD.
#
from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    ConflictError,
)
from tldw_Server_API.app.core.DB_Management.ManuscriptDB import ManuscriptDBHelper


@pytest.fixture()
def mdb(tmp_path):
    db = CharactersRAGDB(str(tmp_path / "test.db"), client_id="test_client")
    return ManuscriptDBHelper(db)


class TestAnalysisCRUD:
    def test_create_and_get(self, mdb):
        pid = mdb.create_project("Novel")
        ch_id = mdb.create_chapter(pid, "Ch1")
        scene_id = mdb.create_scene(ch_id, pid, title="S1", content_json="{}", content_plain="text")
        aid = mdb.create_analysis(pid, "scene", scene_id, "pacing",
                                  {"pacing": 0.7, "tension": 0.5}, score=0.7)
        analysis = mdb.get_analysis(aid)
        assert analysis is not None
        assert analysis["analysis_type"] == "pacing"
        assert analysis["result"]["pacing"] == 0.7
        assert analysis["score"] == 0.7
        assert analysis["stale"] == 0

    def test_create_with_provider_and_model(self, mdb):
        pid = mdb.create_project("Novel")
        aid = mdb.create_analysis(
            pid, "project", pid, "consistency", {"ok": True},
            provider="openai", model="gpt-4o",
        )
        analysis = mdb.get_analysis(aid)
        assert analysis["provider"] == "openai"
        assert analysis["model"] == "gpt-4o"

    def test_get_missing_returns_none(self, mdb):
        assert mdb.get_analysis("nonexistent") is None

    def test_list_by_project(self, mdb):
        pid = mdb.create_project("Novel")
        ch_id = mdb.create_chapter(pid, "Ch1")
        sid = mdb.create_scene(ch_id, pid, title="S1", content_json="{}", content_plain="text")
        mdb.create_analysis(pid, "scene", sid, "pacing", {"pacing": 0.5})
        mdb.create_analysis(pid, "scene", sid, "tension", {"tension": 0.8})
        analyses = mdb.list_analyses(pid)
        assert len(analyses) == 2

    def test_list_filter_by_type(self, mdb):
        pid = mdb.create_project("Novel")
        ch_id = mdb.create_chapter(pid, "Ch1")
        sid = mdb.create_scene(ch_id, pid, title="S1", content_json="{}", content_plain="text")
        mdb.create_analysis(pid, "scene", sid, "pacing", {})
        mdb.create_analysis(pid, "scene", sid, "tension", {})
        analyses = mdb.list_analyses(pid, analysis_type="pacing")
        assert len(analyses) == 1

    def test_list_filter_by_scope(self, mdb):
        pid = mdb.create_project("Novel")
        ch_id = mdb.create_chapter(pid, "Ch1")
        s1 = mdb.create_scene(ch_id, pid, title="S1", content_json="{}", content_plain="a")
        s2 = mdb.create_scene(ch_id, pid, title="S2", content_json="{}", content_plain="b")
        mdb.create_analysis(pid, "scene", s1, "pacing", {})
        mdb.create_analysis(pid, "scene", s2, "pacing", {})
        analyses = mdb.list_analyses(pid, scope_type="scene", scope_id=s1)
        assert len(analyses) == 1

    def test_list_excludes_stale_by_default(self, mdb):
        pid = mdb.create_project("Novel")
        ch_id = mdb.create_chapter(pid, "Ch1")
        sid = mdb.create_scene(ch_id, pid, title="S1", content_json="{}", content_plain="text")
        mdb.create_analysis(pid, "scene", sid, "pacing", {})
        mdb.mark_analyses_stale("scene", sid)
        analyses = mdb.list_analyses(pid)
        assert len(analyses) == 0
        analyses_with_stale = mdb.list_analyses(pid, include_stale=True)
        assert len(analyses_with_stale) == 1

    def test_list_excludes_deleted(self, mdb):
        pid = mdb.create_project("Novel")
        aid = mdb.create_analysis(pid, "project", pid, "consistency", {})
        mdb.soft_delete_analysis(aid, expected_version=1)
        analyses = mdb.list_analyses(pid)
        assert len(analyses) == 0

    def test_mark_stale(self, mdb):
        pid = mdb.create_project("Novel")
        ch_id = mdb.create_chapter(pid, "Ch1")
        sid = mdb.create_scene(ch_id, pid, title="S1", content_json="{}", content_plain="text")
        aid = mdb.create_analysis(pid, "scene", sid, "pacing", {})
        count = mdb.mark_analyses_stale("scene", sid)
        assert count == 1
        analysis = mdb.get_analysis(aid)
        assert analysis["stale"] == 1

    def test_mark_stale_idempotent(self, mdb):
        pid = mdb.create_project("Novel")
        ch_id = mdb.create_chapter(pid, "Ch1")
        sid = mdb.create_scene(ch_id, pid, title="S1", content_json="{}", content_plain="text")
        mdb.create_analysis(pid, "scene", sid, "pacing", {})
        assert mdb.mark_analyses_stale("scene", sid) == 1
        # Second call should find no fresh rows to mark
        assert mdb.mark_analyses_stale("scene", sid) == 0

    def test_soft_delete(self, mdb):
        pid = mdb.create_project("Novel")
        aid = mdb.create_analysis(pid, "project", pid, "consistency", {})
        mdb.soft_delete_analysis(aid, expected_version=1)
        assert mdb.get_analysis(aid) is None

    def test_soft_delete_version_conflict(self, mdb):
        pid = mdb.create_project("Novel")
        aid = mdb.create_analysis(pid, "project", pid, "consistency", {})
        with pytest.raises(ConflictError):
            mdb.soft_delete_analysis(aid, expected_version=99)

    def test_scene_update_marks_analyses_stale(self, mdb):
        pid = mdb.create_project("Novel")
        ch_id = mdb.create_chapter(pid, "Ch1")
        sid = mdb.create_scene(ch_id, pid, title="S1", content_json="{}", content_plain="old text")
        aid = mdb.create_analysis(pid, "scene", sid, "pacing", {"pacing": 0.5})
        # Verify not stale initially
        assert mdb.get_analysis(aid)["stale"] == 0
        # Update scene content
        mdb.update_scene(sid, {"content_plain": "new text entirely different"}, expected_version=1)
        # Verify analysis is now stale
        analysis = mdb.get_analysis(aid)
        assert analysis["stale"] == 1

    def test_scene_update_non_content_does_not_mark_stale(self, mdb):
        pid = mdb.create_project("Novel")
        ch_id = mdb.create_chapter(pid, "Ch1")
        sid = mdb.create_scene(ch_id, pid, title="S1", content_json="{}", content_plain="text")
        aid = mdb.create_analysis(pid, "scene", sid, "pacing", {"pacing": 0.5})
        # Update only the title, not content
        mdb.update_scene(sid, {"title": "S1 Renamed"}, expected_version=1)
        # Analysis should still be fresh
        assert mdb.get_analysis(aid)["stale"] == 0
