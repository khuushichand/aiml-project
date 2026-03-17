"""Unit tests for CloneService — media ID mapping, deep copy of chunks/transcripts."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tldw_Server_API.app.core.Sharing.clone_service import CloneService

pytestmark = pytest.mark.unit


def _make_service(
    *,
    src_media_items: dict | None = None,
    src_transcripts: list | None = None,
    src_workspace: dict | None = None,
    src_sources: list | None = None,
    src_notes: list | None = None,
    src_artifacts: list | None = None,
    add_result: tuple = (42, "uuid-42", "ok"),
) -> tuple[CloneService, MagicMock, MagicMock, MagicMock, MagicMock]:
    src_chacha = MagicMock()
    src_media = MagicMock()
    tgt_chacha = MagicMock()
    tgt_media = MagicMock()

    src_chacha.get_workspace.return_value = src_workspace or {
        "name": "Test WS",
        "description": "desc",
        "workspace_type": "research",
    }
    src_chacha.list_workspace_sources.return_value = src_sources if src_sources is not None else []
    src_chacha.list_workspace_notes.return_value = src_notes or []
    src_chacha.list_workspace_artifacts.return_value = src_artifacts or []

    src_media.get_media_by_id.return_value = src_media_items

    tgt_media.add_media_with_keywords.return_value = add_result

    svc = CloneService(
        source_chacha_db=src_chacha,
        source_media_db=src_media,
        target_chacha_db=tgt_chacha,
        target_media_db=tgt_media,
    )
    return svc, src_chacha, src_media, tgt_chacha, tgt_media


def test_clone_empty_workspace():
    svc, _, _, tgt_chacha, _ = _make_service()
    result = svc.clone_workspace("ws-1", new_name="My Clone")
    assert result["name"] == "My Clone"
    assert result["sources_copied"] == 0
    tgt_chacha.create_workspace.assert_called_once()


def test_clone_copies_media_with_db_generated_id():
    """_copy_media_item should return the DB-generated int ID, not a UUID."""
    media_row = {
        "url": "https://example.com/video",
        "title": "Test Video",
        "type": "video",
        "content": "hello world",
        "keywords": "tag1, tag2",
        "prompt": "",
        "transcription_model": "whisper",
        "author": "Author",
        "ingestion_date": "2026-01-01",
    }
    svc, _, _, _, tgt_media = _make_service(
        src_media_items=media_row,
        add_result=(99, "uuid-99", "inserted"),
        src_sources=[{"id": "s1", "media_id": "7", "source_type": "media", "title": "T"}],
    )

    with patch(
        "tldw_Server_API.app.core.Sharing.clone_service.get_media_transcripts",
        return_value=[],
    ):
        result = svc.clone_workspace("ws-1")

    # The media_id_map should map old -> new using the DB-generated ID
    assert result["media_id_map"]["7"] == "99"
    assert result["sources_copied"] == 1


def test_copy_media_passes_keywords_as_list():
    media_row = {
        "url": "",
        "title": "T",
        "type": "text",
        "content": "c",
        "keywords": "alpha, beta, gamma",
        "prompt": "",
        "transcription_model": "",
        "author": "",
        "ingestion_date": "",
    }
    svc, _, _, _, tgt_media = _make_service(
        src_media_items=media_row,
        add_result=(1, "u1", "ok"),
    )

    with patch(
        "tldw_Server_API.app.core.Sharing.clone_service.get_media_transcripts",
        return_value=[],
    ):
        new_id = svc._copy_media_item("10")

    assert new_id == "1"
    call_kwargs = tgt_media.add_media_with_keywords.call_args
    kw = call_kwargs.kwargs if call_kwargs.kwargs else {}
    if not kw:
        # positional call — keywords is the 5th keyword arg
        kw = call_kwargs[1] if len(call_kwargs) > 1 else {}
    keywords_val = kw.get("keywords")
    assert isinstance(keywords_val, list)
    assert set(keywords_val) == {"alpha", "beta", "gamma"}


def test_copy_media_deep_copies_transcripts():
    media_row = {
        "url": "",
        "title": "T",
        "type": "text",
        "content": "c",
        "keywords": "",
        "prompt": "",
        "transcription_model": "",
        "author": "",
        "ingestion_date": "",
    }
    transcripts = [
        {"transcription": "hello world", "whisper_model": "base", "created_at": "2026-01-01"},
    ]
    svc, _, _, _, tgt_media = _make_service(
        src_media_items=media_row,
        add_result=(10, "u10", "ok"),
    )

    mock_upsert = MagicMock()
    with (
        patch(
            "tldw_Server_API.app.core.Sharing.clone_service.get_media_transcripts",
            return_value=transcripts,
        ),
        patch(
            "tldw_Server_API.app.core.Sharing.clone_service.upsert_transcript",
            mock_upsert,
        ),
    ):
        new_id = svc._copy_media_item("30")

    assert new_id == "10"
    mock_upsert.assert_called_once_with(
        tgt_media,
        10,
        transcription="hello world",
        whisper_model="base",
        created_at="2026-01-01",
    )


def test_copy_media_returns_none_for_missing_media():
    svc, _, _, _, _ = _make_service(src_media_items=None)
    result = svc._copy_media_item("999")
    assert result is None


def test_clone_skips_source_when_media_copy_fails():
    """Sources with failed media copies should be skipped to avoid dangling references."""
    svc, _, _, tgt_chacha, _ = _make_service(
        src_media_items=None,  # get_media_by_id returns None -> copy fails
        src_sources=[{"id": "s1", "media_id": "7", "source_type": "media", "title": "T"}],
    )

    with patch(
        "tldw_Server_API.app.core.Sharing.clone_service.get_media_transcripts",
        return_value=[],
    ):
        result = svc.clone_workspace("ws-1")

    assert result["sources_copied"] == 1
    # add_workspace_source should NOT have been called since the media copy failed
    tgt_chacha.add_workspace_source.assert_not_called()


def test_clone_workspace_not_found():
    src_chacha = MagicMock()
    src_chacha.get_workspace.return_value = None
    svc = CloneService(
        source_chacha_db=src_chacha,
        source_media_db=MagicMock(),
        target_chacha_db=MagicMock(),
        target_media_db=MagicMock(),
    )
    with pytest.raises(ValueError, match="not found"):
        svc.clone_workspace("nonexistent")


def test_clone_default_name_appends_clone_suffix():
    svc, _, _, _, _ = _make_service(
        src_workspace={"name": "Research", "description": "", "workspace_type": "research"}
    )
    result = svc.clone_workspace("ws-1")
    assert result["name"] == "Research (Clone)"


def test_clone_progress_callback():
    stages: list[tuple[str, float]] = []
    svc, _, _, _, _ = _make_service()
    svc.clone_workspace("ws-1", on_progress=lambda s, p: stages.append((s, p)))
    stage_names = [s for s, _ in stages]
    assert "loading_source" in stage_names
    assert "complete" in stage_names
    assert stages[-1] == ("complete", 1.0)
