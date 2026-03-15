"""Backend-dispatched schema bootstrap entrypoint for Media DB."""

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.schema.backends.postgres import (
    initialize_postgres_schema,
)
from tldw_Server_API.app.core.DB_Management.media_db.schema.backends.sqlite import (
    initialize_sqlite_schema,
)


def ensure_media_schema(db) -> None:
    """Dispatch schema bootstrap to the active backend implementation."""

    if db.backend_type == BackendType.SQLITE:
        initialize_sqlite_schema(db)
        return
    if db.backend_type == BackendType.POSTGRESQL:
        initialize_postgres_schema(db)
        return
    raise NotImplementedError(f"Schema initialization not implemented for backend {db.backend_type}")
