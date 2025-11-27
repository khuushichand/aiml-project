from __future__ import annotations

from datetime import datetime

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def _make_media_db() -> MediaDatabase:
    return MediaDatabase(db_path=":memory:", client_id="tests-visual")


@pytest.mark.unit
def test_visual_documents_insert_list_and_soft_delete():
    db = _make_media_db()

    # Create a dummy media row
    media_id, _, _ = db.add_media_with_keywords(
        title="Visual Source",
        media_type="document",
        content="base content",
        keywords=[],
    )
    assert isinstance(media_id, int)

    # Insert a couple of visual documents
    uuid1 = db.insert_visual_document(
        media_id=media_id,
        caption="First figure",
        ocr_text="Figure 1: overview",
        tags="diagram,figure",
        page_number=1,
        frame_index=None,
        timestamp_seconds=None,
    )
    uuid2 = db.insert_visual_document(
        media_id=media_id,
        caption="Second figure",
        ocr_text="Figure 2: details",
        tags="diagram,figure",
        page_number=2,
        frame_index=None,
        timestamp_seconds=None,
    )

    assert uuid1 and uuid2 and uuid1 != uuid2

    docs = db.list_visual_documents_for_media(media_id)
    assert len(docs) == 2
    captions = {d["caption"] for d in docs}
    assert {"First figure", "Second figure"} == captions
    # Ensure soft-delete flag is not set initially
    assert all(d["deleted"] == 0 for d in docs)

    # Soft delete and verify they no longer appear by default
    db.soft_delete_visual_documents_for_media(media_id)
    docs_after = db.list_visual_documents_for_media(media_id)
    assert docs_after == []

    # But they remain in the table when include_deleted is True
    docs_all = db.list_visual_documents_for_media(media_id, include_deleted=True)
    assert len(docs_all) == 2
    assert all(d["deleted"] == 1 for d in docs_all)

