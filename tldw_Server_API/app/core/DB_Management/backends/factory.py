"""
Database backend factory for creating and managing database backends.

This module provides a factory pattern implementation for creating
database backend instances based on configuration.
"""

import os
from typing import Dict, Optional, Type
from loguru import logger

from .base import DatabaseBackend, DatabaseConfig, BackendType, DatabaseError
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from .sqlite_backend import SQLiteBackend

# Try to import PostgreSQL backend if available
try:
    from .postgresql_backend import PostgreSQLBackend
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False


# Registry of available backends
_BACKEND_REGISTRY: Dict[BackendType, Type[DatabaseBackend]] = {
    BackendType.SQLITE: SQLiteBackend,
}

# Register PostgreSQL if available
if POSTGRESQL_AVAILABLE:
    _BACKEND_REGISTRY[BackendType.POSTGRESQL] = PostgreSQLBackend

# Global backend instances cache
_backend_instances: Dict[str, DatabaseBackend] = {}


class DatabaseBackendFactory:
    """Factory for creating database backend instances."""

    @staticmethod
    def create_backend(config: DatabaseConfig) -> DatabaseBackend:
        """
        Create a database backend instance based on configuration.

        Args:
            config: Database configuration

        Returns:
            DatabaseBackend instance

        Raises:
            DatabaseError: If backend type is not supported
        """
        backend_type = config.backend_type

        if backend_type not in _BACKEND_REGISTRY:
            raise DatabaseError(f"Unsupported backend type: {backend_type}")

        backend_class = _BACKEND_REGISTRY[backend_type]
        logger.info(f"Creating {backend_type.value} backend")

        return backend_class(config)


class BackendFactory:
    """
    Backward-compatible alias used by some tests/utilities.

    Provides a stricter type check that raises ValueError when an invalid
    backend type string is provided in the config.
    """

    @staticmethod
    def create_backend(config: DatabaseConfig) -> DatabaseBackend:
        bt = config.backend_type
        # Coerce string backend types to enum, raising ValueError on invalid input
        if isinstance(bt, str):
            try:
                config.backend_type = BackendType(bt)
            except ValueError as e:
                # Match expected behavior in tests
                raise ValueError(f"Invalid backend type: {bt}") from e
        return DatabaseBackendFactory.create_backend(config)

    @staticmethod
    def create_from_env(
        backend_type: Optional[str] = None,
        config_overrides: Optional[Dict] = None
    ) -> DatabaseBackend:
        """
        Create a backend from environment variables.

        Args:
            backend_type: Override backend type (default from env)
            config_overrides: Additional config overrides

        Returns:
            DatabaseBackend instance
        """
        # Determine backend type
        if backend_type is None:
            backend_type = os.getenv("TLDW_DB_BACKEND", "sqlite").lower()

        try:
            backend_enum = BackendType(backend_type)
        except ValueError:
            raise DatabaseError(f"Invalid backend type: {backend_type}")

        # Build configuration from environment
        config = DatabaseConfig(backend_type=backend_enum)

        # SQLite configuration
        if backend_enum == BackendType.SQLITE:
            config.sqlite_path = os.getenv(
                "TLDW_SQLITE_PATH",
                str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
            )
            config.sqlite_wal_mode = os.getenv(
                "TLDW_SQLITE_WAL_MODE", "true"
            ).lower() == "true"
            config.sqlite_foreign_keys = os.getenv(
                "TLDW_SQLITE_FOREIGN_KEYS", "true"
            ).lower() == "true"

        # PostgreSQL configuration (future)
        elif backend_enum == BackendType.POSTGRESQL:
            config.pg_host = os.getenv("TLDW_PG_HOST", "localhost")
            config.pg_port = int(os.getenv("TLDW_PG_PORT", "5432"))
            config.pg_database = os.getenv("TLDW_PG_DATABASE", "tldw")
            config.pg_user = os.getenv("TLDW_PG_USER", "tldw_user")
            config.pg_password = os.getenv("TLDW_PG_PASSWORD", "")
            config.pg_sslmode = os.getenv("TLDW_PG_SSLMODE", "prefer")

        # Common configuration
        config.pool_size = int(os.getenv("TLDW_DB_POOL_SIZE", "10"))
        config.pool_timeout = float(os.getenv("TLDW_DB_POOL_TIMEOUT", "30.0"))
        config.echo = os.getenv("TLDW_DB_ECHO", "false").lower() == "true"

        # Apply overrides
        if config_overrides:
            for key, value in config_overrides.items():
                if hasattr(config, key):
                    setattr(config, key, value)

        return DatabaseBackendFactory.create_backend(config)

    @staticmethod
    def create_from_config_file(
        config_path: str,
        backend_override: Optional[str] = None
    ) -> DatabaseBackend:
        """
        Create a backend from a configuration file.

        Args:
            config_path: Path to configuration file
            backend_override: Override backend type from config

        Returns:
            DatabaseBackend instance
        """
        import yaml

        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        db_config = config_data.get('database', {})

        # Determine backend type
        backend_type_str = backend_override or db_config.get('backend', 'sqlite')

        try:
            backend_type = BackendType(backend_type_str)
        except ValueError:
            raise DatabaseError(f"Invalid backend type: {backend_type_str}")

        config = DatabaseConfig(backend_type=backend_type)

        # Load backend-specific configuration
        if backend_type == BackendType.SQLITE:
            sqlite_config = db_config.get('sqlite', {})
            config.sqlite_path = sqlite_config.get(
                'path', str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
            )
            config.sqlite_wal_mode = sqlite_config.get('wal_mode', True)
            config.sqlite_foreign_keys = sqlite_config.get('foreign_keys', True)

        elif backend_type == BackendType.POSTGRESQL:
            pg_config = db_config.get('postgresql', {})
            config.pg_host = pg_config.get('host', 'localhost')
            config.pg_port = pg_config.get('port', 5432)
            config.pg_database = pg_config.get('database', 'tldw')
            config.pg_user = pg_config.get('user', 'tldw_user')
            config.pg_password = pg_config.get('password', '')
            config.pg_sslmode = pg_config.get('sslmode', 'prefer')
            config.pool_size = pg_config.get('pool_size', 20)
            config.max_overflow = pg_config.get('max_overflow', 40)

        return DatabaseBackendFactory.create_backend(config)


