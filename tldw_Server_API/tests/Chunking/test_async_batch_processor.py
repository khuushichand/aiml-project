import asyncio

import pytest

from tldw_Server_API.app.core.Chunking.async_chunker import AsyncBatchProcessor


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_batch_processor_task_done_and_eviction() -> None:
    processor = AsyncBatchProcessor(batch_size=2, max_concurrent=1, max_results=2)

    await processor.add_request("r1", "one two three", method="words", max_size=2, overlap=0)
    await processor.add_request("r2", "four five six", method="words", max_size=2, overlap=0)
    await processor.add_request("r3", "seven eight nine", method="words", max_size=2, overlap=0)

    # Process until queue is drained
    await processor.process_batch()
    await processor.process_batch()

    # Ensure task_done was called for all items (queue.join should not hang)
    await asyncio.wait_for(processor._queue.join(), timeout=1.0)

    # Oldest result should be evicted when max_results is exceeded
    assert processor.get_result("r1") is None
    assert processor.get_result("r2") is not None
    assert processor.get_result("r3") is not None

    await processor.stop_processing()
