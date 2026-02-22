import pytest

from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


pytestmark = pytest.mark.integration


def test_prompt_studio_pool_returns_connections(pg_database_config: DatabaseConfig, tmp_path):
    pg_database_config.pool_size = 1
    pg_database_config.max_overflow = 0
    backend = DatabaseBackendFactory.create_backend(pg_database_config)
    db = PromptStudioDatabase(
        db_path=str(tmp_path / "prompt_studio_pool.sqlite"),
        client_id="pool-ps",
        backend=backend,
    )

    pool = backend.get_pool()
    counts = {"get": 0, "return": 0}
    orig_get = pool.get_connection
    orig_return = pool.return_connection

    def tracked_get_connection():
        counts["get"] += 1
        return orig_get()

    def tracked_return_connection(conn):
        counts["return"] += 1
        return orig_return(conn)

    try:
        # Ensure any init-time connection is cleared before tracking.
        try:
            db.close_connection()
        except Exception:
            _ = None

        pool.get_connection = tracked_get_connection  # type: ignore[assignment]
        pool.return_connection = tracked_return_connection  # type: ignore[assignment]

        for _ in range(5):
            db.get_connection()
            db.close_connection()

        assert counts["get"] == 5
        assert counts["return"] == 5
    finally:
        try:
            pool.get_connection = orig_get  # type: ignore[assignment]
            pool.return_connection = orig_return  # type: ignore[assignment]
        except Exception:
            _ = None
        try:
            db.close()
        except Exception:
            _ = None
        try:
            backend.get_pool().close_all()
        except Exception:
            _ = None
