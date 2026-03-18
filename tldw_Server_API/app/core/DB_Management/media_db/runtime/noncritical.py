"""Shared noncritical exception tuples for Media DB integrations."""

from __future__ import annotations

import json
import sqlite3

import yaml

from tldw_Server_API.app.core.DB_Management.backends.base import (
    DatabaseError as BackendDatabaseError,
)
from tldw_Server_API.app.core.DB_Management.db_migration import MigrationError
from tldw_Server_API.app.core.DB_Management.media_db.errors import (
    ConflictError,
    DatabaseError,
    InputError,
)


MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    AttributeError,
    BackendDatabaseError,
    ConflictError,
    DatabaseError,
    InputError,
    MigrationError,
    KeyError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
    json.JSONDecodeError,
    sqlite3.Error,
    yaml.YAMLError,
)


__all__ = ["MEDIA_NONCRITICAL_EXCEPTIONS"]