def register_backend(backend_type: BackendType, backend_class: Type[DatabaseBackend]) -> None:
    """
    Register a new backend implementation.

    Args:
        backend_type: Backend type enum
        backend_class: Backend implementation class
    """
    _BACKEND_REGISTRY[backend_type] = backend_class
    logger.info(f"Registered backend: {backend_type.value}")


def get_backend(
    name: str = "default",
    config: Optional[DatabaseConfig] = None,
    create_if_missing: bool = True
) -> Optional[DatabaseBackend]:
    """
    Get or create a named backend instance.

    This function provides a singleton pattern for backend instances,
    ensuring that the same backend instance is reused across the application.

    Args:
        name: Backend instance name
        config: Configuration for creating new instance
        create_if_missing: Create instance if it doesn't exist

    Returns:
        DatabaseBackend instance or None
    """
    global _backend_instances

    if name in _backend_instances:
        return _backend_instances[name]

    if not create_if_missing:
        return None

    if config is None:
        # Try to create from environment
        backend = DatabaseBackendFactory.create_from_env()
    else:
        backend = DatabaseBackendFactory.create_backend(config)

    _backend_instances[name] = backend
    return backend


def close_all_backends() -> None:
    """Close all backend instances and clear the cache."""
    global _backend_instances

    for name, backend in _backend_instances.items():
        try:
            if hasattr(backend, '_pool') and backend._pool:
                backend._pool.close_all()
            logger.info(f"Closed backend: {name}")
        except Exception as e:
            logger.error(f"Error closing backend {name}: {e}")

    _backend_instances.clear()


# Convenience function for getting default backend
def get_default_backend() -> DatabaseBackend:
    """
    Get the default database backend.

    Returns:
        Default DatabaseBackend instance
    """
    return get_backend("default")
