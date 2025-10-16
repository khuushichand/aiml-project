
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, List, Tuple
from unittest.mock import MagicMock

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.RAG.rag_service.analytics_db import AnalyticsDatabase
from tldw_Server_API.app.core.RAG.rag_service.analytics_system import UserFeedbackStore


class _StubConnection:
    def __init__(self) -> None:
        self.statements: List[Tuple[str, Any]] = []

    def execute(self, statement: str, params: Any = None) -> None:
        self.statements.append((statement, params))


class _StubChaChaDb:
    def __init__(self, backend_type: BackendType) -> None:
        self.backend_type = backend_type
        self._conn = _StubConnection()

    @contextmanager
    def transaction(self):  # type: ignore[override]
        yield self._conn

    @property
    def executed(self) -> List[Tuple[str, Any]]:
        return self._conn.statements


def test_user_feedback_schema_sqlite_executes_expected_statements() -> None:
    db = _StubChaChaDb(BackendType.SQLITE)
    UserFeedbackStore(db)
    statements = [stmt for stmt, _ in db.executed]
    assert len(statements) == 3
    assert any('helpful INTEGER' in stmt for stmt in statements)
    assert all('conversation_feedback' in stmt for stmt in statements)


def test_user_feedback_schema_postgres_uses_boolean_and_timestamp() -> None:
    db = _StubChaChaDb(BackendType.POSTGRESQL)
    UserFeedbackStore(db)
    statements = [stmt for stmt, _ in db.executed]
    assert len(statements) == 3
    assert any('helpful BOOLEAN' in stmt for stmt in statements)
    assert any('TIMESTAMPTZ' in stmt for stmt in statements)


def test_record_search_sqlite_writes_row(tmp_path: Path) -> None:
    db_path = tmp_path / 'analytics.sqlite'
    analytics = AnalyticsDatabase(str(db_path))
    try:
        analytics.record_search(
            {
                'query': 'backend coverage',
                'results_count': 3,
                'response_time_ms': 42,
                'cache_hit': False,
            }
        )
        conn = analytics.backend.connect()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT query_hash, results_count FROM search_analytics')
            row = cursor.fetchone()
            assert row is not None
            assert row[1] == 3
        finally:
            conn.close()
    finally:
        analytics.close()


def test_record_search_postgres_calls_backend_execute() -> None:
    analytics = AnalyticsDatabase.__new__(AnalyticsDatabase)
    analytics.backend_type = BackendType.POSTGRESQL
    analytics.backend = MagicMock()

    calls: List[Tuple[str, Any]] = []

    def transaction_factory():
        @contextmanager
        def _ctx():
            yield object()
        return _ctx()

    analytics.transaction = transaction_factory  # type: ignore[assignment]

    def record_execute(_conn: Any, query: str, params: Any = None):
        calls.append((query, params))
        return MagicMock()

    analytics._execute = MagicMock(side_effect=record_execute)  # type: ignore[attr-defined]

    analytics.record_search(
        {
            'query': 'backend coverage',
            'results_count': 3,
            'response_time_ms': 42,
            'cache_hit': True,
        }
    )

    analytics._execute.assert_called_once()
    inserted_query = calls[0][0]
    assert 'INSERT INTO search_analytics' in inserted_query
    assert '%s' in inserted_query
