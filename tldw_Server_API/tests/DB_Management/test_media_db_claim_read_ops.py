from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.scope_context import ScopeContext


pytestmark = pytest.mark.unit


_RUNTIME_MODULE_NAME = (
    "tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_read_ops"
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


def _seed_media(
    db: MediaDatabase,
    *,
    title: str,
    content: str,
    owner_user_id: int | None = None,
    visibility: str | None = None,
) -> int:
    kwargs: dict[str, object] = {}
    if owner_user_id is not None:
        kwargs["owner_user_id"] = owner_user_id
    if visibility is not None:
        kwargs["visibility"] = visibility
    media_id, _, _ = db.add_media_with_keywords(
        title=title,
        media_type="text",
        content=content,
        keywords=None,
        **kwargs,
    )
    return int(media_id)


def _seed_claim(
    db: MediaDatabase,
    *,
    media_id: int,
    chunk_index: int,
    claim_text: str,
) -> dict[str, object]:
    chunk_hash = hashlib.sha256(f"{media_id}:{chunk_index}:{claim_text}".encode("utf-8")).hexdigest()
    db.upsert_claims(
        [
            {
                "media_id": media_id,
                "chunk_index": chunk_index,
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
        "SELECT id, uuid FROM Claims WHERE media_id = ? AND deleted = 0 ORDER BY id DESC LIMIT 1",
        (media_id,),
    ).fetchone()
    return {"id": int(row["id"]), "uuid": str(row["uuid"])}


def test_claim_direct_read_helpers_rebind_and_preserve_order_deleted_scope_and_uuid_lookup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = _make_db(tmp_path, "claims-read.db")
    try:
        assert db.get_claims_by_media.__func__ is _load_helper("get_claims_by_media")
        assert db.get_claim_with_media.__func__ is _load_helper("get_claim_with_media")
        assert db.get_claims_by_uuid.__func__ is _load_helper("get_claims_by_uuid")

        media_id = _seed_media(
            db,
            title="Owned Doc",
            content="Alpha. Beta.",
            owner_user_id=1,
            visibility="personal",
        )
        first = _seed_claim(db, media_id=media_id, chunk_index=1, claim_text="Later chunk")
        second = _seed_claim(db, media_id=media_id, chunk_index=0, claim_text="Earlier chunk")
        deleted = _seed_claim(db, media_id=media_id, chunk_index=2, claim_text="Deleted row")
        db.update_claim(deleted["id"], deleted=True)

        ordered_rows = db.get_claims_by_media(media_id, limit=10, offset=0)
        visible_row = db.get_claim_with_media(second["id"], include_deleted=False)
        deleted_hidden = db.get_claim_with_media(deleted["id"], include_deleted=False)
        deleted_visible = db.get_claim_with_media(deleted["id"], include_deleted=True)

        denied_scope = ScopeContext(
            user_id=2,
            org_ids=[],
            team_ids=[],
            active_org_id=None,
            active_team_id=None,
            is_admin=False,
            session_role=None,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_read_ops.get_scope",
            lambda: denied_scope,
        )
        denied_visible = db.get_claim_with_media(second["id"], include_deleted=False)

        uuid_rows = db.get_claims_by_uuid([str(first["uuid"]), str(second["uuid"])])

        assert [int(row["id"]) for row in ordered_rows] == [int(second["id"]), int(first["id"])]
        assert visible_row is not None
        assert int(visible_row["id"]) == int(second["id"])
        assert deleted_hidden is None
        assert deleted_visible is not None
        assert int(deleted_visible["id"]) == int(deleted["id"])
        assert denied_visible is None
        assert {str(row["uuid"]) for row in uuid_rows} == {str(first["uuid"]), str(second["uuid"])}
        assert db.get_claims_by_uuid([]) == []
    finally:
        db.close_connection()
