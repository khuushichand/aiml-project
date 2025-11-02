# Users_DB.py
# Description: Database operations for user management in multi-user mode
#
# Imports
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import hashlib
import uuid
import sqlite3

# Guarded optional imports for async drivers. Users_DB relies on the
# unified DatabasePool abstraction and should not hard-depend on these
# modules at import time to support SQLite-only deployments.
try:  # pragma: no cover - presence depends on environment
    import asyncpg  # type: ignore
    _ASYNC_PG_AVAILABLE = True
    try:
        _PG_UniqueViolationError = asyncpg.exceptions.UniqueViolationError  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        class _PG_UniqueViolationError(Exception):  # type: ignore
            pass
except Exception:  # pragma: no cover
    _ASYNC_PG_AVAILABLE = False
    class _PG_UniqueViolationError(Exception):  # type: ignore
        pass

try:  # pragma: no cover - optional in SQLite-only deployments
    import aiosqlite  # type: ignore
    _AIOSQLITE_AVAILABLE = True
    # Provide a safe alias for IntegrityError so except clauses don't NameError
    _AIOSQLITE_IntegrityError = aiosqlite.IntegrityError  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _AIOSQLITE_AVAILABLE = False
    # Fallback placeholder so tuple excepts remain valid even when aiosqlite is absent
    class _AIOSQLITE_IntegrityError(Exception):  # type: ignore
        pass
#
# 3rd-party imports
from loguru import logger
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.exceptions import DatabaseError
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

#######################################################################################################################
#
# Exceptions
#

class UserNotFoundError(Exception):
    """Raised when a user is not found in the database"""
    pass

class DuplicateUserError(Exception):
    """Raised when attempting to create a user that already exists"""
    pass

#######################################################################################################################
#
# Users Database Class
#

