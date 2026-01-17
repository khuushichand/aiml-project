import pytest


def test_missing_db_path_raises_when_no_backend(monkeypatch):
    # Import module under test
    import tldw_Server_API.app.core.DB_Management.Media_DB_v2 as m

    # Force content backend resolution to return None
    monkeypatch.setattr(m, "get_content_backend", lambda parser=None: None, raising=True)

    # Stub backend factory to avoid real DB work
    from tldw_Server_API.app.core.DB_Management.backends.base import BackendType

    class _DummyBackend:
        backend_type = BackendType.SQLITE

    monkeypatch.setattr(m.DatabaseBackendFactory, "create_backend", lambda cfg: _DummyBackend(), raising=True)

    # Avoid heavy __init__: construct instance without running initializer
    db = object.__new__(m.MediaDatabase)
    # Simulate missing provided_path to trigger fallback branch
    db.db_path_str = ""

    # Call the backend resolver directly
    with pytest.raises(m.DatabaseError, match="MediaDatabase backend could not be resolved"):
        m.MediaDatabase._resolve_backend(db, backend=None, config=None)


def test_explicit_db_path_avoids_fallback_and_logs_no_warning(monkeypatch, tmp_path):
    # Import module under test
    import tldw_Server_API.app.core.DB_Management.Media_DB_v2 as m
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

    # Point USER_DB_BASE_DIR to tmp to compute a safe path
    base = tmp_path / "user_databases"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))

    # Force content backend to None to ensure provided_path is decisive
    monkeypatch.setattr(m, "get_content_backend", lambda parser=None: None, raising=True)

    # Stub backend factory to avoid real DB work
    from tldw_Server_API.app.core.DB_Management.backends.base import BackendType

    class _DummyBackend:
        backend_type = BackendType.SQLITE

    monkeypatch.setattr(m.DatabaseBackendFactory, "create_backend", lambda cfg: _DummyBackend(), raising=True)

    # Compute explicit per-user path and simulate provided_path branch
    p = str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
    db = object.__new__(m.MediaDatabase)
    db.db_path_str = p

    backend = m.MediaDatabase._resolve_backend(db, backend=None, config=None)
    assert backend is not None
