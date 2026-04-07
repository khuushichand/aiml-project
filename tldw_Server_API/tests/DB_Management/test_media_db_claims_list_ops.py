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
    "tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_list_ops"
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
    owner_user_id: int,
    visibility: str = "personal",
    team_id: int | None = None,
    org_id: int | None = None,
) -> int:
    media_id, _, _ = db.add_media_with_keywords(
        title=title,
        media_type="text",
        content=content,
        keywords=None,
        owner_user_id=owner_user_id,
        visibility=visibility,
    )
    if team_id is not None or org_id is not None:
        now = db._get_current_utc_timestamp_str()
        db.execute_query(
            "UPDATE Media SET team_id = ?, org_id = ?, version = version + 1, "
            "last_modified = ?, client_id = ? WHERE id = ?",
            (team_id, org_id, now, db.client_id, int(media_id)),
        )
    return int(media_id)


def _seed_claim(
    db: MediaDatabase,
    *,
    media_id: int,
    chunk_index: int,
    claim_text: str,
    review_status: str | None = None,
    reviewer_id: int | None = None,
    review_group: str | None = None,
    claim_cluster_id: int | None = None,
    deleted: bool = False,
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
                "review_status": review_status,
                "reviewer_id": reviewer_id,
                "review_group": review_group,
                "claim_cluster_id": claim_cluster_id,
            }
        ]
    )
    row = db.execute_query(
        "SELECT id FROM Claims WHERE media_id = ? ORDER BY id DESC LIMIT 1",
        (media_id,),
    ).fetchone()
    claim_id = int(row["id"])
    if (
        review_status is not None
        or reviewer_id is not None
        or review_group is not None
        or claim_cluster_id is not None
    ):
        now = db._get_current_utc_timestamp_str()
        db.execute_query(
            "UPDATE Claims SET review_status = ?, reviewer_id = ?, review_group = ?, "
            "claim_cluster_id = ?, version = version + 1, last_modified = ?, client_id = ? "
            "WHERE id = ?",
            (
                review_status,
                reviewer_id,
                review_group,
                claim_cluster_id,
                now,
                db.client_id,
                claim_id,
            ),
        )
    if deleted:
        db.update_claim(claim_id, deleted=True)
    return {"id": claim_id}


def test_claims_list_helper_rebinds_and_preserves_filters_pagination_and_ordering(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-list.db")
    try:
        assert db.list_claims.__func__ is _load_helper("list_claims")

        owned_media = _seed_media(
            db,
            title="Owned",
            content="alpha beta",
            owner_user_id=1,
            visibility="personal",
        )
        foreign_media = _seed_media(
            db,
            title="Foreign",
            content="gamma delta",
            owner_user_id=2,
            visibility="personal",
        )
        team_media = _seed_media(
            db,
            title="Team",
            content="team",
            owner_user_id=3,
            visibility="team",
            team_id=77,
        )
        org_media = _seed_media(
            db,
            title="Org",
            content="org",
            owner_user_id=4,
            visibility="org",
            org_id=88,
        )

        first = _seed_claim(
            db,
            media_id=owned_media,
            chunk_index=1,
            claim_text="owned-late",
            review_status="approved",
            reviewer_id=9,
            review_group="beta",
            claim_cluster_id=202,
        )
        second = _seed_claim(
            db,
            media_id=owned_media,
            chunk_index=0,
            claim_text="owned-early",
            review_status="approved",
            reviewer_id=9,
            review_group="beta",
            claim_cluster_id=202,
        )
        deleted = _seed_claim(
            db,
            media_id=owned_media,
            chunk_index=2,
            claim_text="owned-deleted",
            deleted=True,
        )
        foreign = _seed_claim(
            db,
            media_id=foreign_media,
            chunk_index=0,
            claim_text="foreign",
            review_status="pending",
            reviewer_id=42,
            review_group="alpha",
            claim_cluster_id=8,
        )
        team = _seed_claim(
            db,
            media_id=team_media,
            chunk_index=0,
            claim_text="team-claim",
        )
        org = _seed_claim(
            db,
            media_id=org_media,
            chunk_index=0,
            claim_text="org-claim",
        )

        default_rows = db.list_claims(limit="oops", offset=-7)
        owned_rows = db.list_claims(owner_user_id=1, include_deleted=True)
        review_rows = db.list_claims(
            review_status="approved",
            reviewer_id=9,
            review_group="beta",
            claim_cluster_id=202,
        )
        team_rows = db.list_claims(team_id=77)
        org_rows = db.list_claims(org_id=88)
        media_rows = db.list_claims(media_id=owned_media, include_deleted=True)

        assert [int(row["id"]) for row in default_rows] == [
            int(second["id"]),
            int(first["id"]),
            int(foreign["id"]),
            int(team["id"]),
            int(org["id"]),
        ]
        assert {int(row["id"]) for row in owned_rows} == {
            int(first["id"]),
            int(second["id"]),
            int(deleted["id"]),
        }
        assert [int(row["id"]) for row in review_rows] == [int(second["id"]), int(first["id"])]
        assert [int(row["id"]) for row in team_rows] == [int(team["id"])]
        assert [int(row["id"]) for row in org_rows] == [int(org["id"])]
        assert {int(row["id"]) for row in media_rows} == {
            int(first["id"]),
            int(second["id"]),
            int(deleted["id"]),
        }
    finally:
        db.close_connection()


def test_claims_list_helper_scope_filter_excludes_rows_outside_active_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = _make_db(tmp_path, "claims-list-scope.db")
    try:
        visible_media = _seed_media(
            db,
            title="Visible",
            content="visible",
            owner_user_id=2,
            visibility="personal",
        )
        hidden_media = _seed_media(
            db,
            title="Hidden",
            content="hidden",
            owner_user_id=1,
            visibility="personal",
        )
        visible = _seed_claim(db, media_id=visible_media, chunk_index=0, claim_text="visible")
        _hidden = _seed_claim(db, media_id=hidden_media, chunk_index=0, claim_text="hidden")

        scope = ScopeContext(
            user_id=2,
            org_ids=[],
            team_ids=[],
            active_org_id=None,
            active_team_id=None,
            is_admin=False,
            session_role=None,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_list_ops.get_scope",
            lambda: scope,
        )

        rows = db.list_claims()

        assert [int(row["id"]) for row in rows] == [int(visible["id"])]
    finally:
        db.close_connection()
