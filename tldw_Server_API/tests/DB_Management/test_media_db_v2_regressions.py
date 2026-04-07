from tldw_Server_API.app.core.DB_Management.media_db import media_database
from tldw_Server_API.app.core.DB_Management.media_db import native_class


def test_native_media_database_exports_resolve_same_class() -> None:
    assert native_class.MediaDatabase is media_database.MediaDatabase
