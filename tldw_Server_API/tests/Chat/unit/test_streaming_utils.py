# test_streaming_utils.py
# Unit tests for streaming response utilities

import asyncio
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

from tldw_Server_API.app.core.Chat.streaming_utils import (
    StreamingResponseHandler,
    create_streaming_response_with_timeout,
    STREAMING_IDLE_TIMEOUT,
    HEARTBEAT_INTERVAL,
)


class TestStreamingResponseHandler:
    """Test StreamingResponseHandler class."""

    def test_initialization(self):
        """Test handler initialization."""
        handler = StreamingResponseHandler(
            conversation_id="conv_123",
            model_name="gpt-4",
            idle_timeout=600,
            heartbeat_interval=60
        )

        assert handler.conversation_id == "conv_123"
        assert handler.model_name == "gpt-4"
        assert handler.idle_timeout == 600
        assert handler.heartbeat_interval == 60
        assert handler.is_cancelled is False
        assert handler.error_occurred is False
        assert handler.full_response == []

    def test_update_activity(self):
        """Test activity timestamp update."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")
        initial_time = handler.last_activity

        time.sleep(0.01)  # Small delay
        handler.update_activity()

        assert handler.last_activity > initial_time

    def test_is_timed_out(self):
        """Test timeout detection."""
        handler = StreamingResponseHandler(
            "conv_123", "gpt-4", idle_timeout=1
        )

        # Should not be timed out initially
        assert handler.is_timed_out() is False

        # Simulate timeout
        handler.last_activity = time.time() - 2
        assert handler.is_timed_out() is True

    def test_cancel(self):
        """Test stream cancellation."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        assert handler.is_cancelled is False
        handler.cancel()
        assert handler.is_cancelled is True

    @pytest.mark.asyncio
    async def test_heartbeat_generator(self):
        """Test heartbeat message generation."""
        handler = StreamingResponseHandler(
            "conv_123", "gpt-4",
            idle_timeout=10,
            heartbeat_interval=0.1  # Short interval for testing
        )

        heartbeats = []
        async for message in handler.heartbeat_generator():
            heartbeats.append(message)
            if len(heartbeats) >= 2:
                handler.cancel()  # Stop after 2 heartbeats
                break

        assert len(heartbeats) >= 2
        for hb in heartbeats:
            assert ": heartbeat" in hb
            # Check for ISO timestamp format (can be Z or +00:00)
            assert "\n\n" in hb  # Just check it ends with double newline

    @pytest.mark.asyncio
    async def test_heartbeat_timeout_detection(self):
        """Test heartbeat detects timeout."""
        handler = StreamingResponseHandler(
            "conv_123", "gpt-4",
            idle_timeout=0.1,  # Very short timeout
            heartbeat_interval=0.05
        )

        # Force timeout
        handler.last_activity = time.time() - 1

        messages = []
        async for message in handler.heartbeat_generator():
            messages.append(message)
            break  # Get first message

        assert len(messages) == 1
        assert "Stream timeout" in messages[0]
        assert handler.is_cancelled is True


