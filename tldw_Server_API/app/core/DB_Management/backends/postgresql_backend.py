"""
PostgreSQL backend implementation for the database abstraction layer.

This module provides a concrete implementation of the DatabaseBackend
interface for PostgreSQL databases, enabling the application to use
PostgreSQL as an alternative to SQLite.

Note: This implementation requires psycopg2 or psycopg3 to be installed:
    pip install psycopg2-binary psycopg2-pool
    # or
    pip install "psycopg[binary,pool]"
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union, Generator
import json

from .base import (
    DatabaseBackend,
    DatabaseConfig,
    BackendType,
    BackendFeatures,
    ConnectionPool,
    QueryResult,
    FTSQuery,
    DatabaseError,
    NotSupportedError
)

logger = logging.getLogger(__name__)

# Try to import psycopg2, but don't fail if not available
try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not available. PostgreSQL backend will not work.")


class PostgreSQLConnectionPool(ConnectionPool):
    """PostgreSQL connection pool using psycopg2."""
    
    def __init__(self, config: DatabaseConfig):
        """
        Initialize PostgreSQL connection pool.
        
        Args:
            config: Database configuration
        """
        if not PSYCOPG2_AVAILABLE:
            raise DatabaseError("psycopg2 is not installed. Install with: pip install psycopg2-binary")
        
        self.config = config
        self._closed = False
        
        # Build connection parameters
        conn_params = {
            'host': config.pg_host or 'localhost',
            'port': config.pg_port or 5432,
            'database': config.pg_database or 'tldw',
            'user': config.pg_user or 'tldw_user',
            'password': config.pg_password or '',
            'sslmode': config.pg_sslmode or 'prefer',
            'connect_timeout': config.connect_timeout or 10,
            'cursor_factory': psycopg2.extras.RealDictCursor,
        }
        
        # Create connection pool
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=config.pool_size or 10,
            **conn_params
        )
    
    def get_connection(self) -> Any:
        """Get a connection from the pool."""
        if self._closed:
            raise DatabaseError("Connection pool is closed")
        return self._pool.getconn()
    
    def return_connection(self, connection: Any) -> None:
        """Return a connection to the pool."""
        if not self._closed:
            self._pool.putconn(connection)
    
    @contextmanager
    def connection(self) -> Generator[Any, None, None]:
        """Context manager for connection handling."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)
    
    def close_all(self) -> None:
        """Close all connections in the pool."""
        self._closed = True
        self._pool.closeall()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "closed": self._closed,
            "backend": "postgresql"
        }


