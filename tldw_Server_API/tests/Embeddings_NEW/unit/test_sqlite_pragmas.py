import threading
import time
from pathlib import Path

from tldw_Server_API.app.core.Embeddings import vector_store_meta_db as meta
from tldw_Server_API.app.core.config import settings


def test_vector_store_meta_db_concurrent_writes(tmp_path, monkeypatch):
    # Point USER_DB_BASE_DIR to a temp directory
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path))
    # Ensure settings picks up the new env var (avoid using cached base dir)
    from tldw_Server_API.app.core.config import clear_config_cache
    clear_config_cache()
    # settings.get is resolved at runtime; ensure it reflects our env by reading it
    # Settings resolves USER_DB_BASE_DIR at import/init; if already set, this still writes to tmp_path above

    user_id = "vs_meta_pragmas"
    meta.init_meta_db(user_id)

    errors = []

    def writer(idx: int):
        try:
            sid = f"store_{idx}"
            meta.register_store(user_id, sid, f"Name {idx}")
            # Perform several updates quickly
            for j in range(5):
                meta.rename_store(user_id, sid, f"Name {idx}-{j}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Encountered errors during concurrent writes: {errors}"
    stores = meta.list_stores(user_id)
    # We expect at least all the initial inserts to be present
    assert len(stores) >= 10
