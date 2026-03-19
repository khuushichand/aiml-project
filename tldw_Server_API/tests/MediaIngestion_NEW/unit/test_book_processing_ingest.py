from __future__ import annotations

from contextlib import contextmanager

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Books import Book_Processing_Lib as books


@pytest.mark.unit
def test_ingest_text_file_uses_managed_media_database(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text_file = tmp_path / "sample.txt"
    text_file.write_text("Book body", encoding="utf-8")

    class _FakeDb:
        def __init__(self) -> None:
            self.closed = False

        def close_connection(self) -> None:
            self.closed = True

    fake_db = _FakeDb()
    managed_calls: list[dict[str, object]] = []
    add_calls: list[dict[str, object]] = []

    @contextmanager
    def _fake_managed_media_database(client_id, *, initialize=True, **kwargs):
        managed_calls.append(
            {
                "client_id": client_id,
                "initialize": initialize,
                "kwargs": kwargs,
            }
        )
        try:
            yield fake_db
        finally:
            fake_db.close_connection()

    def _fake_add_media_with_keywords(**kwargs):
        add_calls.append(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(
        books,
        "managed_media_database",
        _fake_managed_media_database,
        raising=False,
    )
    monkeypatch.setattr(
        books,
        "create_media_database",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("legacy raw factory should not be used")),
        raising=False,
    )
    monkeypatch.setattr(books, "add_media_with_keywords", _fake_add_media_with_keywords)

    result = books.ingest_text_file(
        str(text_file),
        title="Sample Book",
        author="Author Name",
        keywords="fiction,novel",
        base_dir=tmp_path,
    )

    assert "ingested successfully" in result
    assert fake_db.closed is True
    assert managed_calls == [
        {
            "client_id": "book_ingest",
            "initialize": False,
            "kwargs": {},
        }
    ]
    assert len(add_calls) == 1
    assert add_calls[0]["db_instance"] is fake_db
    assert add_calls[0]["title"] == "Sample Book"
    assert add_calls[0]["author"] == "Author Name"
    assert add_calls[0]["keywords"] == ["text_file", "epub_converted", "fiction", "novel"]