class PostgreSQLBackend(DatabaseBackend):
    """PostgreSQL implementation of the database backend."""
    
    @property
    def backend_type(self) -> BackendType:
        """Get the backend type."""
        return BackendType.POSTGRESQL
    
    def _get_features(self) -> BackendFeatures:
        """Get PostgreSQL feature support."""
        return BackendFeatures(
            full_text_search=True,   # tsvector/tsquery
            json_support=True,        # JSON/JSONB
            array_support=True,       # Native arrays
            window_functions=True,    # Full support
            cte_support=True,         # WITH queries
            partial_indexes=True,     # Partial indexes
            generated_columns=True,   # GENERATED columns
            upsert_support=True,      # ON CONFLICT
            returning_clause=True,    # RETURNING
            listen_notify=True        # LISTEN/NOTIFY
        )
    
    def connect(self) -> Any:
        """Create a new PostgreSQL connection."""
        if not PSYCOPG2_AVAILABLE:
            raise DatabaseError("psycopg2 is not installed")
        
        conn = psycopg2.connect(
            host=self.config.pg_host or 'localhost',
            port=self.config.pg_port or 5432,
            database=self.config.pg_database or 'tldw',
            user=self.config.pg_user or 'tldw_user',
            password=self.config.pg_password or '',
            sslmode=self.config.pg_sslmode or 'prefer',
            connect_timeout=self.config.connect_timeout or 10
        )
        
        # Use RealDictCursor for dict-like row access
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        
        return conn
    
    def disconnect(self, connection: Any) -> None:
        """Close a PostgreSQL connection."""
        if connection and not connection.closed:
            connection.close()
    
    @contextmanager
    def transaction(self, connection: Optional[Any] = None) -> Generator[Any, None, None]:
        """PostgreSQL transaction context manager."""
        if connection:
            conn = connection
            owns_connection = False
        else:
            conn = self.get_pool().get_connection()
            owns_connection = True
        
        try:
            # PostgreSQL uses implicit transactions
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
        finally:
            if owns_connection:
                self.get_pool().return_connection(conn)
    
    def get_pool(self) -> ConnectionPool:
        """Get or create the connection pool."""
        if self._pool is None:
            self._pool = PostgreSQLConnectionPool(self.config)
        return self._pool
    
    def execute(
        self,
        query: str,
        params: Optional[Union[Tuple, Dict]] = None,
        connection: Optional[Any] = None
    ) -> QueryResult:
        """Execute a query and return results."""
        start_time = time.time()
        
        if connection:
            conn = connection
            external_conn = True
        else:
            conn = self.get_pool().get_connection()
            external_conn = False
        
        try:
            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            statement = query.strip()
            statement_upper = statement.upper()
            has_description = cursor.description is not None

            if has_description:
                rows = cursor.fetchall()
                if rows and not isinstance(rows[0], dict):
                    column_names = [col[0] for col in cursor.description or []]
                    result_rows = [
                        {column_names[idx]: value for idx, value in enumerate(row)}
                        for row in rows
                    ]
                else:
                    result_rows = [dict(row) for row in rows]
                if not statement_upper.startswith("SELECT"):
                    conn.commit()
            else:
                result_rows = []
                if not statement_upper.startswith("SELECT"):
                    conn.commit()

            execution_time = time.time() - start_time

            lastrowid = None
            if result_rows:
                first_row = result_rows[0]
                lastrowid = first_row.get('id') if isinstance(first_row, dict) else None

            return QueryResult(
                rows=result_rows,
                rowcount=cursor.rowcount,
                lastrowid=lastrowid,
                description=cursor.description,
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise DatabaseError(f"PostgreSQL error: {e}")
        finally:
            if not external_conn:
                self.get_pool().return_connection(conn)
    
    def execute_many(
        self,
        query: str,
        params_list: List[Union[Tuple, Dict]],
        connection: Optional[Any] = None
    ) -> QueryResult:
        """Execute a query multiple times with different parameters."""
        start_time = time.time()
        
        if connection:
            conn = connection
            external_conn = True
        else:
            conn = self.get_pool().get_connection()
            external_conn = False
        
        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            
            execution_time = time.time() - start_time
            
            return QueryResult(
                rows=[],
                rowcount=cursor.rowcount,
                lastrowid=None,
                description=cursor.description,
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            raise DatabaseError(f"PostgreSQL error: {e}")
        finally:
            if not external_conn:
                self.get_pool().return_connection(conn)
    
    def create_tables(self, schema: str, connection: Optional[Any] = None) -> None:
        """Create tables from a schema definition."""
        # PostgreSQL doesn't support multiple statements in execute()
        # Need to split and execute separately
        statements = [s.strip() for s in schema.split(';') if s.strip()]
        
        if connection:
            conn = connection
            external_conn = True
        else:
            conn = self.get_pool().get_connection()
            external_conn = False
        
        try:
            cursor = conn.cursor()
            for statement in statements:
                if statement:
                    cursor.execute(statement)
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Schema creation failed: {e}")
            raise DatabaseError(f"Failed to create schema: {e}")
        finally:
            if not external_conn:
                self.get_pool().return_connection(conn)
    
    def table_exists(self, table_name: str, connection: Optional[Any] = None) -> bool:
        """Check if a table exists."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            )
        """
        result = self.execute(query, (table_name,), connection)
        return result.scalar
    
    def get_table_info(
        self,
        table_name: str,
        connection: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Get information about a table's columns."""
        query = """
            SELECT 
                column_name as name,
                data_type as type,
                is_nullable = 'YES' as nullable,
                column_default as default,
                false as primary_key
            FROM information_schema.columns
            WHERE table_schema = 'public' 
            AND table_name = %s
            ORDER BY ordinal_position
        """
        result = self.execute(query, (table_name,), connection)
        return result.rows
    
    def create_fts_table(
        self,
        table_name: str,
        source_table: str,
        columns: List[str],
        connection: Optional[Any] = None
    ) -> None:
        """
        Create PostgreSQL full-text search setup.
        
        Instead of a virtual table, PostgreSQL uses tsvector columns
        and GIN indexes.
        """
        self.features.require("full_text_search")
        
        if connection:
            conn = connection
            external_conn = True
        else:
            conn = self.get_pool().get_connection()
            external_conn = False
        
        try:
            cursor = conn.cursor()
            
            # Add tsvector column to source table if not exists
            fts_column = f"{table_name}_tsv"
            cursor.execute(f"""
                ALTER TABLE {self.escape_identifier(source_table)} 
                ADD COLUMN IF NOT EXISTS {self.escape_identifier(fts_column)} tsvector
            """)
            
            # Create update function for tsvector
            # Build columns concat for both contexts
            columns_concat_set = " || ' ' || ".join([
                f"coalesce({self.escape_identifier(col)}, '')"
                for col in columns
            ])
            columns_concat_new = " || ' ' || ".join([
                f"coalesce(NEW.{self.escape_identifier(col)}, '')"
                for col in columns
            ])
            
            cursor.execute(f"""
                UPDATE {self.escape_identifier(source_table)}
                SET {self.escape_identifier(fts_column)} = 
                    to_tsvector('english', {columns_concat_set})
            """)
            
            # Create GIN index for fast searching
            index_name = f"idx_{source_table}_{fts_column}"
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {self.escape_identifier(index_name)}
                ON {self.escape_identifier(source_table)} 
                USING gin({self.escape_identifier(fts_column)})
            """)
            
            # Create trigger to keep tsvector updated
            trigger_name = f"update_{fts_column}_trigger"
            function_name = f"update_{fts_column}_function"
            
            cursor.execute(f"""
                CREATE OR REPLACE FUNCTION {self.escape_identifier(function_name)}()
                RETURNS trigger AS $$
                BEGIN
                    NEW.{self.escape_identifier(fts_column)} := 
                        to_tsvector('english', {columns_concat_new});
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
            """)
            
            cursor.execute(f"""
                DROP TRIGGER IF EXISTS {self.escape_identifier(trigger_name)} 
                ON {self.escape_identifier(source_table)}
            """)
            
            cursor.execute(f"""
                CREATE TRIGGER {self.escape_identifier(trigger_name)}
                BEFORE INSERT OR UPDATE ON {self.escape_identifier(source_table)}
                FOR EACH ROW EXECUTE FUNCTION {self.escape_identifier(function_name)}()
            """)
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            logger.error(f"FTS setup failed: {e}")
            raise DatabaseError(f"Failed to create FTS: {e}")
        finally:
            if not external_conn:
                self.get_pool().return_connection(conn)
    
    def fts_search(
        self,
        fts_query: FTSQuery,
        connection: Optional[Any] = None
    ) -> QueryResult:
        """Perform a PostgreSQL full-text search."""
        self.features.require("full_text_search")
        
        if not fts_query.table:
            raise DatabaseError("Table name required for FTS")
        
        # Build the FTS query
        fts_column = f"{fts_query.table}_tsv"
        
        query_parts = [
            f"SELECT *, ts_rank({self.escape_identifier(fts_column)}, query) AS rank",
            f"FROM {self.escape_identifier(fts_query.table)},",
            f"to_tsquery('english', %s) query",
            f"WHERE {self.escape_identifier(fts_column)} @@ query"
        ]
        
        params = [fts_query.query_text]
        
        # Add additional filters
        for key, value in fts_query.filters.items():
            query_parts.append(f"AND {self.escape_identifier(key)} = %s")
            params.append(value)
        
        # Add ORDER BY
        query_parts.append("ORDER BY rank DESC")
        
        # Add LIMIT/OFFSET
        if fts_query.limit:
            query_parts.append(f"LIMIT {fts_query.limit}")
        if fts_query.offset:
            query_parts.append(f"OFFSET {fts_query.offset}")
        
        query = " ".join(query_parts)
        
        return self.execute(query, tuple(params), connection)
    
    def update_fts_index(
        self,
        table_name: str,
        connection: Optional[Any] = None
    ) -> None:
        """Update PostgreSQL FTS index (trigger-based, so automatic)."""
        # PostgreSQL FTS is updated automatically via triggers
        # This method exists for API compatibility
        pass
    
    def escape_identifier(self, identifier: str) -> str:
        """Escape a PostgreSQL identifier."""
        # PostgreSQL uses double quotes for identifiers
        return '"' + identifier.replace('"', '""') + '"'
    
    def get_last_insert_id(self, connection: Optional[Any] = None) -> Optional[int]:
        """Get the last inserted row ID using RETURNING clause."""
        # PostgreSQL doesn't have a direct equivalent to SQLite's lastrowid
        # Use RETURNING clause in INSERT statements instead
        logger.warning("PostgreSQL doesn't support last_insert_id. Use RETURNING clause in INSERT.")
        return None
    
    def vacuum(self, connection: Optional[Any] = None) -> None:
        """Vacuum the PostgreSQL database."""
        # VACUUM can't run in a transaction
        if connection:
            conn = connection
            external_conn = True
        else:
            conn = self.connect()  # Need a separate connection
            external_conn = False
        
        try:
            old_isolation = conn.isolation_level
            conn.set_isolation_level(0)  # AUTOCOMMIT
            cursor = conn.cursor()
            cursor.execute("VACUUM ANALYZE")
            conn.set_isolation_level(old_isolation)
        finally:
            if not external_conn:
                conn.close()
    
    def get_database_size(self, connection: Optional[Any] = None) -> int:
        """Get the database size in bytes."""
        query = "SELECT pg_database_size(current_database())"
        result = self.execute(query, connection=connection)
        return result.scalar or 0
    
    def export_schema(self, connection: Optional[Any] = None) -> str:
        """Export the database schema as SQL."""
        # This would require pg_dump or complex queries
        # Simplified version that gets table definitions
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """
        result = self.execute(query, connection=connection)
        
        schema_parts = []
        for row in result.rows:
            table_name = row['table_name']
            # This is a simplified version - full implementation would need pg_dump
            schema_parts.append(f"-- Table: {table_name}")
        
        return "\n".join(schema_parts)
    
    def export_data(
        self,
        table_name: str,
        connection: Optional[Any] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """Export data from a table."""
        query = f"SELECT * FROM {self.escape_identifier(table_name)}"
        
        if connection:
            conn = connection
            external_conn = True
        else:
            conn = self.get_pool().get_connection()
            external_conn = False
        
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            
            for row in cursor:
                yield dict(row)
        finally:
            if not external_conn:
                self.get_pool().return_connection(conn)
    
    def import_data(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        connection: Optional[Any] = None
    ) -> int:
        """Import data into a table."""
        if not data:
            return 0
        
        # Get column names from first row
        columns = list(data[0].keys())
        columns_str = ", ".join([self.escape_identifier(col) for col in columns])
        placeholders = ", ".join(["%s" for _ in columns])
        
        query = f"""
            INSERT INTO {self.escape_identifier(table_name)} ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING
        """
        
        # Convert dicts to tuples
        params_list = [tuple(row.get(col) for col in columns) for row in data]
        
        result = self.execute_many(query, params_list, connection)
        return result.rowcount
