"""Unit tests for the in-memory chat loop event store."""

from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Chat.chat_loop_store import InMemoryChatLoopStore


@pytest.mark.unit
def test_store_replays_events_after_seq_cursor() -> None:
    store = InMemoryChatLoopStore()
    store.append("run_1", "run_started", {"ok": True})
    store.append("run_1", "llm_chunk", {"text": "Hi"})

    tail = store.list_after("run_1", 1)
    assert len(tail) == 1
    assert tail[0].event == "llm_chunk"
    assert tail[0].seq == 2


@pytest.mark.unit
def test_store_sequences_are_monotonic_per_run() -> None:
    store = InMemoryChatLoopStore()
    first = store.append("run_1", "run_started", {})
    second = store.append("run_1", "llm_chunk", {"text": "A"})
    third = store.append("run_1", "llm_complete", {"text": "AB"})

    assert [first.seq, second.seq, third.seq] == [1, 2, 3]


@pytest.mark.unit
def test_store_keeps_runs_isolated() -> None:
    store = InMemoryChatLoopStore()
    store.append("run_1", "run_started", {})
    store.append("run_2", "run_started", {})
    store.append("run_2", "llm_chunk", {"text": "X"})

    run1_events = store.list_after("run_1", 0)
    run2_events = store.list_after("run_2", 0)
    assert len(run1_events) == 1
    assert len(run2_events) == 2
