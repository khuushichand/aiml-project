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
    "tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_cluster_exact_rebuild_ops"
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


def _seed_claim(db: MediaDatabase, *, content: str, claim_text: str, title: str) -> tuple[int, int]:
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


def test_rebuild_claim_clusters_exact_rebinds_and_preserves_exact_grouping_and_cleanup(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-cluster-exact.db")
    try:
        assert db.rebuild_claim_clusters_exact.__func__ is _load_helper(
            "rebuild_claim_clusters_exact"
        )

        _, alpha_claim_id = _seed_claim(
            db,
            title="Alpha Doc",
            content="Alpha body",
            claim_text="Alpha claim",
        )
        _, alpha_spaced_claim_id = _seed_claim(
            db,
            title="Alpha Spaced Doc",
            content="Alpha spaced body",
            claim_text=" alpha   claim ",
        )
        _, unique_claim_id = _seed_claim(
            db,
            title="Unique Doc",
            content="Unique body",
            claim_text="Unique claim",
        )

        stale_cluster = db.create_claim_cluster(
            user_id="1",
            canonical_claim_text="Stale cluster",
            representative_claim_id=unique_claim_id,
        )
        stale_cluster_id = int(stale_cluster["id"])
        db.add_claim_to_cluster(
            cluster_id=stale_cluster_id,
            claim_id=unique_claim_id,
            similarity_score=0.42,
        )

        result = db.rebuild_claim_clusters_exact(user_id="1", min_size="invalid")

        clusters = db.list_claim_clusters("1", limit=10, offset=0)
        assert result == {"clusters_created": 1, "claims_assigned": 2}
        assert [int(row["cluster_version"]) for row in clusters] == [2]
        assert [int(row["id"]) for row in clusters] != [stale_cluster_id]
        assert db.get_claim_cluster(stale_cluster_id) == {}

        cluster_id = int(clusters[0]["id"])
        members = db.list_claim_cluster_members(cluster_id, limit=10, offset=0)
        member_ids = {int(row["id"]) for row in members}
        unique_claim_row = db.execute_query(
            "SELECT claim_cluster_id FROM Claims WHERE id = ?",
            (unique_claim_id,),
        ).fetchone()

        assert member_ids == {alpha_claim_id, alpha_spaced_claim_id}
        assert unique_claim_row["claim_cluster_id"] is None
    finally:
        db.close_connection()


def test_rebuild_claim_clusters_exact_preserves_postgres_returning_id_path() -> None:
    helper_rebuild_claim_clusters_exact = _load_helper("rebuild_claim_clusters_exact")
    assert helper_rebuild_claim_clusters_exact is not None

    class _InsertCursor:
        lastrowid = None

        def fetchone(self):
            return {"id": 17}

    class _NoopCursor:
        lastrowid = None

        def fetchone(self):
            return None

    fetch_calls: list[tuple[str, tuple[object, ...]]] = []
    execute_calls: list[tuple[str, tuple[object, ...]]] = []

    @contextmanager
    def _transaction():
        yield object()

    def _fetchall_with_connection(conn, sql, params=None):
        params_tuple = tuple(params or ())
        fetch_calls.append((sql, params_tuple))
        if len(fetch_calls) == 1:
            return []
        return [
            {"id": 1, "claim_text": "Alpha claim"},
            {"id": 2, "claim_text": " alpha   claim "},
        ]

    def _execute_with_connection(conn, sql, params=None):
        execute_calls.append((sql, tuple(params or ())))
        if "RETURNING id" in sql:
            return _InsertCursor()
        return _NoopCursor()

    fake_db = SimpleNamespace(
        backend_type=BackendType.POSTGRESQL,
        transaction=_transaction,
        _fetchall_with_connection=_fetchall_with_connection,
        _execute_with_connection=_execute_with_connection,
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:00Z",
    )

    result = helper_rebuild_claim_clusters_exact(fake_db, user_id="1", min_size=2)

    assert result == {"clusters_created": 1, "claims_assigned": 2}
    assert any(sql.endswith(" RETURNING id") for sql, _ in execute_calls)
    assert any(
        sql.startswith("UPDATE claim_clusters SET cluster_version = cluster_version + 1")
        for sql, _ in execute_calls
    )