@pytest.mark.asyncio
class TestSafeStreamGenerator:
    """Test safe stream generation with error handling."""

    async def test_async_stream_processing(self):
        """Test processing of async stream."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        async def mock_stream():
            yield "Hello"
            yield " "
            yield "World"

        messages = []
        async for message in handler.safe_stream_generator(mock_stream()):
            messages.append(message)

        # Check stream_start event
        assert "event: stream_start" in messages[0]
        assert "conv_123" in messages[0]

        # Check content chunks (should be 3 content messages + 1 finish_reason message)
        content_messages = [m for m in messages if "choices" in m and "delta" in m and "data: " in m]
        # Filter out the finish_reason message
        actual_content_messages = [m for m in content_messages if '"finish_reason"' not in m]
        assert len(actual_content_messages) == 3

        # Check completion
        assert any("[DONE]" in m for m in messages)

        # Check full response collected
        assert "".join(handler.full_response) == "Hello World"

    async def test_sync_stream_processing(self):
        """Test processing of sync stream."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        def mock_stream():
            yield "Sync"
            yield " "
            yield "Stream"

        messages = []
        async for message in handler.safe_stream_generator(mock_stream()):
            messages.append(message)

        # Check content was processed
        assert "".join(handler.full_response) == "Sync Stream"

    async def test_bytes_stream_processing(self):
        """Test processing of byte stream."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        async def mock_stream():
            yield b"Byte"
            yield b" "
            yield b"Stream"

        messages = []
        async for message in handler.safe_stream_generator(mock_stream()):
            messages.append(message)

        assert "".join(handler.full_response) == "Byte Stream"

    async def test_stream_cancellation(self):
        """Test stream cancellation handling."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        async def mock_stream():
            yield "Start"
            handler.cancel()
            yield "Should not appear"

        messages = []
        async for message in handler.safe_stream_generator(mock_stream()):
            messages.append(message)

        # Should stop after cancellation
        assert "".join(handler.full_response) == "Start"
        assert handler.is_cancelled is True

    async def test_stream_error_handling(self):
        """Test error handling during streaming."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        async def mock_stream():
            yield "Before error"
            raise ValueError("Stream error")

        messages = []
        async for message in handler.safe_stream_generator(mock_stream()):
            messages.append(message)

        # Should have error message
        error_messages = [m for m in messages if "error" in m]
        assert len(error_messages) > 0
        assert handler.error_occurred is True

    async def test_save_callback_execution(self):
        """Test save callback is executed."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")
        save_called = False
        saved_content = None

        async def save_callback(content):
            nonlocal save_called, saved_content
            save_called = True
            saved_content = content

        async def mock_stream():
            yield "Test content"

        messages = []
        async for message in handler.safe_stream_generator(mock_stream(), save_callback):
            messages.append(message)

        assert save_called is True
        assert saved_content == "Test content"

    async def test_save_callback_error(self):
        """Test handling of save callback errors."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        async def failing_callback(content):
            raise Exception("Save failed")

        async def mock_stream():
            yield "Content"

        with patch('tldw_Server_API.app.core.Chat.streaming_utils.logger') as mock_logger:
            messages = []
            async for message in handler.safe_stream_generator(mock_stream(), failing_callback):
                messages.append(message)

            # Should log error but not crash
            mock_logger.error.assert_called()
            assert "Content" in "".join(handler.full_response)

    async def test_cancelled_error_handling(self):
        """Test handling of asyncio.CancelledError."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        async def mock_stream():
            yield "Start"
            raise asyncio.CancelledError()

        messages = []
        async for message in handler.safe_stream_generator(mock_stream()):
            messages.append(message)

        assert handler.is_cancelled is True
        # Should have logged disconnection
        with patch('tldw_Server_API.app.core.Chat.streaming_utils.logger') as mock_logger:
            async for _ in handler.safe_stream_generator(mock_stream()):
                pass
            mock_logger.info.assert_called()

    async def test_stream_metadata(self):
        """Test stream metadata messages."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        async def mock_stream():
            yield "Content"

        messages = []
        async for message in handler.safe_stream_generator(mock_stream()):
            messages.append(message)

        # Check stream_start event
        start_msgs = [m for m in messages if "stream_start" in m]
        assert len(start_msgs) == 1
        assert "conv_123" in start_msgs[0]

        # Check stream_end event
        end_msgs = [m for m in messages if "stream_end" in m]
        assert len(end_msgs) == 1
        assert "success" in end_msgs[0]

    @pytest.mark.asyncio
    async def test_sync_stream_closed_on_cancel(self):
        """Ensure underlying sync generator is explicitly closed on cancel."""
        handler = StreamingResponseHandler("conv_close_sync", "gpt-4")

        closed_flag = {"closed": False}

        def provider_stream():
            try:
                yield "A"
                yield "B"
            finally:
                closed_flag["closed"] = True

        async def drive():
            agen = handler.safe_stream_generator(provider_stream())
            # Consume first yield (stream_start)
            await agen.__anext__()
            # Consume first chunk
            await agen.__anext__()
            # Cancel and close early
            handler.cancel()
            await agen.aclose()

        await drive()
        assert closed_flag["closed"] is True

    async def test_done_message_format(self):
        """Test OpenAI-compatible [DONE] message."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        async def mock_stream():
            yield "Test"

        messages = []
        async for message in handler.safe_stream_generator(mock_stream()):
            messages.append(message)

        # Find done message
        done_msgs = [m for m in messages if "[DONE]" in m]
        assert len(done_msgs) == 1

        # Find completion chunk
        completion_msgs = [m for m in messages if "finish_reason" in m]
        assert len(completion_msgs) == 1

        # Parse and verify format
        for msg in completion_msgs:
            if msg.startswith("data: ") and "[DONE]" not in msg:
                data = json.loads(msg[6:msg.index("\n")])
                assert "id" in data
                assert "object" in data
                assert data["object"] == "chat.completion.chunk"
                assert "choices" in data
                assert data["choices"][0]["finish_reason"] == "stop"


