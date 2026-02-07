import asyncio

import pytest

from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint


def _system_lock_keys_for_loop(loop: asyncio.AbstractEventLoop) -> set[str]:
    with chat_endpoint._system_message_guard:
        per_loop = chat_endpoint._system_message_locks.get(loop)
        if not per_loop:
            return set()
        return set(per_loop.keys())


@pytest.mark.asyncio
async def test_system_message_lock_cache_entry_released_after_persist():
    class _FakeDB:
        def has_system_message_for_conversation(self, _conversation_id: str) -> bool:
            return False

        def get_conversation_by_id(self, _conversation_id: str) -> dict[str, str]:
            return {"created_at": "2026-01-01T00:00:00Z"}

    async def _save_message(_db, _conversation_id: str, _payload: dict, use_transaction: bool = True):
        assert use_transaction is True
        return "msg-1"

    loop = asyncio.get_running_loop()
    baseline = _system_lock_keys_for_loop(loop)

    result = await chat_endpoint._persist_system_message_if_needed(
        db=_FakeDB(),
        conversation_id="conv-lock-release-1",
        system_message="System prompt",
        save_message_fn=_save_message,
        loop=loop,
    )

    assert result == "msg-1"
    assert _system_lock_keys_for_loop(loop) == baseline


@pytest.mark.asyncio
async def test_system_message_lock_cache_entry_released_when_save_fails():
    class _FakeDB:
        def has_system_message_for_conversation(self, _conversation_id: str) -> bool:
            return False

        def get_conversation_by_id(self, _conversation_id: str) -> dict[str, str]:
            return {"created_at": "2026-01-01T00:00:00Z"}

    async def _failing_save(_db, _conversation_id: str, _payload: dict, use_transaction: bool = True):
        assert use_transaction is True
        raise RuntimeError("save failed")

    loop = asyncio.get_running_loop()
    baseline = _system_lock_keys_for_loop(loop)

    result = await chat_endpoint._persist_system_message_if_needed(
        db=_FakeDB(),
        conversation_id="conv-lock-release-2",
        system_message="System prompt",
        save_message_fn=_failing_save,
        loop=loop,
    )

    assert result is None
    assert _system_lock_keys_for_loop(loop) == baseline
