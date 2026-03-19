from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from tldw_Server_API.app.services import audiobook_jobs_worker


pytestmark = pytest.mark.unit


def test_load_source_text_uses_managed_media_database_for_media_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    events = []

    class _FakeDb:
        def get_media_by_id(self, media_id: int):
            events.append(("get_media_by_id", media_id))
            return {
                "content": "Chapter one. Chapter two.",
                "title": "DB Title",
                "author": "DB Author",
            }

    @contextlib.contextmanager
    def _fake_managed_media_database(client_id, **kwargs):
        events.append(("open", client_id, kwargs))
        yield _FakeDb()

    monkeypatch.setattr(
        audiobook_jobs_worker.DatabasePaths,
        "get_media_db_path",
        lambda user_id: tmp_path / f"user-{user_id}.db",
    )
    monkeypatch.setattr(
        audiobook_jobs_worker,
        "MediaDatabase",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("audiobook_jobs_worker should not construct MediaDatabase directly")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        audiobook_jobs_worker,
        "managed_media_database",
        _fake_managed_media_database,
        raising=False,
    )

    text, metadata, tag_result = audiobook_jobs_worker._load_source_text(
        {"input_type": "txt", "media_id": "9"},
        user_id=7,
    )

    assert text == "Chapter one. Chapter two."
    assert metadata["title"] == "DB Title"
    assert metadata["author"] == "DB Author"
    assert tag_result.clean_text == "Chapter one. Chapter two."
    assert events == [
        (
            "open",
            "audiobook_worker",
            {
                "db_path": str(tmp_path / "user-7.db"),
                "initialize": False,
            },
        ),
        ("get_media_by_id", 9),
    ]
