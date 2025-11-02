"""
Database backend abstraction layer for supporting multiple database systems.

This module provides a unified interface for database operations, allowing
the application to work with different database backends (SQLite, PostgreSQL, etc.)
without changing the application code.
"""

from .base import (
    DatabaseBackend,
    DatabaseConfig,
    ConnectionPool,
    QueryResult,
    FTSQuery,
    BackendFeatures,
    DatabaseError,
    NotSupportedError
)

from .factory import (
    DatabaseBackendFactory,
    BackendFactory,
    get_backend,
    register_backend
)

__all__ = [
    # Base classes
    'DatabaseBackend',
    'DatabaseConfig',
    'ConnectionPool',
    'QueryResult',
    'FTSQuery',
    'BackendFeatures',
    'DatabaseError',
    'NotSupportedError',

    # Factory
    'DatabaseBackendFactory',
    'BackendFactory',
    'get_backend',
    'register_backend'
]
