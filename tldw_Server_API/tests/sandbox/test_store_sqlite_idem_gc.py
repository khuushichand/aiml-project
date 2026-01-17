from __future__ import annotations

import time as _time


def test_sqlite_idempotency_gc_deletes_expired(tmp_path, monkeypatch) -> None:


    db_path = tmp_path / "sandbox_store.db"
    from tldw_Server_API.app.core.Sandbox.store import SQLiteStore

    store = SQLiteStore(db_path=str(db_path), idem_ttl_sec=60)

    base = _time.time()
    # Insert one old record (older than TTL)
    monkeypatch.setattr("tldw_Server_API.app.core.Sandbox.store.time.time", lambda: base - 120)
    store.store_idempotency(endpoint="gc/test", user_id="u1", key="old", body={"a": 1}, object_id="oid-old", response={"ok": True})
    # Insert one fresh record
    monkeypatch.setattr("tldw_Server_API.app.core.Sandbox.store.time.time", lambda: base)
    store.store_idempotency(endpoint="gc/test", user_id="u1", key="new", body={"b": 2}, object_id="oid-new", response={"ok": True})

    # Run GC; expect to delete exactly one
    deleted = store.gc_idempotency()
    assert deleted == 1

    # Ensure only 'new' remains when listing with a broad window
    items = store.list_idempotency(endpoint="gc/test", limit=10, offset=0)
    keys = [it.get("key") for it in items]
    assert "new" in keys and "old" not in keys
