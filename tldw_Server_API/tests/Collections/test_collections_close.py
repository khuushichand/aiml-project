import shutil
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseError


pytestmark = pytest.mark.unit


def test_close_closes_owned_sqlite_backend_pool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "test_user_dbs_collections_close"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    try:
        collections_db = CollectionsDatabase.for_user(user_id=778)
        pool = collections_db.backend.get_pool()
        pool.get_connection()

        collections_db.close()

        with pytest.raises(DatabaseError, match="Connection pool is closed"):
            pool.get_connection()
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass
