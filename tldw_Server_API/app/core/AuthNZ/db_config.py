# db_config.py
# Description: Centralized database configuration helper for AuthNZ system
#
# This module provides a unified configuration system for database backend selection,
# supporting both SQLite and PostgreSQL with automatic detection from environment.
#
########################################################################################################################

import os
from typing import Optional, Dict, Any
from pathlib import Path
from urllib.parse import urlparse, unquote
from loguru import logger

from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig, BackendType
from tldw_Server_API.app.core.DB_Management.UserDatabase_v2 import UserDatabase
from tldw_Server_API.app.core.AuthNZ.settings import get_settings

logger = logger

########################################################################################################################
# Configuration Helper Class
########################################################################################################################

class AuthDatabaseConfig:
    """
    Centralized configuration helper for AuthNZ database backend selection.

    Supports automatic detection from environment variables and provides
    consistent configuration across all AuthNZ modules.
    """

    # Singleton instance
    _instance: Optional['AuthDatabaseConfig'] = None
    _user_db: Optional[UserDatabase] = None

    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize configuration from environment and settings."""
        if not hasattr(self, '_initialized'):
            self.settings = get_settings()
            self._initialized = True
            self._detect_backend()

    def _detect_backend(self):
        """Detect database backend from environment or settings."""
        # Always refresh settings snapshot in case reset_settings() was called
        try:
            self.settings = get_settings()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"AuthDatabaseConfig: falling back to existing settings snapshot: {exc}")

        # Check environment variable first
        self.backend_type = os.getenv("TLDW_USER_DB_BACKEND", "").lower()

        # If not set, try to infer from DATABASE_URL
        if not self.backend_type:
            db_url = self.settings.DATABASE_URL
            parsed = urlparse(db_url)
            scheme = (parsed.scheme or "").lower()
            base_scheme = scheme.split("+", 1)[0]
            if base_scheme in {"postgresql", "postgres"}:
                self.backend_type = "postgresql"
            elif base_scheme in {"sqlite", "file"}:
                self.backend_type = "sqlite"
            else:
                # Default to SQLite
                self.backend_type = "sqlite"

        logger.info(f"Detected database backend: {self.backend_type}")

    def get_config(self) -> DatabaseConfig:
        """
        Get database configuration based on detected backend.

        Returns:
            DatabaseConfig: Configuration for the selected backend
        """
        if self.backend_type in ["postgresql", "postgres"]:
            return self._get_postgresql_config()
        else:
            return self._get_sqlite_config()

    def _get_sqlite_config(self) -> DatabaseConfig:
        """
        Get SQLite configuration.

        Returns:
            DatabaseConfig: SQLite-specific configuration
        """
        raw_url = self.settings.DATABASE_URL
        # Extract path from sqlite:/// URL or use as-is
        parsed = urlparse(raw_url)
        scheme = (parsed.scheme or "").lower()
        base_scheme = scheme.split("+", 1)[0]

        def _combine_path() -> str:
            netloc = parsed.netloc or ""
            path = parsed.path or ""
            combined = f"{netloc}{path}" if netloc else path
            combined = unquote(combined or "")
            # Handle sqlite:///:memory: and variants
            if combined in {":memory:", "/:memory:"}:
                return ":memory:"
            if combined.startswith("///"):
                combined = combined.lstrip("/")
            if combined.startswith("/"):
                try:
                    return str(Path(combined).resolve())
                except Exception:
                    return combined
            # Relative path - resolve against project root
            return str((Path.cwd() / combined).resolve())

        if base_scheme in {"sqlite", "file", ""}:
            combined = _combine_path()
            if combined == ":memory:":
                sqlite_path = ":memory:"
            else:
                sqlite_path = combined
        else:
            # Fallback for unexpected schemes, treat as direct path
            sqlite_path = raw_url

        config = DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=sqlite_path,
            sqlite_wal_mode=self._get_bool_env("TLDW_SQLITE_WAL_MODE", True),
            sqlite_foreign_keys=self._get_bool_env("TLDW_SQLITE_FOREIGN_KEYS", True),
            echo=self._get_bool_env("TLDW_DB_ECHO", False)
        )

        logger.debug(f"SQLite config: path={sqlite_path}")
        return config

    def _get_postgresql_config(self) -> DatabaseConfig:
        """
        Get PostgreSQL configuration.

        Returns:
            DatabaseConfig: PostgreSQL-specific configuration
        """
        # Use DATABASE_URL or construct from components
        connection_string = os.getenv("DATABASE_URL", self.settings.DATABASE_URL)

        # If not a full URL, try to construct from components
        if not connection_string.startswith(("postgresql://", "postgres://")):
            host = os.getenv("TLDW_PG_HOST", "localhost")
            port = int(os.getenv("TLDW_PG_PORT", "5432"))
            database = os.getenv("TLDW_PG_DATABASE", "tldw_users")
            user = os.getenv("TLDW_PG_USER", "tldw")
            password = os.getenv("TLDW_PG_PASSWORD", "")

            connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"

        config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            connection_string=connection_string,
            pool_size=int(os.getenv("TLDW_DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("TLDW_DB_MAX_OVERFLOW", "20")),
            pool_timeout=float(os.getenv("TLDW_DB_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("TLDW_DB_POOL_RECYCLE", "3600")),
            pg_sslmode=os.getenv("TLDW_PG_SSLMODE", "prefer"),
            echo=self._get_bool_env("TLDW_DB_ECHO", False)
        )

        # Mask password in log
        parsed = urlparse(connection_string)
        safe_url = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}{parsed.path}"
        logger.debug(f"PostgreSQL config: url={safe_url}, pool_size={config.pool_size}")

        return config

    def get_user_database(self, client_id: str = "auth_service") -> UserDatabase:
        """
        Get or create UserDatabase instance with proper configuration.

        Args:
            client_id: Client identifier for database operations

        Returns:
            UserDatabase: Configured database instance
        """
        if self._user_db is None:
            config = self.get_config()
            self._user_db = UserDatabase(config=config, client_id=client_id)
            logger.info(f"Created UserDatabase with {self.backend_type} backend")
        return self._user_db

    def reset(self):
        """Reset configuration and database instance (mainly for testing)."""
        self._user_db = None
        # Ensure backend detection reflects updated environment/settings
        self.settings = get_settings()
        self._detect_backend()

    @staticmethod
    def _get_bool_env(key: str, default: bool) -> bool:
        """
        Get boolean value from environment variable.

        Args:
            key: Environment variable name
            default: Default value if not set

        Returns:
            bool: Parsed boolean value
        """
        value = os.getenv(key, "").lower()
        if value in ("true", "1", "yes", "on"):
            return True
        elif value in ("false", "0", "no", "off"):
            return False
        return default

    def get_info(self) -> Dict[str, Any]:
        """
        Get configuration information for debugging/logging.

        Returns:
            Dict with configuration details
        """
        info = {
            "backend_type": self.backend_type,
            "auth_mode": self.settings.AUTH_MODE,
            "registration_enabled": self.settings.ENABLE_REGISTRATION,
            "require_registration_code": self.settings.REQUIRE_REGISTRATION_CODE
        }

        if self.backend_type == "sqlite":
            info["database_path"] = self.settings.DATABASE_URL.replace("sqlite:///", "")
        else:
            parsed = urlparse(self.settings.DATABASE_URL)
            info["database_host"] = parsed.hostname
            info["database_name"] = parsed.path.lstrip("/")

        return info

    @classmethod
    def print_config(cls):
        """Print current configuration for debugging."""
        instance = cls()
        info = instance.get_info()

        print("\n" + "="*60)
        print("AuthNZ Database Configuration")
        print("="*60)

        for key, value in info.items():
            print(f"  {key:.<30} {value}")

        print("="*60 + "\n")

########################################################################################################################
# Convenience Functions
########################################################################################################################

def get_auth_db_config() -> AuthDatabaseConfig:
    """
    Get the AuthDatabaseConfig singleton instance.

    Returns:
        AuthDatabaseConfig: Configuration instance
    """
    return AuthDatabaseConfig()

def get_configured_user_database(client_id: str = "auth_service") -> UserDatabase:
    """
    Get a properly configured UserDatabase instance.

    Args:
        client_id: Client identifier for database operations

    Returns:
        UserDatabase: Configured database instance
    """
    config = get_auth_db_config()
    return config.get_user_database(client_id)

def get_backend_type() -> str:
    """
    Get the current database backend type.

    Returns:
        str: "sqlite" or "postgresql"
    """
    config = get_auth_db_config()
    return config.backend_type

def is_postgresql() -> bool:
    """
    Check if using PostgreSQL backend.

    Returns:
        bool: True if using PostgreSQL
    """
    return get_backend_type() in ["postgresql", "postgres"]

def is_sqlite() -> bool:
    """
    Check if using SQLite backend.

    Returns:
        bool: True if using SQLite
    """
    return get_backend_type() == "sqlite"

########################################################################################################################
# Environment Variable Documentation
########################################################################################################################

"""
Environment Variables for AuthNZ Database Configuration:

