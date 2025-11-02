# UserDatabase shim
# ------------------
# Legacy imports expect `UserDatabase` in this module. The project now uses the
# backend-aware implementation defined in `UserDatabase_v2`.  This wrapper keeps
# backward compatibility while delegating all behaviour to the new class.

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseBackend,
    DatabaseConfig,
)
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.UserDatabase_v2 import (
    UserDatabase as _UserDatabaseV2,
    UserDatabaseError,
    UserNotFoundError,
    DuplicateUserError,
    InvalidPermissionError,
    RegistrationCodeError,
    AuthenticationError,
)


class UserDatabase(_UserDatabaseV2):
    """Compatibility wrapper that forwards to the v2 backend-aware implementation."""

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        client_id: str = "auth_service",
        *,
        backend: Optional[DatabaseBackend] = None,
        config: Optional[DatabaseConfig] = None,
    ) -> None:
        # If a backend or explicit DatabaseConfig is supplied, honour it.
        if backend is not None or config is not None:
            super().__init__(backend=backend, config=config, client_id=client_id)
            return

        # Legacy callers pass a filesystem path to an SQLite database.
        resolved_path = Path(db_path) if db_path is not None else Path("../Databases/Users.db")
        sqlite_config = DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=str(resolved_path),
        )
        sqlite_backend = DatabaseBackendFactory.create_backend(sqlite_config)
        super().__init__(backend=sqlite_backend, client_id=client_id)


# Re-export exception classes for compatibility.
__all__ = [
    "UserDatabase",
    "UserDatabaseError",
    "UserNotFoundError",
    "DuplicateUserError",
    "InvalidPermissionError",
    "RegistrationCodeError",
    "AuthenticationError",
]