class UsersDB:
    """Handles all database operations for user management"""

    def __init__(self, db_pool: Optional[DatabasePool] = None):
        """Initialize Users database handler"""
        self.db_pool = db_pool
        self._initialized = False
        self.settings = get_settings()

    def _using_postgres_backend(self) -> bool:
        """Return True when the underlying DatabasePool is backed by PostgreSQL."""
        if self.db_pool is None:
            return False
        return getattr(self.db_pool, "pool", None) is not None

    async def initialize(self):
        """Initialize database connection and ensure tables exist"""
        if self._initialized:
            return

        # Get database pool
        if not self.db_pool:
            self.db_pool = await get_db_pool()

        # Create users table if it doesn't exist
        await self._create_tables()

        self._initialized = True
        logger.info("UsersDB initialized")

    async def _create_tables(self):
        """Create users and related tables if they don't exist"""
        try:
            async with self.db_pool.transaction() as conn:
                is_postgres = getattr(self.db_pool, "pool", None) is not None
                if is_postgres:
                    # PostgreSQL
                    # Prefer pgcrypto (gen_random_uuid); gracefully fall back to uuid-ossp if unavailable.
                    try:
                        await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
                    except Exception as ext_err:  # pragma: no cover - env dependent
                        logger.warning(f"pgcrypto extension not available: {ext_err}. Trying uuid-ossp as fallback.")
                        try:
                            await conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
                        except Exception as ext2_err:
                            logger.warning(f"uuid-ossp extension also unavailable: {ext2_err}. Proceeding without extension; UUID defaults may be set separately if functions exist.")
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            uuid UUID UNIQUE,
                            username VARCHAR(50) UNIQUE NOT NULL,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            metadata JSONB,
                            is_active BOOLEAN DEFAULT TRUE,
                            is_superuser BOOLEAN DEFAULT FALSE,
                            role VARCHAR(50) DEFAULT 'user',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_login TIMESTAMP,
                            email_verified BOOLEAN DEFAULT FALSE,
                            is_verified BOOLEAN DEFAULT FALSE,
                            storage_quota_mb INTEGER DEFAULT 5120,
                            storage_used_mb INTEGER DEFAULT 0
                        )
                    """)

                    # Create indexes
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
                    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS metadata JSONB")
                    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS uuid UUID")
                    # Populate missing UUIDs using available function
                    try:
                        await conn.execute("UPDATE users SET uuid = gen_random_uuid() WHERE uuid IS NULL")
                    except Exception:
                        try:
                            await conn.execute("UPDATE users SET uuid = uuid_generate_v4() WHERE uuid IS NULL")
                        except Exception as uuid_err:
                            logger.warning(f"Unable to populate UUIDs with gen_random_uuid or uuid_generate_v4: {uuid_err}")
                    await conn.execute("ALTER TABLE users ALTER COLUMN uuid SET NOT NULL")
                    try:
                        await conn.execute("ALTER TABLE users ALTER COLUMN uuid SET DEFAULT gen_random_uuid()")
                    except Exception:
                        try:
                            await conn.execute("ALTER TABLE users ALTER COLUMN uuid SET DEFAULT uuid_generate_v4()")
                        except Exception as def_err:
                            logger.warning(f"Could not set UUID default via pgcrypto/uuid-ossp: {def_err}")

                else:
                    # SQLite
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
                            username TEXT UNIQUE NOT NULL,
                            email TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            metadata TEXT,
                            is_active INTEGER DEFAULT 1,
                            is_superuser INTEGER DEFAULT 0,
                            role TEXT DEFAULT 'user',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_login TIMESTAMP,
                            email_verified INTEGER DEFAULT 0,
                            is_verified INTEGER DEFAULT 0,
                            storage_quota_mb INTEGER DEFAULT 5120,
                            storage_used_mb INTEGER DEFAULT 0
                        )
                    """)

                    # Create indexes
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
                    cursor = await conn.execute("PRAGMA table_info(users)")
                    columns_info = await cursor.fetchall()
                    columns = {row[1] for row in columns_info}
                    if "metadata" not in columns:
                        await conn.execute("ALTER TABLE users ADD COLUMN metadata TEXT")
                    if "uuid" not in columns:
                        await conn.execute("ALTER TABLE users ADD COLUMN uuid TEXT UNIQUE")
                    await conn.execute(
                        "UPDATE users SET uuid = lower(hex(randomblob(16))) WHERE uuid IS NULL OR uuid = ''"
                    )

                    await conn.commit()

                logger.debug("Users table and indexes created/verified")

        except Exception as e:
            logger.error(f"Failed to create users table: {e}")
            raise DatabaseError(f"Failed to create users table: {e}")

    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by ID

        Args:
            user_id: User's database ID

        Returns:
            User data dictionary or None if not found

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        if not self._initialized:
            await self.initialize()

        try:
            result = await self.db_pool.fetchone(
                "SELECT * FROM users WHERE id = ?",
                user_id
            )

            if not result:
                raise UserNotFoundError(f"User with ID {user_id} not found")

            # Convert to dictionary
            user_dict = dict(result)

            # Convert boolean fields for SQLite
            if not self._using_postgres_backend():  # SQLite
                user_dict['is_active'] = bool(user_dict.get('is_active', 1))
                user_dict['is_superuser'] = bool(user_dict.get('is_superuser', 0))
                user_dict['email_verified'] = bool(user_dict.get('email_verified', 0))

            return user_dict

        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get user by ID {user_id}: {e}")
            raise DatabaseError(f"Failed to get user: {e}")

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user by username

        Args:
            username: Username to search for

        Returns:
            User data dictionary or None if not found
        """
        if not self._initialized:
            await self.initialize()

        try:
            result = await self.db_pool.fetchone(
                "SELECT * FROM users WHERE username = ?",
                username
            )

            if not result:
                return None

            # Convert to dictionary
            user_dict = dict(result)

            # Convert boolean fields for SQLite
            if not self._using_postgres_backend():  # SQLite
                user_dict['is_active'] = bool(user_dict.get('is_active', 1))
                user_dict['is_superuser'] = bool(user_dict.get('is_superuser', 0))
                user_dict['email_verified'] = bool(user_dict.get('email_verified', 0))

            return user_dict

        except Exception as e:
            logger.error(f"Failed to get user by username {username}: {e}")
            raise DatabaseError(f"Failed to get user: {e}")

    async def get_user_by_uuid(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get user by UUID (textual identifier) when available.

        Args:
            user_uuid: UUID string stored with the user.

        Returns:
            User data dictionary or None if not found.
        """
        if not self._initialized:
            await self.initialize()

        if not user_uuid:
            return None

        try:
            result = await self.db_pool.fetchone(
                "SELECT * FROM users WHERE uuid = ?",
                user_uuid
            )

            if not result:
                return None

            user_dict = dict(result)

            if not self._using_postgres_backend():  # SQLite conversions
                user_dict['is_active'] = bool(user_dict.get('is_active', 1))
                user_dict['is_superuser'] = bool(user_dict.get('is_superuser', 0))
                user_dict['email_verified'] = bool(user_dict.get('email_verified', 0))

            return user_dict

        except Exception as e:
            logger.error(f"Failed to get user by uuid {user_uuid}: {e}")
            raise DatabaseError(f"Failed to get user: {e}")

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user by email

        Args:
            email: Email to search for

        Returns:
            User data dictionary or None if not found
        """
        if not self._initialized:
            await self.initialize()

        try:
            result = await self.db_pool.fetchone(
                "SELECT * FROM users WHERE email = ?",
                email.lower()
            )

            if not result:
                return None

            # Convert to dictionary
            user_dict = dict(result)

            # Convert boolean fields for SQLite
            if not self._using_postgres_backend():  # SQLite
                user_dict['is_active'] = bool(user_dict.get('is_active', 1))
                user_dict['is_superuser'] = bool(user_dict.get('is_superuser', 0))
                user_dict['email_verified'] = bool(user_dict.get('email_verified', 0))

            return user_dict

        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            raise DatabaseError(f"Failed to get user: {e}")

    async def create_user(
        self,
        username: str,
        email: str,
        password_hash: str,
        role: str = "user",
        is_active: bool = True,
        is_superuser: bool = False,
        storage_quota_mb: int = 5120
    ) -> Dict[str, Any]:
        """
        Create a new user

        Args:
            username: Unique username
            email: User's email address
            password_hash: Hashed password
            role: User role (default: "user")
            is_active: Whether user is active
            is_superuser: Whether user is a superuser
            storage_quota_mb: Storage quota in MB

        Returns:
            Created user data

        Raises:
            DuplicateUserError: If username or email already exists
        """
        if not self._initialized:
            await self.initialize()

        # Check for existing user
        existing = await self.get_user_by_username(username)
        if existing:
            raise DuplicateUserError(f"Username '{username}' already exists")

        existing = await self.get_user_by_email(email)
        if existing:
            raise DuplicateUserError(f"Email '{email}' already exists")

        try:
            generated_uuid = str(uuid.uuid4())

            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchval'):
                    # PostgreSQL
                    user_id = await conn.fetchval(
                        """
                        INSERT INTO users (
                            uuid, username, email, password_hash, role,
                            is_active, is_superuser, storage_quota_mb
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        RETURNING id
                        """,
                        generated_uuid, username, email.lower(), password_hash, role,
                        is_active, is_superuser, storage_quota_mb
                    )
                else:
                    # SQLite
                    # Defensive: ensure legacy schemas have required columns
                    try:
                        cur = await conn.execute("PRAGMA table_info(users)")
                        cols = {row[1] for row in await cur.fetchall()}
                        # Add commonly-missing columns for older installs
                        async def _add_col(name: str, decl: str):
                            nonlocal cols
                            if name not in cols:
                                await conn.execute(f"ALTER TABLE users ADD COLUMN {decl}")
                                cols.add(name)

                        await _add_col('uuid', "uuid TEXT UNIQUE")
                        await _add_col('is_active', "is_active INTEGER DEFAULT 1")
                        await _add_col('is_superuser', "is_superuser INTEGER DEFAULT 0")
                        await _add_col('email_verified', "email_verified INTEGER DEFAULT 0")
                        await _add_col('is_verified', "is_verified INTEGER DEFAULT 0")
                        await _add_col('storage_quota_mb', "storage_quota_mb INTEGER DEFAULT 5120")
                        await _add_col('storage_used_mb', "storage_used_mb INTEGER DEFAULT 0")
                    except Exception:
                        # Best-effort; insertion may still succeed if columns already present
                        pass
                    cursor = await conn.execute(
                        """
                        INSERT INTO users (
                            uuid, username, email, password_hash, role,
                            is_active, is_superuser, storage_quota_mb
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            generated_uuid,
                            username,
                            email.lower(),
                            password_hash,
                            role,
                            int(is_active),
                            int(is_superuser),
                            storage_quota_mb,
                        )
                    )
                    user_id = cursor.lastrowid
                    await conn.commit()

                logger.info(f"Created user: {username} (ID: {user_id})")

                # Return the created user
                return await self.get_user_by_id(user_id)

        except DuplicateUserError:
            raise
        except _PG_UniqueViolationError as e:
            logger.warning(f"Duplicate user detected during create_user for '{username}': {e}")
            raise DuplicateUserError("Username or email already exists")
        except (_AIOSQLITE_IntegrityError, sqlite3.IntegrityError) as e:
            message = str(e).lower()
            if "unique constraint failed" in message or "unique constraint violation" in message:
                logger.warning(f"Duplicate user detected during create_user for '{username}': {e}")
                raise DuplicateUserError("Username or email already exists") from e
            logger.error(f"Failed to create user {username}: {e}")
            raise DatabaseError(f"Failed to create user: {e}") from e
        except Exception as e:
            msg = str(e)
            if "UNIQUE constraint failed" in msg and "users" in msg:
                logger.warning(f"Duplicate user detected during create_user for '{username}': {e}")
                raise DuplicateUserError("Username or email already exists")
            logger.error(f"Failed to create user {username}: {e}")
            raise DatabaseError(f"Failed to create user: {e}")

    async def update_user(
        self,
        user_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Update user information

        Args:
            user_id: User ID to update
            **kwargs: Fields to update

        Returns:
            Updated user data
        """
        if not self._initialized:
            await self.initialize()

        # Ensure user exists
        user = await self.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        # Filter allowed fields
        allowed_fields = {
            'email', 'password_hash', 'is_active', 'is_superuser',
            'role', 'last_login', 'email_verified', 'storage_quota_mb',
            'storage_used_mb'
        }

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return user  # Nothing to update

        try:
            # Build update query
            # Note: Build placeholder style per backend; keep deterministic field order
            field_names = list(updates.keys())

            async with self.db_pool.transaction() as conn:
                # Determine backend explicitly: asyncpg connections expose fetchval()
                is_postgres = hasattr(conn, 'fetchval')

                if is_postgres:
                    # PostgreSQL - use $1..$n placeholders
                    set_clause = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(field_names))
                    values = [updates[k] for k in field_names] + [user_id]
                    query = (
                        f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
                        f"WHERE id = ${len(values)}"
                    )
                    await conn.execute(query, *values)
                else:
                    # SQLite - convert bools to ints and use '?' placeholders
                    for key in ['is_active', 'is_superuser', 'email_verified']:
                        if key in updates:
                            updates[key] = int(bool(updates[key]))
                    set_clause = ", ".join(f"{k} = ?" for k in field_names)
                    values = [updates[k] for k in field_names] + [user_id]
                    query = (
                        f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = ?"
                    )
                    await conn.execute(query, values)

                # SQLite shim commits on transaction exit, but keep for compatibility
                if not is_postgres:
                    await conn.commit()

                logger.info(f"Updated user {user_id}: {list(updates.keys())}")

                # Return updated user
                return await self.get_user_by_id(user_id)

        except Exception as e:
            logger.error(f"Failed to update user {user_id}: {e}")
            raise DatabaseError(f"Failed to update user: {e}")

    async def delete_user(self, user_id: int) -> bool:
        """
        Delete a user (soft delete by marking inactive)

        Args:
            user_id: User ID to delete

        Returns:
            True if successful
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Soft delete - just mark as inactive
            await self.update_user(user_id, is_active=False)
            logger.info(f"Soft deleted user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {e}")
            raise DatabaseError(f"Failed to delete user: {e}")

    async def update_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        await self.update_user(user_id, last_login=datetime.utcnow())

    async def list_users(
        self,
        offset: int = 0,
        limit: int = 100,
        role: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        List users with optional filtering

        Args:
            offset: Pagination offset
            limit: Maximum results
            role: Filter by role
            is_active: Filter by active status

        Returns:
            List of user dictionaries
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Build query with filters
            query = "SELECT * FROM users WHERE 1=1"
            params = []

            if role is not None:
                query += " AND role = ?"
                params.append(role)

            if is_active is not None:
                query += " AND is_active = ?"
                params.append(int(is_active) if not self._using_postgres_backend() else is_active)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            results = await self.db_pool.fetchall(query, *params)

            users = []
            for row in results:
                user_dict = dict(row)

                # Convert boolean fields for SQLite
                if not self._using_postgres_backend():  # SQLite
                    user_dict['is_active'] = bool(user_dict.get('is_active', 1))
                    user_dict['is_superuser'] = bool(user_dict.get('is_superuser', 0))
                    user_dict['email_verified'] = bool(user_dict.get('email_verified', 0))

                users.append(user_dict)

            return users

        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            raise DatabaseError(f"Failed to list users: {e}")


#######################################################################################################################
#
# Module Functions
#

# Global instance
_users_db: Optional[UsersDB] = None

async def get_users_db() -> UsersDB:
    """Get UsersDB singleton instance"""
    global _users_db
    if not _users_db:
        _users_db = UsersDB()
        await _users_db.initialize()
    return _users_db

async def reset_users_db() -> None:
    """Reset the UsersDB singleton (testing utility)."""
    global _users_db
    _users_db = None

# Convenience functions for backward compatibility
async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID (convenience function)"""
    db = await get_users_db()
    return await db.get_user_by_id(user_id)

async def get_user_by_uuid(user_uuid: str) -> Optional[Dict[str, Any]]:
    """Get user by UUID (convenience function)"""
    db = await get_users_db()
    return await db.get_user_by_uuid(user_uuid)

async def create_user(username: str, email: str, password_hash: str, **kwargs) -> Dict[str, Any]:
    """Create user (convenience function)"""
    db = await get_users_db()
    return await db.create_user(username, email, password_hash, **kwargs)

async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username (convenience function)"""
    db = await get_users_db()
    return await db.get_user_by_username(username)


#######################################################################################################################
#
# Per-User Database Path Management
# Each user gets their own SQLite database for their media/content
#

def get_user_db_path(user_id: int, db_name: str = "media") -> str:
    """
    Resolve the canonical path for a user's database file.

    Args:
        user_id: The user's ID
        db_name: Logical database key (media, chacha, prompts, audit, evaluations, personalization, etc.)

    Returns:
        Absolute path to the requested database file as a string.
    """
    db_name_normalized = (db_name or "media").strip().lower()
    path_getters = {
        "media": DatabasePaths.get_media_db_path,
        "chacha": DatabasePaths.get_chacha_db_path,
        "chachanotes": DatabasePaths.get_chacha_db_path,
        "prompts": DatabasePaths.get_prompts_db_path,
        "audit": DatabasePaths.get_audit_db_path,
        "evaluations": DatabasePaths.get_evaluations_db_path,
        "personalization": DatabasePaths.get_personalization_db_path,
        "workflows": DatabasePaths.get_workflows_db_path,
        "workflows_scheduler": DatabasePaths.get_workflows_scheduler_db_path,
    }

    getter = path_getters.get(db_name_normalized)
    if getter:
        return str(getter(user_id))

    # Fallback: place custom databases alongside the canonical user directory
    fallback_path = DatabasePaths.get_user_base_directory(user_id) / f"{db_name_normalized}.db"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    return str(fallback_path)


def get_user_chromadb_path(user_id: int) -> str:
    """
    Construct the path for a user's ChromaDB data.

    Args:
        user_id: The user's ID

    Returns:
        Path to the user's ChromaDB directory
    """
    base_dir = DatabasePaths.get_user_base_directory(user_id)
    chroma_path = base_dir / "chroma_storage"
    chroma_path.mkdir(parents=True, exist_ok=True)
    return str(chroma_path)


async def get_user_media_db(user_id: int, db_name: str = "media"):
    """
    Get a MediaDatabase instance for a specific user.

    Args:
        user_id: The user's ID
        db_name: Name of the database

    Returns:
        MediaDatabase instance for the user

    Note:
        This creates the user directory structure if it doesn't exist.
    """
    from pathlib import Path

    # Get the database path (ensures directory exists)
    db_path = Path(get_user_db_path(user_id, db_name))

    # Import media DB factory (avoid circular import)
    try:
        from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database

        # Create and return the database instance via central factory
        db_instance = create_media_database(client_id=str(user_id), db_path=str(db_path))
        return db_instance

    except ImportError as e:
        logger.error(f"Failed to import MediaDatabase: {e}")
        raise ImportError("MediaDatabase class not available")


async def ensure_user_directories(user_id: int):
    """
    Ensure all necessary directories exist for a user.

    Args:
        user_id: The user's ID
    """
    from pathlib import Path

    # Ensure database structure via centralized helpers
    DatabasePaths.validate_database_structure(user_id)

    # Ensure Chroma storage directory exists alongside other user assets
    chroma_dir = Path(get_user_chromadb_path(user_id))
    chroma_dir.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Ensured directories exist for user {user_id} -> {DatabasePaths.get_user_base_directory(user_id)}")


async def cleanup_user_data(user_id: int):
    """
    Clean up all data associated with a user (for deletion).

    Args:
        user_id: The user's ID

    Warning:
        This permanently deletes all user data!
    """
    import shutil

    base_dir = DatabasePaths.get_user_base_directory(user_id)
    if base_dir.exists():
        shutil.rmtree(base_dir)
        logger.info(f"Removed user data directory for user {user_id}: {base_dir}")


#
# End of Users_DB.py
#######################################################################################################################
