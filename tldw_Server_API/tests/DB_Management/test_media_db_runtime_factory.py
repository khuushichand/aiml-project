import configparser
from contextlib import contextmanager

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, QueryResult
from tldw_Server_API.app.core.DB_Management.media_db.runtime import factory as runtime_factory


def _runtime_config(
    *,
    postgres_content_mode: bool,
    backend_loader=None,
    default_db_path: str = "/tmp/media.db",
):
    cfg = configparser.ConfigParser()
    return runtime_factory.MediaDbRuntimeConfig(
        default_db_path=default_db_path,
        default_config=cfg,
        postgres_content_mode=postgres_content_mode,
        backend_loader=backend_loader or (lambda: None),
    )


def test_create_media_database_sqlite_uses_default_path_and_no_backend(monkeypatch):
    class StubMediaDatabase:
        calls = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.__class__.calls.append(kwargs)

    runtime = _runtime_config(postgres_content_mode=False)
    monkeypatch.setattr(runtime_factory, "_load_media_database_cls", lambda: StubMediaDatabase)

    db = runtime_factory.create_media_database(
        "client-1",
        runtime=runtime,
    )

    assert isinstance(db, StubMediaDatabase)
    assert StubMediaDatabase.calls == [
        {
            "db_path": "/tmp/media.db",
            "client_id": "client-1",
            "backend": None,
            "config": runtime.default_config,
        }
    ]


def test_create_media_database_postgres_requires_backend():
    runtime = _runtime_config(postgres_content_mode=True, backend_loader=lambda: None)

    with pytest.raises(RuntimeError) as excinfo:
        runtime_factory.create_media_database(
            "client-2",
            runtime=runtime,
        )

    assert "PostgreSQL content backend configured" in str(excinfo.value)


def test_validate_postgres_content_backend_uses_factory_validator(monkeypatch):
    expected_version = 7

    class StubBackend:
        backend_type = BackendType.POSTGRESQL

        def __init__(self):
            self.queries = []

        @contextmanager
        def transaction(self):
            yield object()

        def execute(self, query, params=None, connection=None):
            self.queries.append(query)
            if "schema_version" in query:
                return QueryResult(rows=[{"version": expected_version}], rowcount=1)
            return QueryResult(rows=[{"ok": 1}], rowcount=1)

    class StubMediaDatabase:
        _CURRENT_SCHEMA_VERSION = expected_version
        instances = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.checked_policies = []
            self.closed = False
            self.__class__.instances.append(self)

        def _postgres_policy_exists(self, conn, table, policy):
            self.checked_policies.append((table, policy))
            return True

        def close_connection(self):
            self.closed = True

    runtime = _runtime_config(
        postgres_content_mode=True,
        backend_loader=lambda: None,
    )
    stub_backend = StubBackend()
    monkeypatch.setattr(runtime_factory, "_load_media_database_cls", lambda: StubMediaDatabase)

    runtime_factory.validate_postgres_content_backend(
        runtime=runtime,
        get_content_backend_instance=lambda: stub_backend,
    )

    assert any("schema_version" in query for query in stub_backend.queries)
    assert StubMediaDatabase.instances
    assert StubMediaDatabase.instances[-1].checked_policies
    assert StubMediaDatabase.instances[-1].closed is True

