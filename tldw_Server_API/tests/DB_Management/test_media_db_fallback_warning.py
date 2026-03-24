import pytest


def test_missing_db_path_raises_when_no_backend(monkeypatch):
    from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
    from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError
    from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        backend_resolution as backend_resolution_module,
    )

    monkeypatch.setattr(backend_resolution_module, "get_content_backend", lambda parser=None: None, raising=True)

    class _DummyBackend:
        backend_type = BackendType.SQLITE

    monkeypatch.setattr(
        backend_resolution_module.DatabaseBackendFactory,
        "create_backend",
        lambda cfg: _DummyBackend(),
        raising=True,
    )

    db = object.__new__(MediaDatabase)
    db.db_path_str = ""

    with pytest.raises(DatabaseError, match="MediaDatabase backend could not be resolved"):
        MediaDatabase._resolve_backend(db, backend=None, config=None)


def test_explicit_db_path_avoids_fallback_and_logs_no_warning(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        backend_resolution as backend_resolution_module,
    )

    base = tmp_path / "user_databases"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))

    monkeypatch.setattr(backend_resolution_module, "get_content_backend", lambda parser=None: None, raising=True)

    class _DummyBackend:
        backend_type = BackendType.SQLITE

    monkeypatch.setattr(
        backend_resolution_module.DatabaseBackendFactory,
        "create_backend",
        lambda cfg: _DummyBackend(),
        raising=True,
    )

    p = str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
    db = object.__new__(MediaDatabase)
    db.db_path_str = p

    backend = MediaDatabase._resolve_backend(db, backend=None, config=None)
    assert backend is not None
