from __future__ import annotations

from datetime import datetime
import importlib
from unittest.mock import MagicMock

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase


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


@pytest.mark.unit
def test_insert_visual_document_helper_path():
    helper_module = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.visual_document_ops"
    )

    db = MagicMock()
    conn = object()
    db.get_connection.return_value = conn
    db.client_id = "tests-visual"
    db._execute_with_connection = MagicMock()
    db._log_sync_event = MagicMock()

    result = helper_module.insert_visual_document(
        db,
        11,
        caption="Detected figure",
        ocr_text="Figure 1",
        page_number=1,
    )

    assert isinstance(result, str)
    db._execute_with_connection.assert_called_once()
    db._log_sync_event.assert_called_once()


@pytest.mark.unit
def test_insert_visual_document_logs_warning_when_sync_event_fails(monkeypatch):
    helper_module = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.visual_document_ops"
    )

    warning_calls = []
    monkeypatch.setattr(
        helper_module.logger,
        "warning",
        lambda message, *args: warning_calls.append((message, args)),
    )

    db = MagicMock()
    conn = object()
    db.get_connection.return_value = conn
    db.client_id = "tests-visual"
    db._execute_with_connection = MagicMock()
    db._log_sync_event.side_effect = RuntimeError("sync write unavailable")

    result = helper_module.insert_visual_document(
        db,
        11,
        caption="Detected figure",
        ocr_text="Figure 1",
        page_number=1,
    )

    assert isinstance(result, str)
    db._execute_with_connection.assert_called_once()
    db._log_sync_event.assert_called_once()
    assert len(warning_calls) == 1
    message, args = warning_calls[0]
    assert "Failed to record VisualDocuments sync event" in message
    assert args[0] == 11
    assert args[1] == "create"
    assert args[2] == result


@pytest.mark.unit
def test_list_visual_documents_helper_path():
    helper_module = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.visual_document_ops"
    )

    db = MagicMock()
    conn = object()
    db.get_connection.return_value = conn
    db._fetchall_with_connection.return_value = [{"id": 1}]

    result = helper_module.list_visual_documents_for_media(
        db,
        11,
        include_deleted=True,
    )

    assert result == [{"id": 1}]
    db._fetchall_with_connection.assert_called_once()
    _conn, sql, params = db._fetchall_with_connection.call_args.args
    assert _conn is conn
    assert "SELECT * FROM VisualDocuments" in sql
    assert params == {"media_id": 11}


@pytest.mark.parametrize("hard_delete", [False, True])
@pytest.mark.unit
def test_soft_delete_visual_documents_logs_warning_when_sync_event_fails(
    monkeypatch,
    hard_delete: bool,
):
    helper_module = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.visual_document_ops"
    )

    warning_calls = []
    monkeypatch.setattr(
        helper_module.logger,
        "warning",
        lambda message, *args: warning_calls.append((message, args)),
    )

    db = MagicMock()
    conn = object()
    db.get_connection.return_value = conn
    db._fetchall_with_connection.return_value = [{"uuid": "visual-1", "version": 2}]
    db._execute_with_connection = MagicMock()
    db._log_sync_event.side_effect = RuntimeError("sync write unavailable")

    helper_module.soft_delete_visual_documents_for_media(db, 11, hard_delete=hard_delete)

    assert db._log_sync_event.call_count == 1
    assert len(warning_calls) == 1
    message, args = warning_calls[0]
    assert "Failed to record VisualDocuments sync event" in message
    assert args[0] == 11
    assert args[1] == "delete"
    assert args[2] == ("media:11" if hard_delete else "visual-1")


@pytest.mark.unit
def test_soft_delete_visual_documents_helper_path():
    helper_module = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.visual_document_ops"
    )

    db = MagicMock()
    conn = object()
    db.get_connection.return_value = conn
    db._fetchall_with_connection.return_value = [{"uuid": "visual-1", "version": 2}]
    db._execute_with_connection = MagicMock()
    db._log_sync_event = MagicMock()

    helper_module.soft_delete_visual_documents_for_media(db, 11)
    helper_module.soft_delete_visual_documents_for_media(db, 11, hard_delete=True)

    assert db._fetchall_with_connection.call_count == 1
    assert db._execute_with_connection.call_count == 2
    assert db._log_sync_event.call_count == 2
