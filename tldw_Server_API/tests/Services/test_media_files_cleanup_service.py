from __future__ import annotations

import contextlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.services import media_files_cleanup_service as cleanup


pytestmark = pytest.mark.unit


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows
        self.queries: list[str] = []

    def execute(self, query: str):
        self.queries.append(query)
        return _FakeCursor(self._rows)


class _FakeCleanupDb:
    def __init__(self, rows):
        self._connection = _FakeConnection(rows)

    def get_connection(self):
        return self._connection


def test_collect_known_storage_paths_uses_managed_media_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db_path = tmp_path / "media.db"
    db_path.write_text("")
    fake_db = _FakeCleanupDb(
        rows=[
            ("1/media/11/file-one.txt",),
            {"storage_path": "1/media/12/file-two.txt"},
        ]
    )
    captured = {}

    @contextlib.contextmanager
    def _fake_managed_media_database(client_id, **kwargs):
        captured["client_id"] = client_id
        captured.update(kwargs)
        yield fake_db

    monkeypatch.setattr(
        cleanup.DatabasePaths,
        "get_media_db_path",
        lambda user_id: str(db_path),
    )
    monkeypatch.setattr(
        cleanup,
        "MediaDatabase",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("media_files_cleanup should not construct MediaDatabase directly")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        cleanup,
        "managed_media_database",
        _fake_managed_media_database,
        raising=False,
    )

    result = cleanup._collect_known_storage_paths(77)

    assert result == {
        "1/media/11/file-one.txt",
        "1/media/12/file-two.txt",
    }
    assert captured == {
        "client_id": "cleanup_service",
        "db_path": str(db_path),
        "initialize": False,
    }
    assert fake_db.get_connection().queries == [
        "SELECT storage_path FROM MediaFiles WHERE storage_path IS NOT NULL"
    ]
