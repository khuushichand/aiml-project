from __future__ import annotations

import pytest

from tldw_Server_API.app.services import document_processing_service as dps


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_documents_store_in_db_uses_media_repository_api(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_path = tmp_path / "document.txt"
    document_path.write_text("Alpha document body", encoding="utf-8")

    class _FakeDb:
        def __init__(self) -> None:
            self.closed = False

        def close_connection(self) -> None:
            self.closed = True

    class _FakeRepo:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def add_media_with_keywords(self, **kwargs):
            self.calls.append(kwargs)
            return 42, "doc-repo-uuid", "stored"

    fake_db = _FakeDb()
    fake_repo = _FakeRepo()
    fake_chunks = [{"text": "Alpha document body", "chunk_type": "text"}]

    monkeypatch.setattr(dps, "_ensure_placeholder_enabled", lambda: None)
    monkeypatch.setattr(dps, "create_media_database", lambda **kwargs: fake_db)
    monkeypatch.setattr(dps, "get_user_media_db_path", lambda _user_id: str(tmp_path / "media.db"))
    monkeypatch.setattr(dps, "build_plaintext_chunks", lambda *args, **kwargs: fake_chunks)
    monkeypatch.setattr(dps, "get_media_repository", lambda db: fake_repo, raising=False)

    result = await dps.process_documents(
        doc_urls=None,
        doc_files=[str(document_path)],
        api_name=None,
        api_key=None,
        custom_prompt_input=None,
        system_prompt_input=None,
        use_cookies=False,
        cookies=None,
        keep_original=True,
        custom_keywords=["alpha", "beta"],
        chunk_method="sentences",
        max_chunk_size=256,
        chunk_overlap=0,
        use_adaptive_chunking=False,
        use_multi_level_chunking=False,
        chunk_language="en",
        store_in_db=True,
        overwrite_existing=False,
        custom_title="Stored doc",
    )

    assert result["status"] == "success"
    assert result["results"][0]["db_id"] == 42
    assert fake_db.closed is True
    assert fake_repo.calls == [
        {
            "url": str(document_path),
            "title": "Stored doc",
            "media_type": "document",
            "content": "Alpha document body",
            "keywords": ["alpha", "beta"],
            "prompt": None,
            "analysis_content": "",
            "safe_metadata": '{"title": "Stored doc", "source": "document", "url": "'
            + str(document_path)
            + '"}',
            "transcription_model": "document-import",
            "author": None,
            "ingestion_date": None,
            "overwrite": False,
            "chunks": fake_chunks,
        }
    ]
