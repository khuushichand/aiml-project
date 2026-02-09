"""Tests for NoteGraphService."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from tldw_Server_API.app.api.v1.schemas.notes_graph import (
    EdgeType,
    NoteGraphRequest,
    TimeRange,
)
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import InputError
from tldw_Server_API.app.core.Notes_Graph.graph_cache import GraphCache
from tldw_Server_API.app.core.Notes_Graph.graph_service import (
    NoteGraphService,
    _decode_cursor,
    _encode_cursor,
)

pytestmark = pytest.mark.unit


def _uid():
    return str(uuid.uuid4())


def _mock_db(notes=None, edges=None, tag_edges=None, tag_counts=None,
             source_info=None, note_count=0, all_ids=None):
    """Build a MagicMock CharactersRAGDB with graph helpers."""
    db = MagicMock()
    _notes = notes or []
    _note_map = {n["id"]: n for n in _notes}

    def get_notes_batch(ids, include_deleted=True):
        return [_note_map[i] for i in ids if i in _note_map]

    def get_manual_edges_for_notes(user_id, note_ids):
        if edges is None:
            return []
        return [e for e in edges if e["from_note_id"] in note_ids or e["to_note_id"] in note_ids]

    def get_all_note_ids_for_graph(include_deleted=True, limit=500):
        return (all_ids or [i for i in _note_map])[:limit]

    def get_note_tag_edges(note_ids):
        if tag_edges is None:
            return []
        return [t for t in tag_edges if t["note_id"] in note_ids]

    def count_notes_per_tag():
        return tag_counts or {}

    def get_note_source_info(note_ids):
        if source_info is None:
            return []
        return [s for s in source_info if s["note_id"] in note_ids]

    def count_user_notes(include_deleted=True):
        return note_count

    db.get_notes_batch = MagicMock(side_effect=get_notes_batch)
    db.get_manual_edges_for_notes = MagicMock(side_effect=get_manual_edges_for_notes)
    db.get_all_note_ids_for_graph = MagicMock(side_effect=get_all_note_ids_for_graph)
    db.get_note_tag_edges = MagicMock(side_effect=get_note_tag_edges)
    db.count_notes_per_tag = MagicMock(side_effect=count_notes_per_tag)
    db.get_note_source_info = MagicMock(side_effect=get_note_source_info)
    db.count_user_notes = MagicMock(side_effect=count_user_notes)
    return db


def _note(nid, title="N", content="body", deleted=0, conv_id=None):
    return {
        "id": nid, "title": title, "content": content,
        "created_at": "2025-01-01T00:00:00", "last_modified": "2025-06-01T00:00:00",
        "deleted": deleted, "conversation_id": conv_id,
    }


def _manual_edge(from_id, to_id, user_id="u1", directed=False, weight=1.0):
    return {
        "edge_id": _uid(), "user_id": user_id,
        "from_note_id": from_id, "to_note_id": to_id,
        "type": "manual", "directed": int(directed), "weight": weight,
        "created_at": "2025-01-01T00:00:00", "created_by": "test", "metadata": None,
    }


class TestEgoGraphRadius1:
    def test_center_with_3_neighbors(self):
        center = _uid()
        n1, n2, n3 = _uid(), _uid(), _uid()
        notes = [_note(center), _note(n1), _note(n2), _note(n3)]
        edges = [
            _manual_edge(center, n1),
            _manual_edge(center, n2),
            _manual_edge(center, n3),
        ]
        db = _mock_db(notes=notes, edges=edges, note_count=4)
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(center_note_id=center, radius=1)
        resp = svc.generate_graph(req)
        note_ids = {n.id for n in resp.nodes if n.type == "note"}
        assert center in note_ids
        assert {n1, n2, n3} <= note_ids
        assert len(resp.edges) == 3


class TestEgoGraphRadius2:
    def test_two_layers(self):
        c = _uid()
        n1 = _uid()
        n2 = _uid()  # 2nd-hop neighbor
        notes = [_note(c), _note(n1), _note(n2)]
        edges_r1 = [_manual_edge(c, n1)]
        edges_r2 = [_manual_edge(n1, n2)]
        all_edges = edges_r1 + edges_r2
        db = _mock_db(notes=notes, edges=all_edges, note_count=3)
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(center_note_id=c, radius=2)
        resp = svc.generate_graph(req)
        note_ids = {n.id for n in resp.nodes if n.type == "note"}
        assert {c, n1, n2} == note_ids


class TestSeedlessSmallCollection:
    def test_full_graph(self):
        ids = [_uid() for _ in range(5)]
        notes = [_note(i) for i in ids]
        db = _mock_db(notes=notes, note_count=5, all_ids=ids)
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1)
        resp = svc.generate_graph(req)
        assert len([n for n in resp.nodes if n.type == "note"]) == 5


class TestSeedlessLargeRejected:
    def test_422_error(self):
        db = _mock_db(note_count=500)
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1)
        with pytest.raises(InputError):
            svc.generate_graph(req)


class TestTagFilterSeeds:
    def test_correct_seed_set(self):
        n1, n2, n3 = _uid(), _uid(), _uid()
        notes = [_note(n1), _note(n2), _note(n3)]
        tag_edges = [
            {"note_id": n1, "keyword_id": 1, "keyword": "ml"},
            {"note_id": n2, "keyword_id": 1, "keyword": "ml"},
        ]
        db = _mock_db(notes=notes, tag_edges=tag_edges, note_count=3, all_ids=[n1, n2, n3])
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(tag="ml", radius=1)
        resp = svc.generate_graph(req)
        note_ids = {n.id for n in resp.nodes if n.type == "note"}
        assert n1 in note_ids
        assert n2 in note_ids


class TestWikilinkEdges:
    def test_wikilink_in_content(self):
        n1 = _uid()
        n2 = _uid()
        notes = [
            _note(n1, content=f"See [[id:{n2}]] for details"),
            _note(n2),
        ]
        db = _mock_db(notes=notes, note_count=2, all_ids=[n1, n2])
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1, edge_types=[EdgeType.wikilink])
        resp = svc.generate_graph(req)
        wl = [e for e in resp.edges if e.type == EdgeType.wikilink]
        assert len(wl) == 1
        assert wl[0].source == n1
        assert wl[0].target == n2
        assert wl[0].directed is True


class TestBacklinkEdges:
    def test_reverse_of_wikilinks(self):
        n1 = _uid()
        n2 = _uid()
        notes = [
            _note(n1, content=f"Ref [[id:{n2}]]"),
            _note(n2),
        ]
        db = _mock_db(notes=notes, note_count=2, all_ids=[n1, n2])
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1, edge_types=[EdgeType.backlink])
        resp = svc.generate_graph(req)
        bl = [e for e in resp.edges if e.type == EdgeType.backlink]
        assert len(bl) == 1
        assert bl[0].source == n2
        assert bl[0].target == n1


class TestTagMembershipEdges:
    def test_from_note_keywords(self):
        n1 = _uid()
        notes = [_note(n1)]
        tag_edges = [{"note_id": n1, "keyword_id": 10, "keyword": "ai"}]
        db = _mock_db(notes=notes, tag_edges=tag_edges, note_count=1, all_ids=[n1])
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1, edge_types=[EdgeType.tag_membership])
        resp = svc.generate_graph(req)
        tm = [e for e in resp.edges if e.type == EdgeType.tag_membership]
        assert len(tm) == 1
        tag_n = [n for n in resp.nodes if n.type == "tag"]
        assert len(tag_n) == 1
        assert tag_n[0].label == "ai"


class TestPopularTagCutoff:
    def test_excluded(self):
        n1 = _uid()
        notes = [_note(n1)]
        tag_edges = [{"note_id": n1, "keyword_id": 5, "keyword": "popular"}]
        # 30 out of 100 notes = 30% > 15% cutoff, and 30 >= 25 absolute min
        tag_counts = {5: 30}
        db = _mock_db(
            notes=notes, tag_edges=tag_edges, tag_counts=tag_counts,
            note_count=100, all_ids=[n1],
        )
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1, edge_types=[EdgeType.tag_membership])
        resp = svc.generate_graph(req)
        tm = [e for e in resp.edges if e.type == EdgeType.tag_membership]
        assert len(tm) == 0

    def test_not_excluded_below_absolute(self):
        n1 = _uid()
        notes = [_note(n1)]
        tag_edges = [{"note_id": n1, "keyword_id": 5, "keyword": "semi"}]
        # 20% > 15% cutoff, but 20 < 25 absolute min → NOT excluded
        tag_counts = {5: 20}
        db = _mock_db(
            notes=notes, tag_edges=tag_edges, tag_counts=tag_counts,
            note_count=100, all_ids=[n1],
        )
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1, edge_types=[EdgeType.tag_membership])
        resp = svc.generate_graph(req)
        tm = [e for e in resp.edges if e.type == EdgeType.tag_membership]
        assert len(tm) == 1


class TestSourceMembershipEdges:
    def test_from_conversations(self):
        n1 = _uid()
        conv_id = _uid()
        notes = [_note(n1, conv_id=conv_id)]
        source_info = [
            {"note_id": n1, "conversation_id": conv_id, "source": "youtube", "external_ref": "abc123"},
        ]
        db = _mock_db(notes=notes, source_info=source_info, note_count=1, all_ids=[n1])
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1, edge_types=[EdgeType.source_membership])
        resp = svc.generate_graph(req)
        sm = [e for e in resp.edges if e.type == EdgeType.source_membership]
        assert len(sm) == 1
        src_n = [n for n in resp.nodes if n.type == "source"]
        assert len(src_n) == 1
        assert src_n[0].id == "source:youtube:abc123"


class TestMaxDegreeEnforced:
    def test_excess_neighbors_trimmed(self):
        center = _uid()
        neighbors = [_uid() for _ in range(10)]
        notes = [_note(center)] + [_note(n) for n in neighbors]
        edges = [_manual_edge(center, n) for n in neighbors]
        db = _mock_db(notes=notes, edges=edges, note_count=11)
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(center_note_id=center, radius=1, max_degree=3)
        resp = svc.generate_graph(req)
        # center + 3 max neighbors
        note_count = len([n for n in resp.nodes if n.type == "note"])
        assert note_count <= 4


class TestMaxNodesTruncation:
    def test_truncated_true(self):
        center = _uid()
        neighbors = [_uid() for _ in range(10)]
        notes = [_note(center)] + [_note(n) for n in neighbors]
        edges = [_manual_edge(center, n) for n in neighbors]
        db = _mock_db(notes=notes, edges=edges, note_count=11)
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(center_note_id=center, radius=1, max_nodes=5)
        resp = svc.generate_graph(req)
        assert resp.truncated is True
        assert "max_nodes" in resp.truncated_by


class TestRadius2Caps:
    def test_stricter_limits(self):
        center = _uid()
        notes = [_note(center)]
        db = _mock_db(notes=notes, note_count=1)
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(center_note_id=center, radius=2, max_nodes=300)
        resp = svc.generate_graph(req)
        assert resp.limits.max_nodes == 200
        assert resp.limits.max_edges == 800
        assert resp.limits.max_degree == 20
        assert resp.radius_cap_applied is True


class TestEdgeTypeFilter:
    def test_only_requested_types(self):
        n1 = _uid()
        n2 = _uid()
        notes = [
            _note(n1, content=f"[[id:{n2}]]"),
            _note(n2),
        ]
        edges = [_manual_edge(n1, n2)]
        tag_edges = [{"note_id": n1, "keyword_id": 1, "keyword": "test"}]
        db = _mock_db(notes=notes, edges=edges, tag_edges=tag_edges, note_count=2, all_ids=[n1, n2])
        svc = NoteGraphService(user_id="u1", db=db)
        # Only request manual edges
        req = NoteGraphRequest(radius=1, edge_types=[EdgeType.manual])
        resp = svc.generate_graph(req)
        types = {e.type for e in resp.edges}
        assert EdgeType.wikilink not in types
        assert EdgeType.tag_membership not in types


class TestDeletedNotesFlagged:
    def test_soft_deleted_in_graph(self):
        n1 = _uid()
        notes = [_note(n1, deleted=1)]
        db = _mock_db(notes=notes, note_count=1, all_ids=[n1])
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1)
        resp = svc.generate_graph(req)
        note_nodes = [n for n in resp.nodes if n.type == "note"]
        assert len(note_nodes) == 1
        assert note_nodes[0].deleted is True


class TestCacheHit:
    def test_second_call_uses_cache(self):
        n1 = _uid()
        notes = [_note(n1)]
        db = _mock_db(notes=notes, note_count=1, all_ids=[n1])
        cache = GraphCache(ttl_seconds=60, max_keys=100)
        svc = NoteGraphService(user_id="u1", db=db, cache=cache)
        req = NoteGraphRequest(radius=1)
        resp1 = svc.generate_graph(req)
        # Reset call count
        db.get_notes_batch.reset_mock()
        resp2 = svc.generate_graph(req)
        # Second call should not hit DB
        db.get_notes_batch.assert_not_called()
        assert resp1 == resp2


class TestCursorRoundtrip:
    def test_encode_decode(self):
        encoded = _encode_cursor(1, 42, "abc-123")
        decoded = _decode_cursor(encoded)
        assert decoded["layer"] == 1
        assert decoded["pos"] == 42
        assert decoded["last_id"] == "abc-123"


class TestDeterministicOrdering:
    def test_same_query_same_result(self):
        n1 = _uid()
        n2 = _uid()
        notes = [_note(n1), _note(n2)]
        edges = [_manual_edge(n1, n2)]
        db = _mock_db(notes=notes, edges=edges, note_count=2, all_ids=[n1, n2])
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1)
        r1 = svc.generate_graph(req)
        r2 = svc.generate_graph(req)
        assert [n.id for n in r1.nodes] == [n.id for n in r2.nodes]
        assert [e.id for e in r1.edges] == [e.id for e in r2.edges]


class TestEmptyGraph:
    def test_no_notes(self):
        db = _mock_db(note_count=0, all_ids=[])
        svc = NoteGraphService(user_id="u1", db=db)
        req = NoteGraphRequest(radius=1)
        resp = svc.generate_graph(req)
        assert resp.nodes == []
        assert resp.edges == []
        assert resp.truncated is False


class TestPruningOrder:
    def test_tag_source_before_wikilinks_before_manual(self):
        """When max_edges is hit, tag/source edges are pruned before wikilinks, manual last."""
        n1, n2 = _uid(), _uid()
        notes = [
            _note(n1, content=f"[[id:{n2}]]"),
            _note(n2),
        ]
        manual_edges = [_manual_edge(n1, n2)]
        tag_edges = [
            {"note_id": n1, "keyword_id": 1, "keyword": "t1"},
            {"note_id": n2, "keyword_id": 2, "keyword": "t2"},
        ]
        db = _mock_db(
            notes=notes, edges=manual_edges, tag_edges=tag_edges,
            note_count=2, all_ids=[n1, n2],
        )
        svc = NoteGraphService(user_id="u1", db=db)
        # Request all types but restrict edges to 2
        req = NoteGraphRequest(
            radius=1,
            edge_types=[EdgeType.manual, EdgeType.wikilink, EdgeType.tag_membership],
            max_edges=2,
        )
        resp = svc.generate_graph(req)
        types = [e.type for e in resp.edges]
        # Manual should survive; tag_membership should be pruned first
        assert EdgeType.manual in types
