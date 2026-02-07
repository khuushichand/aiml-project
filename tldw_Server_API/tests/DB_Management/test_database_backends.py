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
    DatabaseError,
)
from tldw_Server_API.app.core.DB_Management.backends.sqlite_backend import SQLiteBackend
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.backends.factory import BackendFactory


class TestDatabaseBackends:
    """Test suite for database backend implementations."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
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
        return DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=temp_db_path, client_id="test_client")

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
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        result = cursor.fetchone()
        assert result is not None
        conn.close()

    def test_sqlite_backend_pragma_returns_rows(self, sqlite_config):
        """Ensure PRAGMA results are returned for table introspection."""
        backend = SQLiteBackend(sqlite_config)
        backend.create_tables("CREATE TABLE IF NOT EXISTS pragma_table (id INTEGER PRIMARY KEY, name TEXT)")

        pragma_result = backend.execute("PRAGMA table_info(pragma_table)")
        assert pragma_result.rows

        info = backend.get_table_info("pragma_table")
        columns = {col.get("name") for col in info}
        assert "id" in columns
        assert "name" in columns

    def test_sqlite_backend_fts_rank_expression_sanitization(self, sqlite_config):
        """Ensure unsafe FTS rank expressions are ignored and queries remain safe."""
        backend = SQLiteBackend(sqlite_config)
        backend.create_tables("CREATE TABLE IF NOT EXISTS docs (id INTEGER PRIMARY KEY, title TEXT, content TEXT)")
        backend.execute("INSERT INTO docs (title, content) VALUES (?, ?)", ("hello", "world"))
        backend.create_fts_table("docs_fts", "docs", ["title", "content"])

        unsafe = "bm25(docs_fts); DROP TABLE docs; --"
        res = backend.fts_search(FTSQuery(query="hello", table="docs_fts", rank_expression=unsafe))
        assert res.rows
        assert backend.table_exists("docs")

        safe = "bm25(docs_fts, 1.0, 2)"
        safe_res = backend.fts_search(FTSQuery(query="hello", table="docs_fts", rank_expression=safe))
        assert safe_res.rows

    def test_backend_factory_sqlite(self, temp_db_path):
        """Test that factory can create SQLite backend."""
        config = DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=temp_db_path, client_id="test_factory")

        backend = DatabaseBackendFactory.create_backend(config)
        assert backend is not None
        assert isinstance(backend, SQLiteBackend)
        assert backend.backend_type == BackendType.SQLITE

    def test_backend_factory_invalid_type(self):
        """Test that factory raises error for invalid backend type."""
        config = DatabaseConfig(backend_type="invalid_type", client_id="test")  # Invalid

        with pytest.raises(ValueError):
            BackendFactory.create_backend(config)

    @patch("tldw_Server_API.app.core.DB_Management.backends.postgresql_backend.PSYCOPG2_AVAILABLE", False)
    def test_postgresql_backend_unavailable(self):
        """Test that PostgreSQL backend fails gracefully when psycopg2 not available."""
        config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL, pg_host="localhost", pg_database="test", client_id="test"
        )

        with pytest.raises(DatabaseError) as exc_info:
            backend = DatabaseBackendFactory.create_backend(config)
            backend.connect()

        assert "psycopg2 is not installed" in str(exc_info.value)

    def test_fts_query_creation(self):
        """Test FTS query object creation."""
        query = FTSQuery(query="test search", columns=["title", "content"], limit=10, offset=0)

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
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
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
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_rollback'")
        result = cursor.fetchone()
        assert result is None
        conn.close()

    def test_sqlite_backend_nested_transaction_does_not_commit_outer(self, sqlite_config):
        """Nested transactions should not commit the outer transaction."""
        backend = SQLiteBackend(sqlite_config)

        # Create table outside transaction so we only test row rollback behavior.
        conn = backend.connect()
        conn.execute("CREATE TABLE nested_txn_test (id INTEGER PRIMARY KEY, value TEXT)")
        conn.close()

        with pytest.raises(RuntimeError):
            with backend.transaction() as conn:
                conn.execute("INSERT INTO nested_txn_test (value) VALUES ('outer')")
                with backend.transaction() as inner_conn:
                    inner_conn.execute("INSERT INTO nested_txn_test (value) VALUES ('inner')")
                raise RuntimeError("boom")

        conn = backend.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM nested_txn_test")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0


class TestPostgreSQLBackend:
    """Tests for PostgreSQL backend (requires PostgreSQL server)."""

    @pytest.fixture
    def pg_config(self, pg_database_config):
        """Use unified Postgres fixture to provision a per-test database.

        This avoids depending on a pre-existing database specified via env vars
        and ensures the DB exists before tests run.
        """
        # Attach a client_id for parity with other backends/tests
        pg_database_config.client_id = "test_pg"
        return pg_database_config

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

    def test_postgresql_fts_search_uses_source_table_mapping(self, pg_config):
        """FTS search should work when table_name differs from source_table."""
        from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import PostgreSQLBackend

        backend = PostgreSQLBackend(pg_config)
        source_table = "fts_mapping_docs"
        fts_table = "docs_fts"

        backend.execute(f"DROP TABLE IF EXISTS {source_table}")
        backend.execute(f"CREATE TABLE {source_table} (id SERIAL PRIMARY KEY, title TEXT, body TEXT)")
        backend.execute(
            f"INSERT INTO {source_table} (title, body) VALUES (%s, %s)",
            ("hello", "world"),
        )

        try:
            backend.create_fts_table(fts_table, source_table, ["title", "body"])
            res = backend.fts_search(FTSQuery(query="hello", table=fts_table))
            assert res.rows
        finally:
            backend.execute(f"DROP TABLE IF EXISTS {source_table}")
