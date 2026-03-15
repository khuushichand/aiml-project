"""Unit tests for chat loop store compaction/replay behavior."""

from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Chat.chat_loop_store import InMemoryChatLoopStore


@pytest.mark.unit
def test_loop_store_compaction_retains_checkpoint_and_tail() -> None:
    store = InMemoryChatLoopStore()
    for i in range(1000):
        store.append("run_1", "llm_chunk", {"i": i})

    checkpoint = store.compact("run_1", keep_tail=100)
    assert checkpoint is not None
    assert checkpoint.last_seq >= 1000
    assert checkpoint.checkpoint_seq >= 900

    rebuilt = store.replay("run_1")
    assert rebuilt is not None
    assert rebuilt.last_seq >= 1000
    assert len(rebuilt.tail_events) == 100


@pytest.mark.unit
def test_loop_store_append_after_compaction_keeps_monotonic_seq() -> None:
    store = InMemoryChatLoopStore()
    for i in range(8):
        store.append("run_2", "llm_chunk", {"i": i})
    store.compact("run_2", keep_tail=3)

    event = store.append("run_2", "run_complete", {})
    assert event.seq == 9
