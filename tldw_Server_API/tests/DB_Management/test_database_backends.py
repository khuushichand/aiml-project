"""
Basic tests for database backend abstraction layer.

These tests verify that the backend abstraction works correctly
and that both SQLite and PostgreSQL backends implement the interface properly.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from tldw_Server_API.app.core.DB_Management.backends.base import (
    DatabaseBackend,
    DatabaseConfig,
    BackendType,
    BackendFeatures,
    FTSQuery,
    DatabaseError
)
from tldw_Server_API.app.core.DB_Management.backends.sqlite_backend import SQLiteBackend
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.backends.factory import BackendFactory


class TestDatabaseBackends:
    """Test suite for database backend implementations."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        try:
            os.unlink(temp_path)
        except:
            pass

    @pytest.fixture
    def sqlite_config(self, temp_db_path):
        """Create SQLite configuration."""
        return DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=temp_db_path,
            client_id="test_client"
        )

    def test_sqlite_backend_creation(self, sqlite_config):
        """Test that SQLite backend can be created."""
        backend = SQLiteBackend(sqlite_config)
        assert backend is not None
        assert backend.backend_type == BackendType.SQLITE

    def test_sqlite_backend_features(self, sqlite_config):
        """Test that SQLite backend reports correct features."""
        backend = SQLiteBackend(sqlite_config)
        features = backend.features

        assert features.full_text_search == True  # SQLite has FTS5
        assert features.json_support == True  # SQLite has JSON1
        assert features.window_functions == True  # Modern SQLite has window functions

    def test_sqlite_backend_connection(self, sqlite_config):
        """Test that SQLite backend can connect to database."""
        backend = SQLiteBackend(sqlite_config)

        # Test connection
        conn = backend.connect()
        assert conn is not None

        # Test that we can execute a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1

        conn.close()

    def test_sqlite_backend_schema_creation(self, sqlite_config):
        """Test that SQLite backend can create schema via create_tables."""
        backend = SQLiteBackend(sqlite_config)

        # Create a minimal test schema using the backend API
        backend.create_tables("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)")

        # Verify the test table exists
        conn = backend.connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        result = cursor.fetchone()
        assert result is not None
        conn.close()

    def test_backend_factory_sqlite(self, temp_db_path):
        """Test that factory can create SQLite backend."""
        config = DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=temp_db_path,
            client_id="test_factory"
        )

        backend = DatabaseBackendFactory.create_backend(config)
        assert backend is not None
        assert isinstance(backend, SQLiteBackend)
        assert backend.backend_type == BackendType.SQLITE

    def test_backend_factory_invalid_type(self):
        """Test that factory raises error for invalid backend type."""
        config = DatabaseConfig(
            backend_type="invalid_type",  # Invalid
            client_id="test"
        )

        with pytest.raises(ValueError):
            BackendFactory.create_backend(config)

    @patch('tldw_Server_API.app.core.DB_Management.backends.postgresql_backend.PSYCOPG2_AVAILABLE', False)
    def test_postgresql_backend_unavailable(self):
        """Test that PostgreSQL backend fails gracefully when psycopg2 not available."""
        config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host="localhost",
            pg_database="test",
            client_id="test"
        )

        with pytest.raises(DatabaseError) as exc_info:
            backend = DatabaseBackendFactory.create_backend(config)
            backend.connect()

        assert "psycopg2 is not installed" in str(exc_info.value)

    def test_fts_query_creation(self):
        """Test FTS query object creation."""
        query = FTSQuery(
            query="test search",
            columns=["title", "content"],
            limit=10,
            offset=0
        )

        assert query.query == "test search"
        assert query.columns == ["title", "content"]
        assert query.limit == 10
        assert query.offset == 0

    def test_sqlite_backend_transaction(self, sqlite_config):
        """Test transaction management in SQLite backend."""
        backend = SQLiteBackend(sqlite_config)

        # Test successful transaction
        with backend.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")

        # Verify table was created
        conn = backend.connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        result = cursor.fetchone()
        assert result is not None
        conn.close()

    def test_sqlite_backend_rollback(self, sqlite_config):
        """Test that transactions rollback on error."""
        backend = SQLiteBackend(sqlite_config)

        # Test failed transaction
        try:
            with backend.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE test_rollback (id INTEGER PRIMARY KEY)")
                # Force an error
                cursor.execute("INVALID SQL")
        except:
            pass  # Expected to fail

        # Verify table was NOT created (rolled back)
        conn = backend.connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_rollback'"
        )
        result = cursor.fetchone()
        assert result is None
        conn.close()


