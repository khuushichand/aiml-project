
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, List, Tuple

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management import migration_tools


class _StubPool:
    def close_all(self) -> None:
        pass


class _StubBackend:
    def __init__(self) -> None:
        self.executed: List[str] = []
        self.executed_many: List[Tuple[str, List[Tuple[Any, ...]]]] = []

    def transaction(self):
        class _Ctx:
            def __init__(self, backend: '_StubBackend') -> None:
                self.backend = backend

            def __enter__(self):
                return self.backend

            def __exit__(self, exc_type, exc, tb) -> None:
                return False

        return _Ctx(self)

    def execute(self, sql: str, params: Any = None, connection: Any = None):
        self.executed.append(sql)
        return None

    def execute_many(self, sql: str, params_list: List[Tuple[Any, ...]], connection: Any = None):
        self.executed_many.append((sql, params_list))
        return None

    def get_pool(self) -> _StubPool:
        return _StubPool()


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db_path = tmp_path / 'source.db'
    conn = sqlite3.connect(str(db_path))
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('CREATE TABLE parent (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)')
    conn.execute('CREATE TABLE child (id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER NOT NULL, '
                 'FOREIGN KEY(parent_id) REFERENCES parent(id))')
    conn.executemany('INSERT INTO parent (name) VALUES (?)', [('p1',), ('p2',)])
    conn.executemany('INSERT INTO child (parent_id) VALUES (?)', [(1,), (2,)])
    conn.commit()
    conn.close()
    return db_path


def test_migrate_sqlite_to_postgres_uses_backend(monkeypatch: pytest.MonkeyPatch, sqlite_db: Path) -> None:
    stub_backend = _StubBackend()

    def fake_create_backend(config: DatabaseConfig) -> _StubBackend:
        return stub_backend

    monkeypatch.setattr(migration_tools.DatabaseBackendFactory, 'create_backend', fake_create_backend)

    config = DatabaseConfig(backend_type=BackendType.POSTGRESQL)
    migration_tools.migrate_sqlite_to_postgres(sqlite_db, config, batch_size=10, label='test')

    delete_statements = [sql for sql in stub_backend.executed if sql.startswith('DELETE FROM')]
    assert delete_statements == ['DELETE FROM child', 'DELETE FROM parent']

    inserted_tables = [call[0].split()[2] for call in stub_backend.executed_many]
    assert inserted_tables == ['parent', 'child']

    parent_rows = stub_backend.executed_many[0][1]
    assert parent_rows == [(1, 'p1'), (2, 'p2')]
    child_rows = stub_backend.executed_many[1][1]
    assert child_rows == [(1, 1), (2, 2)]

    sequence_updates = [sql for sql in stub_backend.executed if sql.startswith('SELECT setval')]
    assert any('parent' in sql for sql in sequence_updates)
    assert any('child' in sql for sql in sequence_updates)
