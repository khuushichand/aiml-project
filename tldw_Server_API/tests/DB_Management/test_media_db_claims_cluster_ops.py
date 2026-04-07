from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.scope_context import ScopeContext


pytestmark = pytest.mark.unit


_RUNTIME_MODULE_NAME = "tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_cluster_ops"


def _load_runtime_module():
    try:
        return importlib.import_module(_RUNTIME_MODULE_NAME)
    except ModuleNotFoundError:
        return None


def _load_helper(name: str):
    module = _load_runtime_module()
    if module is None:
        return None
    return getattr(module, name, None)


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-cluster-helper")
    db.initialize_db()
    return db


def _add_media_with_claim(
    db: MediaDatabase,
    *,
    title: str,
    content: str,
    claim_text: str,
) -> tuple[int, int]:
    media_id, _, _ = db.add_media_with_keywords(
        title=title,
        media_type="text",
        content=content,
        keywords=None,
    )
    chunk_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    db.upsert_claims(
        [
            {
                "media_id": media_id,
                "chunk_index": 0,
                "span_start": None,
                "span_end": None,
                "claim_text": claim_text,
                "confidence": 0.8,
                "extractor": "heuristic",
                "extractor_version": "v1",
                "chunk_hash": chunk_hash,
            }
        ]
    )
    row = db.execute_query(
        "SELECT id FROM Claims WHERE media_id = ? AND deleted = 0 ORDER BY id DESC LIMIT 1",
        (media_id,),
    ).fetchone()
    return int(media_id), int(row["id"])


