from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.core.Sandbox.store import SQLiteStore, InMemoryStore


def _z(dt: datetime) -> str:
    """Return an ISO 8601 string with trailing 'Z'."""
    # Ensure timezone-aware UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def test_sqlite_idempotency_filters_accept_z_suffix(tmp_path) -> None:
    db_path = tmp_path / "sandbox_store.db"
    store = SQLiteStore(db_path=str(db_path), idem_ttl_sec=600)

    # Insert a sample idempotency record (created_at is set internally to time.time())
    store.store_idempotency(
        endpoint="/api/test",
        user_id="user-1",
        key="k1",
        body={"a": 1},
        object_id="obj-1",
        response={"ok": True},
    )

    # Build Z-suffixed ISO filters that should include the above record
    from_iso = _z(datetime.now(timezone.utc) - timedelta(minutes=5))
    to_iso = _z(datetime.now(timezone.utc) + timedelta(minutes=5))

    items = store.list_idempotency(
        endpoint=None,
        user_id=None,
        key=None,
        created_at_from=from_iso,
        created_at_to=to_iso,
        limit=50,
        offset=0,
        sort_desc=True,
    )
    assert isinstance(items, list)
    assert len(items) >= 1

    cnt = store.count_idempotency(
        endpoint=None,
        user_id=None,
        key=None,
        created_at_from=from_iso,
        created_at_to=to_iso,
    )
    assert isinstance(cnt, int)
    assert cnt >= 1


@pytest.mark.parametrize("bad", ["not-a-time", "2021-13-99T25:61:61Z", "", None])
def test_sqlite_idempotency_filters_invalid_inputs_raise(tmp_path, bad) -> None:
    db_path = tmp_path / "sandbox_store.db"
    store = SQLiteStore(db_path=str(db_path), idem_ttl_sec=600)

    # Ensure store is initialized with no records; calling with invalid filters should raise
    if bad is None:
        # count/list signatures expect Optional[str]; pass None should simply be ignored
        # and not raise. So skip None for the negative test.
        pytest.skip("None is not an invalid value; filter is omitted")

    with pytest.raises(ValueError):
        store.list_idempotency(created_at_from=bad)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        store.count_idempotency(created_at_to=bad)  # type: ignore[arg-type]


def test_memory_idempotency_filters_accept_z_suffix() -> None:
    store = InMemoryStore(idem_ttl_sec=600)

    # Insert a sample idempotency record
    store.store_idempotency(
        endpoint="/api/test",
        user_id="user-1",
        key="k1",
        body={"a": 1},
        object_id="obj-1",
        response={"ok": True},
    )

    from_iso = _z(datetime.now(timezone.utc) - timedelta(minutes=5))
    to_iso = _z(datetime.now(timezone.utc) + timedelta(minutes=5))

    items = store.list_idempotency(
        endpoint=None,
        user_id=None,
        key=None,
        created_at_from=from_iso,
        created_at_to=to_iso,
        limit=50,
        offset=0,
        sort_desc=True,
    )
    assert isinstance(items, list)
    assert len(items) >= 1

    cnt = store.count_idempotency(
        endpoint=None,
        user_id=None,
        key=None,
        created_at_from=from_iso,
        created_at_to=to_iso,
    )
    assert isinstance(cnt, int)
    assert cnt >= 1


@pytest.mark.parametrize("bad", ["not-a-time", "2021-13-99T25:61:61Z", "", None])
def test_memory_idempotency_filters_invalid_inputs_ignored(bad) -> None:
    store = InMemoryStore(idem_ttl_sec=600)

    # Insert one record so results are non-empty when filters are ignored
    store.store_idempotency(
        endpoint="/api/test",
        user_id="user-1",
        key="k1",
        body={"a": 1},
        object_id="obj-1",
        response={"ok": True},
    )

    if bad is None:
        pytest.skip("None is not invalid; filter is omitted")

    # InMemory store ignores invalid ISO filters; should not raise and should return data
    items = store.list_idempotency(created_at_from=bad)  # type: ignore[arg-type]
    assert isinstance(items, list)
    assert len(items) >= 1

    cnt = store.count_idempotency(created_at_to=bad)  # type: ignore[arg-type]
    assert isinstance(cnt, int)
    assert cnt >= 1
