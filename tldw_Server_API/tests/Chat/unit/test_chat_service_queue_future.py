import asyncio

import pytest

from tldw_Server_API.app.core.Chat import chat_service


@pytest.mark.asyncio
async def test_queue_future_exception_is_consumed(monkeypatch):
    class DummyLogger:
        def __init__(self):
            self.messages = []

        def debug(self, message, *args):
            self.messages.append((message, args))

    dummy_logger = DummyLogger()
    monkeypatch.setattr(chat_service, "logger", dummy_logger)

    fut = asyncio.get_running_loop().create_future()
    chat_service._attach_queue_future_logger(fut, "req-queue-1")
    fut.set_exception(RuntimeError("boom"))

    await asyncio.sleep(0)
    assert dummy_logger.messages
