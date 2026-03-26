from __future__ import annotations

import hashlib
import importlib
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)


pytestmark = pytest.mark.unit


_RUNTIME_MODULE_NAME = (
    "tldw_Server_API.app.core.DB_Management.media_db.runtime."
    "claims_cluster_assignment_rebuild_ops"
)


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
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="1")
    db.initialize_db()
    return db


def _seed_claim(db: MediaDatabase, *, title: str, content: str, claim_text: str) -> tuple[int, int]:
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
                "confidence": 0.9,
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


def test_rebuild_claim_clusters_from_assignments_rebinds_and_cleans_up_existing_state(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-cluster-assignments.db")
    try:
        assert db.rebuild_claim_clusters_from_assignments.__func__ is _load_helper(
            "rebuild_claim_clusters_from_assignments"
        )

        _, alpha_claim_id = _seed_claim(
            db,
            title="Alpha Doc",
            content="Alpha body",
            claim_text="Alpha claim",
        )
        _, beta_claim_id = _seed_claim(
            db,
            title="Beta Doc",
            content="Beta body",
            claim_text="Beta claim",
        )
        _, stale_claim_id = _seed_claim(
            db,
            title="Stale Doc",
            content="Stale body",
            claim_text="Stale claim",
        )

        stale_cluster = db.create_claim_cluster(
            user_id="1",
            canonical_claim_text="Stale cluster",
            representative_claim_id=stale_claim_id,
        )
        stale_cluster_id = int(stale_cluster["id"])
        db.add_claim_to_cluster(
            cluster_id=stale_cluster_id,
            claim_id=stale_claim_id,
            similarity_score=0.42,
        )

        result = db.rebuild_claim_clusters_from_assignments(
            user_id="1",
            clusters=[
                {
                    "canonical_claim_text": "Assigned cluster",
                    "representative_claim_id": alpha_claim_id,
                    "members": [
                        {"claim_id": alpha_claim_id, "similarity": 0.99},
                        {"similarity": 0.11},
                        {"claim_id": beta_claim_id, "similarity": None},
                    ],
                }
            ],
        )

        clusters = db.list_claim_clusters("1", limit=10, offset=0)
        cluster_id = int(clusters[0]["id"])
        members = db.list_claim_cluster_members(cluster_id, limit=10, offset=0)
        member_ids = {int(row["id"]) for row in members}
        stale_cluster_row = db.get_claim_cluster(stale_cluster_id)
        stale_claim_row = db.execute_query(
            "SELECT claim_cluster_id FROM Claims WHERE id = ?",
            (stale_claim_id,),
        ).fetchone()
        stale_membership_rows = db.execute_query(
            "SELECT claim_id FROM claim_cluster_membership WHERE cluster_id = ?",
            (stale_cluster_id,),
        ).fetchall()

        assert result == {"clusters_created": 1, "claims_assigned": 2}
        assert [int(row["cluster_version"]) for row in clusters] == [1]
        assert stale_cluster_row == {}
        assert member_ids == {alpha_claim_id, beta_claim_id}
        assert stale_claim_row["claim_cluster_id"] is None
        assert stale_membership_rows == []
    finally:
        db.close_connection()


def test_rebuild_claim_clusters_from_assignments_preserves_postgres_returning_id_path() -> None:
    helper_rebuild_claim_clusters_from_assignments = _load_helper(
        "rebuild_claim_clusters_from_assignments"
    )
    assert helper_rebuild_claim_clusters_from_assignments is not None

    class _InsertCursor:
        lastrowid = None

        def fetchone(self):
            return {"id": 17}

    class _NoopCursor:
        lastrowid = None

        def fetchone(self):
            return None

    execute_calls: list[tuple[str, tuple[object, ...]]] = []
    execute_many_calls: list[tuple[str, tuple[tuple[object, ...], ...]]] = []

    @contextmanager
    def _transaction():
        yield object()

    def _fetchall_with_connection(conn, sql, params=None):
        _ = conn
        params_tuple = tuple(params or ())
        if "SELECT id FROM claim_clusters" in sql:
            return [{"id": 5}]
        assert params_tuple == ("1",)
        return []

    def _execute_with_connection(conn, sql, params=None):
        _ = conn
        execute_calls.append((sql, tuple(params or ())))
        if "RETURNING id" in sql:
            return _InsertCursor()
        return _NoopCursor()

    def _execute_many(sql, params, *, connection=None):
        _ = connection
        execute_many_calls.append((sql, tuple(tuple(row) for row in params)))

    fake_db = SimpleNamespace(
        backend_type=BackendType.POSTGRESQL,
        transaction=_transaction,
        _fetchall_with_connection=_fetchall_with_connection,
        _execute_with_connection=_execute_with_connection,
        execute_many=_execute_many,
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:00Z",
    )

    result = helper_rebuild_claim_clusters_from_assignments(
        fake_db,
        user_id="1",
        clusters=[
            {
                "canonical_claim_text": "Alpha cluster",
                "representative_claim_id": 2,
                "members": [
                    {"claim_id": 2, "similarity": 0.98},
                    {"claim_id": 3, "similarity": None},
                    {"similarity": 0.50},
                ],
            }
        ],
    )

    assert result == {"clusters_created": 1, "claims_assigned": 2}
    assert any("DELETE FROM claim_cluster_membership" in sql for sql, _ in execute_calls)
    assert any("DELETE FROM claim_clusters" in sql for sql, _ in execute_calls)
    assert any(sql.endswith(" RETURNING id") for sql, _ in execute_calls)
    assert len(execute_many_calls) == 2
    assert len(execute_many_calls[0][1]) == 2
    assert len(execute_many_calls[1][1]) == 2
