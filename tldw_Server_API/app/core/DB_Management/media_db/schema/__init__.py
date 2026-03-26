"""Schema bootstrap surface for the incremental Media DB package."""

from tldw_Server_API.app.core.DB_Management.media_db.schema.bootstrap import (
    ensure_media_schema,
)
from tldw_Server_API.app.core.DB_Management.media_db.schema import (
    postgres_data_table_structures,
)
from tldw_Server_API.app.core.DB_Management.media_db.schema import (
    postgres_tts_source_hash_structures,
)

__all__ = [
    "ensure_media_schema",
    "postgres_data_table_structures",
    "postgres_tts_source_hash_structures",
]
