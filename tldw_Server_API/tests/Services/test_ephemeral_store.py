from __future__ import annotations

import pytest

from tldw_Server_API.app.services.ephemeral_store import EphemeralStorage

pytestmark = pytest.mark.unit


def _clock_holder(start: float = 0.0):
    state = {"now": float(start)}

    def _clock() -> float:
        return float(state["now"])

    return state, _clock


def test_store_and_get_within_ttl() -> None:
    _state, clock = _clock_holder(start=10.0)
    store = EphemeralStorage(default_ttl_seconds=60, max_entries=8, clock=clock)

    eid = store.store_data({"value": 123})
    assert store.get_data(eid) == {"value": 123}

    stats = store.get_stats()
    assert stats["entries"] == 1
    assert stats["max_entries"] == 8


def test_expired_entry_returns_none_and_prunes() -> None:
    state, clock = _clock_holder(start=1.0)
    store = EphemeralStorage(default_ttl_seconds=5, max_entries=8, clock=clock)

    eid = store.store_data({"x": "y"})
    assert store.get_data(eid) == {"x": "y"}

    state["now"] = 7.0
    assert store.get_data(eid) is None
    assert store.get_stats()["entries"] == 0


def test_max_entries_evicts_oldest_first() -> None:
    state, clock = _clock_holder(start=100.0)
    store = EphemeralStorage(default_ttl_seconds=1000, max_entries=2, clock=clock)

    a = store.store_data({"k": "a"})
    state["now"] += 1.0
    b = store.store_data({"k": "b"})
    state["now"] += 1.0
    c = store.store_data({"k": "c"})

    assert store.get_data(a) is None
    assert store.get_data(b) == {"k": "b"}
    assert store.get_data(c) == {"k": "c"}
    assert store.get_stats()["entries"] == 2


def test_remove_data_is_idempotent() -> None:
    _state, clock = _clock_holder(start=42.0)
    store = EphemeralStorage(default_ttl_seconds=60, max_entries=8, clock=clock)
    eid = store.store_data({"id": 1})

    assert store.remove_data(eid) is True
    assert store.remove_data(eid) is False
    assert store.get_data(eid) is None


def test_store_data_rejects_payload_larger_than_max_bytes() -> None:
    _state, clock = _clock_holder(start=5.0)
    store = EphemeralStorage(default_ttl_seconds=60, max_entries=8, max_bytes=16, clock=clock)

    with pytest.raises(ValueError, match="exceeds max_bytes"):
        store.store_data({"x": "y" * 200})

    assert store.get_stats()["entries"] == 0


def test_store_data_returns_retrievable_key_when_within_max_bytes() -> None:
    _state, clock = _clock_holder(start=5.0)
    store = EphemeralStorage(default_ttl_seconds=60, max_entries=8, max_bytes=1024, clock=clock)

    eid = store.store_data({"x": "small"})

    assert store.get_data(eid) == {"x": "small"}