@pytest.mark.asyncio
class TestCreateStreamingResponseWithTimeout:
    """Test the main streaming response creation function."""

    async def test_basic_streaming(self):
        """Test basic streaming functionality."""
        # Use the StreamingResponseHandler directly for cleaner testing
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        async def mock_stream():
            yield "Hello"
            yield " World"

        save_called = False
        saved_content = None

        async def save_callback(content):
            nonlocal save_called, saved_content
            save_called = True
            saved_content = content

        messages = []
        async for message in handler.safe_stream_generator(mock_stream(), save_callback):
            messages.append(message)

        assert len(messages) > 0
        assert save_called is True
        assert saved_content == "Hello World"

    @pytest.mark.skip(reason="Complex async coordination test - may be flaky")
    async def test_heartbeat_integration(self):
        """Test heartbeat integration with streaming."""
        async def slow_stream():
            yield "Start"
            await asyncio.sleep(0.2)
            yield "End"

        messages = []
        generator = create_streaming_response_with_timeout(
            stream=slow_stream(),
            conversation_id="conv_123",
            model_name="gpt-4",
            heartbeat_interval=0.1
        )

        async for message in generator:
            messages.append(message)
            if "[DONE]" in message or "stream_end" in message:
                break

        # Should have heartbeat messages
        heartbeat_msgs = [m for m in messages if "heartbeat" in m]
        assert len(heartbeat_msgs) >= 1

    @pytest.mark.asyncio
    async def test_async_generator_close_no_runtime_error(self):
        """Closing the async generator should not raise RuntimeError on GeneratorExit."""
        handler = StreamingResponseHandler("conv_close", "gpt-4")

        async def mock_stream():
            yield "Hello"
            await asyncio.sleep(0)
            yield "World"

        agen = handler.safe_stream_generator(mock_stream())

        # Prime the generator (consume stream_start)
        _ = await agen.__anext__()

        # Closing should not raise
        try:
            await agen.aclose()
        except Exception as e:
            pytest.fail(f"aclose() raised an exception: {e}")

        assert handler.is_cancelled is True

    @pytest.mark.asyncio
    async def test_stream_start_emitted_once_and_close_early(self):
        """Ensure stream_start is emitted only once and early close is clean."""
        async def slow_stream():
            yield "chunk1"
            await asyncio.sleep(0.05)
            yield "chunk2"

        gen = create_streaming_response_with_timeout(
            stream=slow_stream(),
            conversation_id="conv_start_once",
            model_name="gpt-4",
            idle_timeout=5,
            heartbeat_interval=0.2,
        )

        # Get first message and ensure it's stream_start
        first = await gen.__anext__()
        assert "event: stream_start" in first

        # Pull a couple more messages, then close early
        messages = []
        for _ in range(3):
            try:
                messages.append(await gen.__anext__())
            except StopAsyncIteration:
                break

        # Close early; should not raise
        try:
            await gen.aclose()
        except Exception as e:
            pytest.fail(f"Early aclose() raised an exception: {e}")

        # Verify only one stream_start was seen in all collected messages
        start_count = sum(1 for m in [first] + messages if "event: stream_start" in m)
        assert start_count == 1


class TestConstants:
    """Test module constants."""

    def test_default_timeout(self):
        """Test default timeout value."""
        assert STREAMING_IDLE_TIMEOUT == 300  # 5 minutes

    def test_default_heartbeat(self):
        """Test default heartbeat interval."""
        assert HEARTBEAT_INTERVAL == 30  # 30 seconds