Common:
    TLDW_USER_DB_BACKEND: Database backend type ("sqlite" or "postgresql")
    TLDW_DB_ECHO: Enable SQL query logging (true/false)
    DATABASE_URL: Full database connection URL

SQLite:
    TLDW_SQLITE_WAL_MODE: Enable WAL mode (true/false, default: true)
    TLDW_SQLITE_FOREIGN_KEYS: Enable foreign keys (true/false, default: true)

PostgreSQL:
    TLDW_PG_HOST: Database host (default: localhost)
    TLDW_PG_PORT: Database port (default: 5432)
    TLDW_PG_DATABASE: Database name (default: tldw_users)
    TLDW_PG_USER: Database user
    TLDW_PG_PASSWORD: Database password
    TLDW_PG_SSLMODE: SSL mode (prefer/require/disable, default: prefer)
    TLDW_DB_POOL_SIZE: Connection pool size (default: 10)
    TLDW_DB_MAX_OVERFLOW: Max overflow connections (default: 20)
    TLDW_DB_POOL_TIMEOUT: Pool timeout in seconds (default: 30)
    TLDW_DB_POOL_RECYCLE: Connection recycle time in seconds (default: 3600)

Examples:

SQLite (Development):
    export TLDW_USER_DB_BACKEND=sqlite
    export DATABASE_URL=sqlite:///./Databases/users.db

PostgreSQL (Production):
    export TLDW_USER_DB_BACKEND=postgresql
    export DATABASE_URL=postgresql://user:password@localhost:5432/tldw_users
    export TLDW_DB_POOL_SIZE=20
"""

#
# End of db_config.py
########################################################################################################################
