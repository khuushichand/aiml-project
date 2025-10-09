from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Sequence
from unittest.mock import MagicMock, call

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


class _CursorStub:
    """Minimal stub matching the subset of cursor API used by CharactersRAGDB."""

    def __init__(self, rows: Sequence[Dict[str, Any]]):
        self._rows = list(rows)

    def fetchall(self) -> List[Dict[str, Any]]:
        return list(self._rows)


def _make_postgres_db() -> CharactersRAGDB:
    db = CharactersRAGDB.__new__(CharactersRAGDB)
    db.backend_type = BackendType.POSTGRESQL
    db.backend = MagicMock()
    db._CHARACTER_CARD_JSON_FIELDS = []
    return db


def test_rebuild_full_text_indexes_postgres_calls_backend():
    db = _make_postgres_db()
    db._FTS_CONFIG = [
        ("character_cards_fts", "character_cards", ["name"]),
        ("messages_fts", "messages", ["content"]),
    ]

    db.rebuild_full_text_indexes()

    expected_calls = [
        call(
            table_name="character_cards_fts",
            source_table="character_cards",
            columns=["name"],
            connection=None,
        ),
        call(
            table_name="messages_fts",
            source_table="messages",
            columns=["content"],
            connection=None,
        ),
    ]

    assert db.backend.create_fts_table.call_args_list == expected_calls


def test_rebuild_full_text_indexes_sqlite_executes_rebuild():
    db = CharactersRAGDB.__new__(CharactersRAGDB)
    db.backend_type = BackendType.SQLITE
    db._FTS_CONFIG = [
        ("keywords_fts", "keywords", []),
        ("notes_fts", "notes", []),
    ]

    executed: List[str] = []

    class _Conn:
        def execute(self, sql: str, *_args: Any) -> None:
            executed.append(sql)

    @contextmanager
    def fake_transaction() -> Iterable[_Conn]:
        yield _Conn()

    db.transaction = fake_transaction  # type: ignore[assignment]

    db.rebuild_full_text_indexes()

    assert executed == [
        "INSERT INTO keywords_fts(keywords_fts) VALUES('rebuild')",
        "INSERT INTO notes_fts(notes_fts) VALUES('rebuild')",
    ]


def test_search_character_cards_postgres_uses_tsquery(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _make_postgres_db()
    rows = [{"id": 1, "rank": 0.42}]
    db.execute_query = MagicMock(return_value=_CursorStub(rows))
    db._deserialize_row_fields = lambda row, _fields: row  # type: ignore[assignment]

    result = db.search_character_cards("dragon rider", limit=5)

    assert result == rows
    assert db.execute_query.call_count == 1
    sql, params = db.execute_query.call_args[0]
    assert "ts_rank" in sql and "to_tsquery('english', ?)" in sql
    assert params == ("dragon & rider", "dragon & rider", 5)


def test_list_flashcards_postgres_translates_fts(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _make_postgres_db()
    db._get_current_utc_timestamp_iso = lambda: "2025-01-01T00:00:00Z"  # type: ignore[assignment]
    db.execute_query = MagicMock(return_value=_CursorStub([]))

    result = db.list_flashcards(q="alchemy", limit=10, offset=0)

    assert result == []
    sql, params = db.execute_query.call_args[0]
    assert "flashcards_fts_tsv @@ to_tsquery('english', ?)" in sql
    assert "alchemy" in params