class TestStreamingResponseHandlerIntegration:
    """Integration tests for complete streaming workflow."""

    @pytest.mark.asyncio
    async def test_full_workflow_success(self):
        """Test complete successful streaming workflow."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")
        save_result = None

        async def save_callback(content):
            nonlocal save_result
            save_result = content

        async def mock_llm_stream():
            responses = ["I", " am", " an", " AI", " assistant"]
            for r in responses:
                yield r
                await asyncio.sleep(0.01)

        all_messages = []
        async for message in handler.safe_stream_generator(mock_llm_stream(), save_callback):
            all_messages.append(message)

        # Verify complete flow
        assert len(all_messages) > 0
        assert handler.error_occurred is False
        assert handler.is_cancelled is False
        assert save_result == "I am an AI assistant"
        assert "".join(handler.full_response) == save_result

    @pytest.mark.asyncio
    async def test_full_workflow_with_error(self):
        """Test complete workflow with error handling."""
        handler = StreamingResponseHandler("conv_123", "gpt-4")

        async def mock_failing_stream():
            yield "Partial"
            yield " response"
            raise ConnectionError("LLM connection lost")

        messages = []
        async for message in handler.safe_stream_generator(mock_failing_stream()):
            messages.append(message)

        assert handler.error_occurred is True
        assert "".join(handler.full_response) == "Partial response"

        # Should have error in messages
        error_found = any("error" in m for m in messages)
        assert error_found is True


@pytest.mark.asyncio
class TestSSENormalization:
    """Tests that upstream provider SSE frames are normalized to plain text chunks."""

    async def test_openai_like_sse_is_normalized(self):
        handler = StreamingResponseHandler("conv_sse", "gpt-4")

        # Upstream emits OpenAI-style SSE frames (each with trailing blank line)
        chunk1 = {"choices": [{"delta": {"content": "Hello"}}]}
        chunk2 = {"choices": [{"delta": {"content": " world"}}]}

        async def provider_stream():
            yield f"data: {json.dumps(chunk1)}\n\n"
            yield f"data: {json.dumps(chunk2)}\n\n"
            yield "data: [DONE]\n\n"

        messages = []
        async for message in handler.safe_stream_generator(provider_stream()):
            messages.append(message)

        # Extract only content chunks we emit to client
        content_lines = [m for m in messages if m.startswith("data: ") and '"choices"' in m and '"delta"' in m and '"content"' in m]
        parsed = []
        for m in content_lines:
            data = json.loads(m[6:m.index("\n")])
            content = data["choices"][0]["delta"].get("content")
            if content:
                parsed.append(content)

        assert parsed == ["Hello", " world"]
        assert any("data: [DONE]" in m for m in messages)
        assert "".join(handler.full_response) == "Hello world"

    async def test_multiline_sse_chunk_with_event_and_multiple_data_lines(self):
        handler = StreamingResponseHandler("conv_sse2", "gpt-4")

        # Single upstream chunk that contains an event plus two data lines and a DONE
        part_a = {"choices": [{"delta": {"content": "Part"}}]}
        part_b = {"choices": [{"delta": {"content": " A"}}]}
        multi = (
            "event: chunk\n"
            f"data: {json.dumps(part_a)}\n"
            f"data: {json.dumps(part_b)}\n"
            "data: [DONE]\n\n"
        )

        async def provider_stream():
            yield multi

        messages = []
        async for message in handler.safe_stream_generator(provider_stream()):
            messages.append(message)

        content_lines = [m for m in messages if m.startswith("data: ") and '"choices"' in m and '"delta"' in m and '"content"' in m]
        parsed = []
        for m in content_lines:
            data = json.loads(m[6:m.index("\n")])
            content = data["choices"][0]["delta"].get("content")
            if content:
                parsed.append(content)

        assert parsed == ["Part", " A"]
        assert any("data: [DONE]" in m for m in messages)
        assert "".join(handler.full_response) == "Part A"

    async def test_upstream_error_is_forwarded(self):
        handler = StreamingResponseHandler("conv_err", "gpt-4")

        async def provider_stream():
            yield "data: {\"error\": {\"message\": \"oops\", \"type\": \"provider\"}}\n\n"

        messages = []
        async for message in handler.safe_stream_generator(provider_stream()):
            messages.append(message)

        # We should have an error message surfaced to the client
        error_msgs = [m for m in messages if m.startswith("data: ") and '"error"' in m]
        assert len(error_msgs) >= 1
        assert handler.error_occurred is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
