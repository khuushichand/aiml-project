# database.py
# Description: Database connection pooling and transaction management for user registration system
#
# Imports
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Any, Dict
import asyncio
#
# 3rd-party imports
import asyncpg
import aiosqlite
from loguru import logger
from fastapi import HTTPException
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    DatabaseError,
    ConnectionPoolExhaustedError,
    TransactionError,
    DatabaseLockError,
    DuplicateUserError,
    WeakPasswordError,
    InvalidRegistrationCodeError,
    RegistrationError
)

#######################################################################################################################
#
# Database Pool Manager

class DatabasePool:
    """Database connection pool manager supporting both PostgreSQL and SQLite"""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize database pool manager"""
        self.settings = settings or get_settings()
        self.pool: Optional[asyncpg.Pool] = None
        self.db_path: Optional[str] = None
        self._initialized = False
        self._lock = asyncio.Lock()
        # Track the event loop this pool is attached to (Postgres only)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    async def initialize(self):
        """Initialize database connection pool"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:
                return
                
            try:
                if self.settings.AUTH_MODE == "multi_user" and self.settings.DATABASE_URL.startswith("postgresql"):
                    # PostgreSQL with connection pooling
                    logger.info("Initializing PostgreSQL connection pool...")
                    
                    self.pool = await asyncpg.create_pool(
                        self.settings.DATABASE_URL,
                        min_size=self.settings.DATABASE_POOL_MIN_SIZE,
                        max_size=self.settings.DATABASE_POOL_MAX_SIZE,
                        max_queries=self.settings.DATABASE_MAX_QUERIES,
                        max_inactive_connection_lifetime=self.settings.DATABASE_MAX_INACTIVE_CONNECTION_LIFETIME,
                        command_timeout=60
                    )
                    # Remember loop for compatibility checks
                    try:
                        self._loop = asyncio.get_running_loop()
                    except RuntimeError:
                        # Fallback for contexts without a running loop
                        self._loop = None
                    
                    # Test connection
                    async with self.pool.acquire() as conn:
                        version = await conn.fetchval("SELECT version()")
                        logger.info(f"PostgreSQL connected: {version[:50]}...")
                    
                    # Create schema if needed
                    await self._create_postgresql_schema()
                    
                else:
                    # SQLite for single-user mode or fallback
                    self.db_path = self.settings.DATABASE_URL.replace("sqlite:///", "")
                    
                    # Ensure directory exists
                    db_dir = Path(self.db_path).parent
                    db_dir.mkdir(parents=True, exist_ok=True)
                    
                    logger.info(f"Using SQLite database: {self.db_path}")
                    
                    # Initialize SQLite schema
                    await self._create_sqlite_schema()
                
                self._initialized = True
                logger.info("Database pool initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize database pool: {e}")
                raise DatabaseError(f"Database initialization failed: {e}")
    
    async def _create_postgresql_schema(self):
        """Create PostgreSQL schema if it doesn't exist"""
        schema_file = Path(__file__).parent.parent.parent.parent / "Databases" / "Postgres" / "Schema" / "postgresql_users.sql"
        
        if not schema_file.exists():
            logger.warning(f"PostgreSQL schema file not found: {schema_file}")
            return
        
        try:
            async with self.pool.acquire() as conn:
                # Check if users table exists
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users')"
                )
                
                if not exists:
                    logger.info("Creating PostgreSQL schema...")
                    schema_sql = schema_file.read_text()
                    await conn.execute(schema_sql)
                    logger.info("PostgreSQL schema created successfully")
                else:
                    logger.debug("PostgreSQL schema already exists")
                    
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL schema: {e}")
            # Don't raise - schema might already exist
    
    async def _create_sqlite_schema(self):
        """Create SQLite schema if it doesn't exist"""
        schema_file = Path(__file__).parent.parent.parent.parent / "Databases" / "SQLite" / "Schema" / "sqlite_users.sql"
        
        if not schema_file.exists():
            logger.warning(f"SQLite schema file not found: {schema_file}")
            return
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                # Enable WAL mode for better concurrency
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute("PRAGMA busy_timeout=5000")
                
                # Check if users table exists
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                )
                exists = await cursor.fetchone()
                
                if not exists:
                    logger.info("Creating SQLite schema...")
                    schema_sql = schema_file.read_text()
                    await conn.executescript(schema_sql)
                    await conn.commit()
                    logger.info("SQLite schema created successfully")
                else:
                    logger.debug("SQLite schema already exists")
                    
        except Exception as e:
            logger.error(f"Failed to create SQLite schema: {e}")
            # Don't raise - schema might already exist
    
    @asynccontextmanager
    async def transaction(self):
        """Database transaction context manager"""
        if not self._initialized:
            await self.initialize()
        
        if self.pool:
            # PostgreSQL transaction
            try:
                async with self.pool.acquire() as conn:
                    async with conn.transaction():
                        yield conn
                logger.debug("PostgreSQL transaction committed successfully")
            except asyncpg.exceptions.TooManyConnectionsError:
                raise ConnectionPoolExhaustedError()
            except HTTPException:
                # Re-raise HTTP exceptions unchanged
                raise
            except (DuplicateUserError, WeakPasswordError, InvalidRegistrationCodeError, RegistrationError):
                # Re-raise registration exceptions unchanged
                raise
            except Exception as e:
                logger.error(f"PostgreSQL transaction error: {e}")
                raise TransactionError("PostgreSQL transaction", str(e))
        else:
            # SQLite transaction
            conn = None
            try:
                conn = await aiosqlite.connect(self.db_path)
                await conn.execute("PRAGMA foreign_keys = ON")
                await conn.execute("BEGIN")
                
                try:
                    yield conn
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise
                    
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e):
                    raise DatabaseLockError()
                raise TransactionError("SQLite transaction", str(e))
            except HTTPException as e:
                # Re-raise HTTP exceptions unchanged
                raise
            except (DuplicateUserError, WeakPasswordError, InvalidRegistrationCodeError, RegistrationError) as e:
                # Re-raise registration exceptions unchanged
                raise
            except Exception as e:
                logger.error(f"SQLite transaction error: {e}")
                raise TransactionError("SQLite transaction", str(e))
            finally:
                if conn:
                    await conn.close()
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a database connection (for queries without transaction)"""
        if not self._initialized:
            await self.initialize()
        
        if self.pool:
            # PostgreSQL connection
            conn = None
            try:
                conn = await self.pool.acquire()
                yield conn
            except asyncpg.exceptions.TooManyConnectionsError:
                raise ConnectionPoolExhaustedError()
            finally:
                if conn:
                    await self.pool.release(conn)
        else:
            # SQLite connection
            conn = None
            try:
                conn = await aiosqlite.connect(self.db_path)
                await conn.execute("PRAGMA foreign_keys = ON")
                conn.row_factory = aiosqlite.Row
                yield conn
            finally:
                if conn:
                    await conn.close()
    
    async def execute(self, query: str, *args) -> Any:
        """Execute a query without returning results"""
        async with self.acquire() as conn:
            if self.pool:
                # PostgreSQL
                params = _flatten_params(args)
                pg_query = _convert_question_mark_to_dollar(query, params)
                return await conn.execute(pg_query, *params)
            else:
                # SQLite
                # Flatten args if a single list/tuple was provided by an adapter
                params = args[0] if (len(args) == 1 and isinstance(args[0], (list, tuple))) else args
                q = _normalize_sqlite_sql(query)
                cursor = await conn.execute(q, tuple(params))
                await conn.commit()
                return cursor
    
    async def fetchone(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        async with self.acquire() as conn:
            if self.pool:
                # PostgreSQL
                params = _flatten_params(args)
                pg_query = _convert_question_mark_to_dollar(query, params)
                row = await conn.fetchrow(pg_query, *params)
                return dict(row) if row else None
            else:
                # SQLite
                params = args[0] if (len(args) == 1 and isinstance(args[0], (list, tuple))) else args
                q = _normalize_sqlite_sql(query)
                cursor = await conn.execute(q, tuple(params))
                row = await cursor.fetchone()
                if row:
                    # Convert Row to dict
                    return {key: row[key] for key in row.keys()}
                return None
    
    async def fetchall(self, query: str, *args) -> list[Any]:
        """Fetch all rows.

        PostgreSQL returns a list of dict-like records (converted via dict(row)).
        SQLite returns aiosqlite.Row objects (supporting both dict-style and index access)
        to maximize compatibility with tests that may use numeric indexing (r[0])
        or key access (r['col']).
        """
        async with self.acquire() as conn:
            if self.pool:
                # PostgreSQL
                params = _flatten_params(args)
                pg_query = _convert_question_mark_to_dollar(query, params)
                rows = await conn.fetch(pg_query, *params)
                return [dict(row) for row in rows]
            else:
                # SQLite
                params = args[0] if (len(args) == 1 and isinstance(args[0], (list, tuple))) else args
                q = _normalize_sqlite_sql(query)
                cursor = await conn.execute(q, tuple(params))
                rows = await cursor.fetchall()
                # Return native Row objects to support both index and key access
                return list(rows)
    
    async def fetchval(self, query: str, *args) -> Any:
        """Fetch a single value"""
        async with self.acquire() as conn:
            if self.pool:
                # PostgreSQL
                params = _flatten_params(args)
                pg_query = _convert_question_mark_to_dollar(query, params)
                return await conn.fetchval(pg_query, *params)
            else:
                # SQLite
                params = args[0] if (len(args) == 1 and isinstance(args[0], (list, tuple))) else args
                q = _normalize_sqlite_sql(query)
                cursor = await conn.execute(q, tuple(params))
                row = await cursor.fetchone()
                return row[0] if row else None
    
    async def close(self):
        """Close database connections"""
        if self.pool:
            try:
                await self.pool.close()
            except Exception as e:
                # In test teardown, the loop bound to the pool may already be closed.
                logger.debug(f"Ignoring pool.close() error during shutdown: {e}")
            finally:
                self.pool = None
                self._loop = None
        self._initialized = False
        logger.info("Database pool closed")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        try:
            if self.pool:
                # PostgreSQL health check
                async with self.pool.acquire() as conn:
                    result = await conn.fetchval("SELECT 1")
                    pool_size = self.pool.get_size()
                    idle_size = self.pool.get_idle_size()
                    
                    return {
                        "status": "healthy",
                        "type": "postgresql",
                        "pool_size": pool_size,
                        "idle_connections": idle_size,
                        "active_connections": pool_size - idle_size
                    }
            else:
                # SQLite health check
                async with aiosqlite.connect(self.db_path) as conn:
                    await conn.execute("SELECT 1")
                    
                    # Get database file size
                    db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                    
                    return {
                        "status": "healthy",
                        "type": "sqlite",
                        "database_size_mb": round(db_size / (1024 * 1024), 2)
                    }
                    
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


#######################################################################################################################
#
# Dependency Injection

# Global database pool instance
_db_pool: Optional[DatabasePool] = None


async def get_db_pool() -> DatabasePool:
    """Get database pool singleton instance"""
    global _db_pool
    if not _db_pool:
        _db_pool = DatabasePool()
        await _db_pool.initialize()
        return _db_pool
    # Ensure the pool is compatible with the current running loop (Postgres path)
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    # If an existing Postgres pool is bound to a different loop, recreate it
    if getattr(_db_pool, 'pool', None) is not None and getattr(_db_pool, '_loop', None) is not None:
        if _db_pool._loop is not None and current_loop is not None and _db_pool._loop is not current_loop:
            logger.info("Detected DB pool bound to a different event loop; recreating for current loop")
            try:
                await _db_pool.close()
            except Exception as e:
                logger.debug(f"Ignoring error while closing incompatible pool: {e}")
            _db_pool = DatabasePool()
            await _db_pool.initialize()
    return _db_pool


async def reset_db_pool():
    """Reset database pool (mainly for testing)"""
    global _db_pool
    if _db_pool:
        try:
            await _db_pool.close()
        except Exception as e:
            # The loop might already be closed by a TestClient; best-effort cleanup.
            logger.debug(f"reset_db_pool: ignoring close error: {e}")
    _db_pool = None


async def get_db():
    """FastAPI dependency to get database connection"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn


async def get_db_transaction():
    """FastAPI dependency to get database transaction"""
    pool = await get_db_pool()
    async with pool.transaction() as conn:
        yield conn


#######################################################################################################################
#
# Utility Functions

async def test_database_connection() -> bool:
    """Test database connection"""
    try:
        pool = await get_db_pool()
        health = await pool.health_check()
        return health.get("status") == "healthy"
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


async def execute_migration(migration_sql: str) -> bool:
    """Execute a database migration"""
    try:
        pool = await get_db_pool()
        await pool.execute(migration_sql)
        logger.info("Migration executed successfully")
        return True
    except Exception as e:
        logger.error(f"Migration failed: {e}")
    return False


# --- Internal helpers ---
_DOLLAR_PARAM = re.compile(r"\$\d+")

#######################################################################################################################
#
# Shared backend detection helper

async def is_postgres_backend() -> bool:
    """Return True if the configured AuthNZ database backend is PostgreSQL.

    Uses the presence of an asyncpg pool on the DatabasePool singleton as the
    definitive signal, avoiding fragile attribute checks on per-request
    connections.
    """
    pool = await get_db_pool()
    return getattr(pool, "pool", None) is not None

def _normalize_sqlite_sql(query: str) -> str:
    """Convert Postgres-style $1 placeholders to SQLite '?' when needed.

    The admin endpoints and services generally branch on backend, but this
    normalization provides a safety net to avoid aiosqlite warnings when a
    $-style query slips through the SQLite path.
    """
    if "$" not in query:
        return query
    # Replace all occurrences of $N with '?' keeping ordering intact
    return _DOLLAR_PARAM.sub("?", query)


def _flatten_params(args: tuple[Any, ...]) -> tuple[Any, ...]:
    """Support both variadic and single-sequence parameter passing."""
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        return tuple(args[0])
    return tuple(args)


def _convert_question_mark_to_dollar(query: str, params: tuple[Any, ...]) -> str:
    """Convert '?' placeholders to Postgres-style '$N' placeholders when needed."""
    if "?" not in query or "$" in query:
        return query
    count = query.count("?")
    if count != len(params):
        logger.warning(
            "Query placeholder count mismatch (found {} '?', got {} params). Leaving query unchanged.",
            count,
            len(params),
        )
        return query
    parts = query.split("?")
    rebuilt = []
    for idx, part in enumerate(parts[:-1]):
        rebuilt.append(part)
        rebuilt.append(f"${idx + 1}")
    rebuilt.append(parts[-1])
    return "".join(rebuilt)


#
# End of database.py
#######################################################################################################################