def test_create_get_and_list_claim_clusters_rebind_and_preserve_filters(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claims-cluster-list.db")
    try:
        assert db.create_claim_cluster.__func__ is _load_helper("create_claim_cluster")
        assert db.get_claim_cluster.__func__ is _load_helper("get_claim_cluster")
        assert db.list_claim_clusters.__func__ is _load_helper("list_claim_clusters")

        _, alpha_claim_id = _add_media_with_claim(
            db,
            title="Alpha Doc",
            content="Alpha claim body.",
            claim_text="Alpha claim",
        )
        _, beta_claim_id = _add_media_with_claim(
            db,
            title="Beta Doc",
            content="Beta claim body.",
            claim_text="Beta claim",
        )

        alpha_cluster = db.create_claim_cluster(
            user_id="1",
            canonical_claim_text="Alpha claim",
            representative_claim_id=alpha_claim_id,
            summary="Alpha summary",
        )
        db.create_claim_cluster(
            user_id="1",
            canonical_claim_text="Beta claim",
            representative_claim_id=beta_claim_id,
            summary="Beta summary",
        )
        db.add_claim_to_cluster(
            cluster_id=int(alpha_cluster["id"]),
            claim_id=alpha_claim_id,
            similarity_score=1.0,
        )

        fetched = db.get_claim_cluster(int(alpha_cluster["id"]))
        listed = db.list_claim_clusters(
            "1",
            keyword="Alpha",
            watchlisted=False,
            min_size=1,
            limit=10,
            offset=0,
        )

        assert int(fetched["id"]) == int(alpha_cluster["id"])
        assert fetched["summary"] == "Alpha summary"
        assert [int(row["id"]) for row in listed] == [int(alpha_cluster["id"])]
    finally:
        db.close_connection()


def test_create_claim_cluster_preserves_postgres_returning_id_path() -> None:
    helper_create_claim_cluster = _load_helper("create_claim_cluster")
    assert helper_create_claim_cluster is not None

    class _Cursor:
        lastrowid = None

        def fetchone(self):
            return {"id": 13}

    execute_calls: list[tuple[str, tuple[object, ...], bool]] = []

    def _execute_query(sql, params=None, commit=False):
        execute_calls.append((sql, tuple(params or ()), commit))
        return _Cursor()

    fake_db = SimpleNamespace(
        backend_type=BackendType.POSTGRESQL,
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:00Z",
        execute_query=_execute_query,
        get_claim_cluster=lambda cluster_id: {"id": int(cluster_id)},
    )

    created = helper_create_claim_cluster(
        fake_db,
        user_id="1",
        canonical_claim_text="Alpha claim",
        representative_claim_id=7,
        summary="summary",
    )

    assert created == {"id": 13}
    assert execute_calls[0][0].endswith(" RETURNING id")


def test_claim_cluster_link_helpers_rebind_and_preserve_direction_filters(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-cluster-links.db")
    try:
        assert db.get_claim_cluster_link.__func__ is _load_helper("get_claim_cluster_link")
        assert db.list_claim_cluster_links.__func__ is _load_helper("list_claim_cluster_links")
        assert db.create_claim_cluster_link.__func__ is _load_helper("create_claim_cluster_link")
        assert db.delete_claim_cluster_link.__func__ is _load_helper("delete_claim_cluster_link")

        _, alpha_claim_id = _add_media_with_claim(
            db,
            title="Alpha Doc",
            content="Alpha claim body.",
            claim_text="Alpha claim",
        )
        _, beta_claim_id = _add_media_with_claim(
            db,
            title="Beta Doc",
            content="Beta claim body.",
            claim_text="Beta claim",
        )
        alpha_cluster = db.create_claim_cluster(
            user_id="1",
            canonical_claim_text="Alpha claim",
            representative_claim_id=alpha_claim_id,
        )
        beta_cluster = db.create_claim_cluster(
            user_id="1",
            canonical_claim_text="Beta claim",
            representative_claim_id=beta_claim_id,
        )

        created = db.create_claim_cluster_link(
            parent_cluster_id=int(alpha_cluster["id"]),
            child_cluster_id=int(beta_cluster["id"]),
            relation_type="related",
        )
        fetched = db.get_claim_cluster_link(
            parent_cluster_id=int(alpha_cluster["id"]),
            child_cluster_id=int(beta_cluster["id"]),
        )
        outbound = db.list_claim_cluster_links(
            cluster_id=int(alpha_cluster["id"]),
            direction="outbound",
        )
        inbound = db.list_claim_cluster_links(
            cluster_id=int(beta_cluster["id"]),
            direction="inbound",
        )
        deleted = db.delete_claim_cluster_link(
            parent_cluster_id=int(alpha_cluster["id"]),
            child_cluster_id=int(beta_cluster["id"]),
        )

        assert created["relation_type"] == "related"
        assert fetched["child_cluster_id"] == int(beta_cluster["id"])
        assert [(row["parent_cluster_id"], row["child_cluster_id"]) for row in outbound] == [
            (int(alpha_cluster["id"]), int(beta_cluster["id"]))
        ]
        assert [(row["parent_cluster_id"], row["child_cluster_id"]) for row in inbound] == [
            (int(alpha_cluster["id"]), int(beta_cluster["id"]))
        ]
        assert deleted == 1
        assert db.get_claim_cluster_link(
            parent_cluster_id=int(alpha_cluster["id"]),
            child_cluster_id=int(beta_cluster["id"]),
        ) == {}
    finally:
        db.close_connection()


def test_list_claim_cluster_members_rebind_and_preserves_scoped_visibility_filtering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _make_db(tmp_path, "claims-cluster-members.db")
    try:
        assert db.list_claim_cluster_members.__func__ is _load_helper("list_claim_cluster_members")

        runtime_module = _load_runtime_module()

        personal_media_id, personal_claim_id = _add_media_with_claim(
            db,
            title="Personal Doc",
            content="Personal claim body.",
            claim_text="Personal claim",
        )
        other_media_id, other_claim_id = _add_media_with_claim(
            db,
            title="Other Personal Doc",
            content="Other personal claim body.",
            claim_text="Other personal claim",
        )
        team_media_id, team_claim_id = _add_media_with_claim(
            db,
            title="Team Doc",
            content="Team claim body.",
            claim_text="Team claim",
        )
        db.execute_query(
            (
                "UPDATE Media SET visibility = ?, owner_user_id = ?, team_id = ?, org_id = ?, "
                "version = version + 1, last_modified = ? WHERE id = ?"
            ),
            ("personal", 1, None, None, "2026-03-22T00:00:11Z", personal_media_id),
            commit=True,
        )
        db.execute_query(
            (
                "UPDATE Media SET visibility = ?, owner_user_id = ?, team_id = ?, org_id = ?, "
                "version = version + 1, last_modified = ? WHERE id = ?"
            ),
            ("personal", 2, None, None, "2026-03-22T00:00:12Z", other_media_id),
            commit=True,
        )
        db.execute_query(
            (
                "UPDATE Media SET visibility = ?, owner_user_id = ?, team_id = ?, org_id = ?, "
                "version = version + 1, last_modified = ? WHERE id = ?"
            ),
            ("team", 99, 7, None, "2026-03-22T00:00:13Z", team_media_id),
            commit=True,
        )

        cluster = db.create_claim_cluster(
            user_id="1",
            canonical_claim_text="Cluster claim",
            representative_claim_id=personal_claim_id,
        )
        cluster_id = int(cluster["id"])
        for claim_id, score, joined_at in [
            (personal_claim_id, 0.95, "2026-03-22T00:00:01Z"),
            (other_claim_id, 0.85, "2026-03-22T00:00:02Z"),
            (team_claim_id, 0.75, "2026-03-22T00:00:03Z"),
        ]:
            db.execute_query(
                (
                    "INSERT INTO claim_cluster_membership "
                    "(cluster_id, claim_id, similarity_score, cluster_joined_at) "
                    "VALUES (?, ?, ?, ?)"
                ),
                (cluster_id, claim_id, score, joined_at),
                commit=True,
            )

        if runtime_module is not None:
            monkeypatch.setattr(
                runtime_module,
                "get_scope",
                lambda: ScopeContext(
                    user_id=1,
                    org_ids=[],
                    team_ids=[7],
                    active_org_id=None,
                    active_team_id=7,
                    is_admin=False,
                    session_role=None,
                ),
            )
        visible_rows = db.list_claim_cluster_members(cluster_id, limit=10, offset=0)

        if runtime_module is not None:
            monkeypatch.setattr(
                runtime_module,
                "get_scope",
                lambda: ScopeContext(
                    user_id=None,
                    org_ids=[],
                    team_ids=[],
                    active_org_id=None,
                    active_team_id=None,
                    is_admin=False,
                    session_role=None,
                ),
            )
        hidden_rows = db.list_claim_cluster_members(cluster_id, limit=10, offset=0)

        assert {row["claim_text"] for row in visible_rows} == {
            "Personal claim",
            "Team claim",
        }
        assert hidden_rows == []
    finally:
        db.close_connection()


def test_add_claim_to_cluster_rebind_and_preserve_assignment_and_version_bump(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-cluster-add.db")
    try:
        assert db.add_claim_to_cluster.__func__ is _load_helper("add_claim_to_cluster")

        _, alpha_claim_id = _add_media_with_claim(
            db,
            title="Alpha Doc",
            content="Alpha claim body.",
            claim_text="Alpha claim",
        )
        _, beta_claim_id = _add_media_with_claim(
            db,
            title="Beta Doc",
            content="Beta claim body.",
            claim_text="Beta claim",
        )
        cluster = db.create_claim_cluster(
            user_id="1",
            canonical_claim_text="Alpha claim",
            representative_claim_id=alpha_claim_id,
        )
        cluster_id = int(cluster["id"])

        db.add_claim_to_cluster(
            cluster_id=cluster_id,
            claim_id=beta_claim_id,
            similarity_score=0.98,
        )

        membership_row = db.execute_query(
            (
                "SELECT cluster_id, claim_id, similarity_score "
                "FROM claim_cluster_membership WHERE cluster_id = ? AND claim_id = ?"
            ),
            (cluster_id, beta_claim_id),
        ).fetchone()
        claim_row = db.execute_query(
            "SELECT claim_cluster_id FROM Claims WHERE id = ?",
            (beta_claim_id,),
        ).fetchone()
        cluster_row = db.execute_query(
            "SELECT cluster_version FROM claim_clusters WHERE id = ?",
            (cluster_id,),
        ).fetchone()

        assert int(membership_row["cluster_id"]) == cluster_id
        assert int(membership_row["claim_id"]) == beta_claim_id
        assert float(membership_row["similarity_score"]) == pytest.approx(0.98)
        assert int(claim_row["claim_cluster_id"]) == cluster_id
        assert int(cluster_row["cluster_version"]) == 2
    finally:
        db.close_connection()
