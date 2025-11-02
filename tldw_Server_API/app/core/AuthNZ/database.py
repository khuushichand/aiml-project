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
from urllib.parse import urlparse, unquote
#
# 3rd-party imports
import asyncpg
import aiosqlite
from loguru import logger
from fastapi import HTTPException
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    DatabaseError,
    ConnectionPoolExhaustedError,
    TransactionError,
    DatabaseLockError,
    DuplicateUserError,
    WeakPasswordError,
    InvalidRegistrationCodeError,
    RegistrationError,
    DuplicateOrganizationError,
    DuplicateTeamError,
    DuplicateRoleError,
    DuplicatePermissionError,
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
        self._sqlite_fs_path: Optional[str] = None
        self._sqlite_uri: bool = False
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
                if self._should_use_postgres():
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
                    self.db_path, self._sqlite_uri, self._sqlite_fs_path = self._resolve_sqlite_paths(self.settings.DATABASE_URL)

                    # Ensure directory exists
                    if self._sqlite_fs_path and self._sqlite_fs_path != ":memory:":
                        db_dir = Path(self._sqlite_fs_path).parent
                        db_dir.mkdir(parents=True, exist_ok=True)

                    logger.info(f"Using SQLite database: {self._sqlite_fs_path or self.db_path}")

                    # Initialize SQLite schema
                    await self._create_sqlite_schema()

                self._initialized = True
                logger.info("Database pool initialized successfully")

            except Exception as e:
                logger.error(f"Failed to initialize database pool: {e}")
                raise DatabaseError(f"Database initialization failed: {e}")

    def _should_use_postgres(self) -> bool:
        """Return True if the configured DATABASE_URL resolves to PostgreSQL."""
        if self.settings.AUTH_MODE != "multi_user":
            return False
        parsed = urlparse(self.settings.DATABASE_URL)
        scheme = (parsed.scheme or "").lower()
        if not scheme:
            return False
        return scheme.startswith("postgres")

    @staticmethod
    def _resolve_sqlite_paths(url: str) -> tuple[str, bool, Optional[str]]:
        """Resolve sqlite connection string, uri flag, and filesystem path."""
        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        if scheme.startswith("file"):
            fs_path = parsed.path or ""
            if fs_path.startswith("//"):
                fs_path = fs_path[1:]
            fs_path = unquote(fs_path or "")
            return url, True, fs_path or None

        if not scheme.startswith("sqlite"):
            # Fallback: treat entire string as path
            return url, False, url

        path_part = parsed.path or ""
        netloc = parsed.netloc or ""
        combined = f"{netloc}{path_part}" if netloc else path_part
        combined = unquote(combined or "")

        if combined in (":memory:", "/:memory:"):
            filesystem_path = ":memory:"
        else:
            if path_part.startswith("//") or netloc:
                filesystem_path = "/" + combined.lstrip("/")
            elif combined.startswith("/"):
                filesystem_path = combined.lstrip("/")
            else:
                filesystem_path = combined

        if filesystem_path.startswith("///"):
            filesystem_path = filesystem_path.lstrip("/")

        if parsed.query:
            if filesystem_path.startswith("/"):
                uri = f"file:{filesystem_path}?{parsed.query}"
            elif filesystem_path:
                uri = f"file:{filesystem_path}?{parsed.query}"
            else:
                uri = f"file:?{parsed.query}"
            return uri, True, filesystem_path or None

        return filesystem_path, False, filesystem_path or None

    async def _create_postgresql_schema(self):
        """Create PostgreSQL schema if it doesn't exist"""
        schema_file = Path(__file__).parent.parent.parent.parent / "Databases" / "Postgres" / "Schema" / "postgresql_users.sql"

        if not schema_file.exists():
            # This path is expected in current builds: schema is provisioned by initialize.py/migrations.
            logger.warning(
                "PostgreSQL schema file not found at %s. Run 'python -m tldw_Server_API.app.core.AuthNZ.initialize' or apply DB migrations to create schema.",
                schema_file,
            )
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

        schema_available = schema_file.exists()
        if not schema_available:
            logger.warning(f"SQLite schema file not found: {schema_file}")

        try:
            async with aiosqlite.connect(self.db_path, uri=self._sqlite_uri) as conn:
                # Enable WAL mode for better concurrency
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute("PRAGMA busy_timeout=5000")

                # Check if users table exists
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                )
                exists = await cursor.fetchone()

                if not exists and schema_available:
                    logger.info("Creating SQLite schema...")
                    schema_sql = schema_file.read_text()
                    await conn.executescript(schema_sql)
                    await conn.commit()
                    logger.info("SQLite schema created successfully")
                else:
                    logger.debug("SQLite schema already exists")

            # Ensure AuthNZ migrations are up to date (handles legacy columns)
            try:
                if self._sqlite_fs_path and self._sqlite_fs_path != ":memory:":
                    await asyncio.to_thread(ensure_authnz_tables, Path(self._sqlite_fs_path))
            except Exception as migration_error:
                logger.debug(f"SQLite migration harmonization skipped: {migration_error}")

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
            except (DuplicateUserError, WeakPasswordError, InvalidRegistrationCodeError, RegistrationError, DuplicateOrganizationError, DuplicateTeamError, DuplicateRoleError, DuplicatePermissionError):
                # Re-raise registration exceptions unchanged
                raise
            except Exception as e:
                logger.error(f"PostgreSQL transaction error: {e}")
                raise TransactionError("PostgreSQL transaction", str(e))
        else:
            # SQLite transaction
            conn = None
            try:
                conn = await aiosqlite.connect(self.db_path, uri=self._sqlite_uri)
                await conn.execute("PRAGMA busy_timeout=5000")
                await conn.execute("PRAGMA foreign_keys = ON")
                await conn.execute("BEGIN")

                try:
                    # Yield a shim that normalizes execute() parameter passing for SQLite
                    class _SQLiteConnShim:
                        def __init__(self, _c):
                            self._c = _c
                        async def execute(self, query: str, *args):
                            # Accept both variadic params and single-sequence params
                            q = _normalize_sqlite_sql(query)
                            if len(args) == 0:
                                return await self._c.execute(q)
                            params = args[0] if (len(args) == 1 and isinstance(args[0], (list, tuple, dict))) else args
                            if isinstance(params, dict):
                                return await self._c.execute(q, params)
                            return await self._c.execute(q, tuple(params))
                        def __getattr__(self, name: str):
                            return getattr(self._c, name)

                    yield _SQLiteConnShim(conn)
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
            except (DuplicateUserError, WeakPasswordError, InvalidRegistrationCodeError, RegistrationError, DuplicateOrganizationError, DuplicateTeamError, DuplicateRoleError, DuplicatePermissionError) as e:
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
                conn = await aiosqlite.connect(self.db_path, uri=self._sqlite_uri)
                await conn.execute("PRAGMA busy_timeout=5000")
                await conn.execute("PRAGMA foreign_keys = ON")
                conn.row_factory = aiosqlite.Row
                # Yield a shim with normalized execute() signature (see transaction())
                class _SQLiteConnShim:
                    def __init__(self, _c):
                        self._c = _c
                    async def execute(self, query: str, *args):
                        q = _normalize_sqlite_sql(query)
                        if len(args) == 0:
                            return await self._c.execute(q)
                        params = args[0] if (len(args) == 1 and isinstance(args[0], (list, tuple, dict))) else args
                        if isinstance(params, dict):
                            return await self._c.execute(q, params)
                        return await self._c.execute(q, tuple(params))
                    def __getattr__(self, name: str):
                        return getattr(self._c, name)

                yield _SQLiteConnShim(conn)
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

    # Compatibility aliases for callers expecting asyncpg-like API
    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Alias for fetchone to match asyncpg-style interfaces."""
        return await self.fetchone(query, *args)

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

    async def fetch(self, query: str, *args) -> list[Any]:
        """Alias for fetchall to match asyncpg-style interfaces."""
        return await self.fetchall(query, *args)

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
                async with aiosqlite.connect(self.db_path, uri=self._sqlite_uri) as conn:
                    await conn.execute("SELECT 1")

                    # Get database file size
                    fs_path = self._sqlite_fs_path
                    db_size = 0
                    if fs_path and fs_path != ":memory:" and os.path.exists(fs_path):
                        db_size = os.path.getsize(fs_path)

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
    current_settings = get_settings()

    if not _db_pool:
        _db_pool = DatabasePool(current_settings)
        await _db_pool.initialize()
        return _db_pool

    previous_settings: Optional[Settings] = getattr(_db_pool, "settings", None)
    if previous_settings:
        auth_mode_changed = previous_settings.AUTH_MODE != current_settings.AUTH_MODE
        db_url_changed = previous_settings.DATABASE_URL != current_settings.DATABASE_URL
        if auth_mode_changed or db_url_changed:
            logger.info(
                "AuthNZ database configuration changed "
                "(AUTH_MODE: {} -> {}, DATABASE_URL: {} -> {}) - recreating pool",
                previous_settings.AUTH_MODE,
                current_settings.AUTH_MODE,
                previous_settings.DATABASE_URL,
                current_settings.DATABASE_URL,
            )
            try:
                await _db_pool.close()
            except Exception as e:
                logger.debug(f"Ignoring error while closing pool during config change: {e}")
            _db_pool = DatabasePool(current_settings)
            await _db_pool.initialize()
            return _db_pool
    else:
        _db_pool.settings = current_settings

    if _db_pool.settings is not current_settings:
        # Keep pool's settings reference in sync with latest resolved Settings object
        _db_pool.settings = current_settings

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
            _db_pool = DatabasePool(current_settings)
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
    try:
        from tldw_Server_API.app.core.MCP_unified.auth.authnz_rbac import reset_rbac_policy as _reset_rbac_policy
        _reset_rbac_policy()
    except Exception:
        pass
    # Reset MCP cached configuration/filters so tests pick up new DB/config values
    try:
        from tldw_Server_API.app.core.MCP_unified.config import get_config as _get_mcp_config
        if hasattr(_get_mcp_config, "cache_clear"):
            _get_mcp_config.cache_clear()
    except Exception:
        pass
    try:
        from tldw_Server_API.app.core.MCP_unified.security.ip_filter import get_ip_access_controller as _get_ip_controller
        if hasattr(_get_ip_controller, "cache_clear"):
            _get_ip_controller.cache_clear()
    except Exception:
        pass
    try:

        from tldw_Server_API.app.core.MCP_unified.server import reset_mcp_server as _reset_mcp_server
        await _reset_mcp_server()
    except Exception:
        pass
    try:
        from tldw_Server_API.app.core.AuthNZ.api_key_manager import reset_api_key_manager as _reset_api_manager
        await _reset_api_manager()
    except Exception:
        pass

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
    try:
        pool = await get_db_pool()
    except DatabaseError as exc:
        logger.debug("AuthNZ backend detection falling back to SQLite due to pool error: {}", exc)
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("AuthNZ backend detection encountered unexpected error: {}", exc)
        return False
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