@pytest.mark.skipif(
    "POSTGRES_TEST_HOST" not in os.environ,
    reason="PostgreSQL test environment not configured"
)
class TestPostgreSQLBackend:
    """Tests for PostgreSQL backend (requires PostgreSQL server)."""

    @pytest.fixture
    def pg_config(self):
        """Create PostgreSQL configuration from environment."""
        return DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host=os.environ.get("POSTGRES_TEST_HOST", "localhost"),
            pg_port=int(os.environ.get("POSTGRES_TEST_PORT", 5432)),
            pg_database=os.environ.get("POSTGRES_TEST_DB", "test_tldw"),
            pg_user=os.environ.get("POSTGRES_TEST_USER", "test_user"),
            pg_password=os.environ.get("POSTGRES_TEST_PASSWORD", "test_pass"),
            client_id="test_pg"
        )

    def test_postgresql_backend_creation(self, pg_config):
        """Test PostgreSQL backend creation."""
        from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import PostgreSQLBackend

        backend = PostgreSQLBackend(pg_config)
        assert backend is not None
        assert backend.backend_type == BackendType.POSTGRESQL

    def test_postgresql_features(self, pg_config):
        """Test PostgreSQL feature detection."""
        from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import PostgreSQLBackend

        backend = PostgreSQLBackend(pg_config)
        features = backend.features

        assert features.full_text_search == True
        assert features.json_support == True
        assert features.array_support == True
        assert features.listen_notify == True

    def test_postgresql_failed_statement_rolls_back_before_reuse(self, pg_config):
        """Ensure failed statements do not poison pooled connections."""
        from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import PostgreSQLBackend

        backend = PostgreSQLBackend(pg_config)
        table_name = "test_connection_reset_guard"

        backend.execute(f"DROP TABLE IF EXISTS {table_name}")
        backend.execute(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY)")
        backend.execute(f"INSERT INTO {table_name} (id) VALUES (%s)", (1,))

        try:
            with pytest.raises(DatabaseError):
                backend.execute(f"INSERT INTO {table_name} (id) VALUES (%s)", (1,))

            result = backend.execute(f"SELECT COUNT(*) AS total FROM {table_name}")
            assert result.rows[0]["total"] == 1
        finally:
            backend.execute(f"DROP TABLE IF EXISTS {table_name}")

    def test_postgresql_cte_insert_commits(self, pg_config):
        """CTE bodies with INSERT should be treated as writes and commit automatically."""
        from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import PostgreSQLBackend

        backend = PostgreSQLBackend(pg_config)
        table_name = "test_cte_insert_commit"

        backend.execute(f"DROP TABLE IF EXISTS {table_name}")
        backend.execute(f"CREATE TABLE {table_name} (id SERIAL PRIMARY KEY, note TEXT)")

        try:
            backend.execute(
                f"""
                WITH inserted AS (
                    INSERT INTO {table_name}(note) VALUES (%s)
                    RETURNING id
                )
                SELECT id FROM inserted
                """,
                ("hello",),
            )

            result = backend.execute(f"SELECT COUNT(*) AS total FROM {table_name}")
            assert result.rows[0]["total"] == 1
        finally:
            backend.execute(f"DROP TABLE IF EXISTS {table_name}")
