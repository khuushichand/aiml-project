import asyncio

import pytest

from tldw_Server_API.app.core.Chat.request_queue import (
    RequestQueue,
    RateLimitedQueue,
    RequestPriority,
    QueuedRequest,
)


@pytest.mark.asyncio
async def test_request_queue_rate_limit_rollback_on_admission_failure():
    queue = RateLimitedQueue(
        max_queue_size=0,
        max_concurrent=1,
        global_rate_limit=5,
        per_client_rate_limit=5,
    )

    with pytest.raises(ValueError):
        await queue.enqueue(
            request_id="req-1",
            request_data={"endpoint": "/api/v1/chat/completions"},
            client_id="client-1",
            priority=RequestPriority.NORMAL,
        )

    assert queue.global_request_times == []
    assert queue.client_request_times.get("client-1") in (None, [])


class _CountingAsyncIterator:
    def __init__(self):
        self.count = 0
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        self.count += 1
        await asyncio.sleep(0)
        return f"chunk-{self.count}"

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_request_queue_stream_cancel_stops_async_iterator():
    queue = RequestQueue(max_queue_size=10, max_concurrent=1)
    # _process_request checks the running flag; set it explicitly for this unit test
    queue._running = True
    stream_channel: asyncio.Queue = asyncio.Queue(maxsize=10)
    async_iter = _CountingAsyncIterator()

    def processor():
        return async_iter

    future: asyncio.Future = asyncio.Future()
    request = QueuedRequest(
        priority=RequestPriority.HIGH.value,
        timestamp=0.0,
        request_id="stream-1",
        request_data={},
        future=future,
        client_id="client-1",
        estimated_tokens=0,
        processor=processor,
        processor_args=(),
        processor_kwargs={},
        streaming=True,
        stream_channel=stream_channel,
    )

    task = asyncio.create_task(queue._process_request(request))

    first = await stream_channel.get()
    assert str(first).startswith("chunk-")

    future.cancel()

    # Drain until sentinel
    while True:
        item = await stream_channel.get()
        if item is None:
            break

    await task

    assert async_iter.closed is True
    assert async_iter.count <= 2

    queue._executor.shutdown(wait=True)
