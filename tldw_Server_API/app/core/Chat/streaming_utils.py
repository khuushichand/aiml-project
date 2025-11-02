# streaming_utils.py
# Description: Utilities for handling streaming responses safely
#
# Imports
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Iterator, Optional, Union, Tuple, List
from loguru import logger

#######################################################################################################################
#
# Constants:

# Load configuration values
from tldw_Server_API.app.core.config import load_comprehensive_config

_config = load_comprehensive_config()
# ConfigParser uses sections, check if Chat-Module section exists
_chat_config = {}
if _config and _config.has_section('Chat-Module'):
    _chat_config = dict(_config.items('Chat-Module'))

# Timeout for idle connections (seconds)
STREAMING_IDLE_TIMEOUT = int(_chat_config.get('streaming_idle_timeout_seconds', 300))  # Default 5 minutes

# Heartbeat interval for long-running streams (seconds)
HEARTBEAT_INTERVAL = int(_chat_config.get('streaming_heartbeat_interval_seconds', 30))

#######################################################################################################################
#
# Functions:

def _extract_text_from_upstream_sse(chunk_str: str) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
    """
    Normalize provider-emitted SSE frames to plain text content.

    Accepts a string that may be:
      - a raw text fragment (returns it as text_content)
      - an SSE line like "data: {...}" (extracts JSON and returns delta.content if present)
      - an SSE DONE line "data: [DONE]" (signals completion via is_done=True)

    Returns: (text_content, error_payload, is_done)
      - text_content: extracted textual delta (or original text) or None
      - error_payload: if upstream provided an error object, return it for direct emission
      - is_done: True if upstream indicated [DONE]
    """
    if not chunk_str:
        return None, None, False

    # Normalize common invisible prefixes (BOM, zero-width spaces) and trim whitespace
    s = chunk_str.lstrip("\ufeff\u200b\u200c\u200d\u2060").strip()

    # Ignore comment/heartbeat/event-only lines from upstream
    if s.startswith(":") or s.startswith("event:"):
        return None, None, False

    # If any 'data:' line exists, try to parse; some providers send 'event:' + 'data:' pairs or multiple frames
    if s.startswith("data:") or ("\ndata:" in s or s.startswith("event:") or "data:" in s):
        saw_done = False
        first_error = None
        # Process by lines to handle possible multi-line chunks
        for line in s.splitlines():
            ls = line.lstrip("\ufeff\u200b\u200c\u200d\u2060").strip()
            if not ls:
                continue
            if ls.startswith(":") or ls.startswith("event:"):
                # Skip comment or event name lines
                continue
            if not ls.startswith("data:"):
                continue
            payload_str = ls[len("data:"):].strip()
            if payload_str == "[DONE]":
                saw_done = True
                continue
            try:
                data = json.loads(payload_str)
            except Exception:
                # Try next line if present
                continue

            if isinstance(data, dict) and "error" in data and first_error is None:
                try:
                    _ = json.dumps({"error": data.get("error")})
                    first_error = {"error": data.get("error")}
                except Exception:
                    first_error = {"error": {"message": "Upstream error (unparseable)", "type": "stream_error"}}
                continue

            if isinstance(data, dict):
                choices = data.get("choices")
                if isinstance(choices, list) and choices:
                    first = choices[0] or {}
                    delta = first.get("delta") or {}
                    content = delta.get("content")
                    if content:
                        return str(content), None, False
                    # Fallback to message.content (non-stream case)
                    message = first.get("message") or {}
                    msg_content = message.get("content")
                    if msg_content:
                        return str(msg_content), None, False
        # If no content found but DONE or error encountered, reflect that
        if first_error is not None:
            return None, first_error, False
        if saw_done:
            return None, None, True
        return None, None, False

    # Not an SSE frame; treat as plain text chunk
    return chunk_str, None, False

class StreamingResponseHandler:
    """
    Handles streaming responses with proper error handling, cleanup, and timeouts.
    """

    def __init__(
        self,
        conversation_id: str,
        model_name: str,
        idle_timeout: int = STREAMING_IDLE_TIMEOUT,
        heartbeat_interval: int = HEARTBEAT_INTERVAL,
        max_response_size: int = 10 * 1024 * 1024,  # 10MB default
        text_transform: Optional[callable] = None,
    ):
        """
        Initialize the streaming response handler.

        Args:
            conversation_id: ID of the conversation
            model_name: Name of the model being used
            idle_timeout: Timeout for idle connections in seconds
            heartbeat_interval: Interval for sending heartbeat messages
            max_response_size: Maximum response size in bytes
        """
        self.conversation_id = conversation_id
        self.model_name = model_name
        self.idle_timeout = idle_timeout
        self.heartbeat_interval = heartbeat_interval
        self.max_response_size = max_response_size
        self.last_activity = time.time()
        self.is_cancelled = False
        self.full_response = []
        self.response_size = 0
        self.error_occurred = False
        # Optional transform to apply to textual deltas before emission (e.g., moderation redaction)
        self.text_transform = text_transform
        # Track whether a terminal [DONE] was already sent (directly or via transform-combined payload)
        self.done_sent = False
        # Accumulate tool/function call deltas for persistence once the stream completes
        self.tool_call_accumulator: Dict[int, Dict[str, Any]] = {}
        self.tool_call_order: List[int] = []
        self.function_call_accumulator: Optional[Dict[str, Any]] = None

    def update_activity(self):
        """Update the last activity timestamp."""
        self.last_activity = time.time()

    def is_timed_out(self) -> bool:
        """Check if the stream has timed out due to inactivity."""
        return (time.time() - self.last_activity) > self.idle_timeout

    def cancel(self):
        """Mark the stream as cancelled."""
        self.is_cancelled = True
        logger.info(f"Stream cancelled for conversation {self.conversation_id}")

    def _accumulate_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> None:
        """Merge incremental tool call deltas into a final structure."""
        if not isinstance(tool_calls, list):
            return
        for idx, entry in enumerate(tool_calls):
            if not isinstance(entry, dict):
                continue
            call_index = entry.get("index")
            if call_index is None:
                call_index = idx
            try:
                call_index = int(call_index)
            except Exception:
                call_index = idx
            if call_index not in self.tool_call_accumulator:
                self.tool_call_accumulator[call_index] = {
                    "id": None,
                    "type": None,
                    "function": {"name": None, "arguments": ""},
                }
                self.tool_call_order.append(call_index)
            accumulator = self.tool_call_accumulator[call_index]
            if entry.get("id"):
                accumulator["id"] = entry["id"]
            if entry.get("type"):
                accumulator["type"] = entry["type"]
            function_delta = entry.get("function") or {}
            if function_delta.get("name"):
                accumulator["function"]["name"] = function_delta["name"]
            if function_delta.get("arguments"):
                accumulator["function"]["arguments"] += function_delta["arguments"]

    def _accumulate_function_call(self, function_delta: Dict[str, Any]) -> None:
        """Merge incremental function call deltas into a final structure."""
        if not isinstance(function_delta, dict):
            return
        if self.function_call_accumulator is None:
            self.function_call_accumulator = {"name": None, "arguments": ""}
        if function_delta.get("name"):
            self.function_call_accumulator["name"] = function_delta["name"]
        if function_delta.get("arguments"):
            self.function_call_accumulator["arguments"] += function_delta["arguments"]

    def get_accumulated_tool_calls(self) -> Optional[List[Dict[str, Any]]]:
        """Return the finalized list of tool calls, if any were streamed."""
        if not self.tool_call_accumulator:
            return None
        ordered_indices = sorted(set(self.tool_call_order))
        results: List[Dict[str, Any]] = []
        for index in ordered_indices:
            data = self.tool_call_accumulator.get(index)
            if not data:
                continue
            function_block = data.get("function") or {}
            results.append(
                {
                    "id": data.get("id"),
                    "type": data.get("type"),
                    "function": {
                        "name": function_block.get("name"),
                        "arguments": function_block.get("arguments", ""),
                    },
                }
            )
        return results or None

    def get_accumulated_function_call(self) -> Optional[Dict[str, Any]]:
        """Return the finalized function call payload, if one was streamed."""
        if not self.function_call_accumulator:
            return None
        name = self.function_call_accumulator.get("name")
        arguments = self.function_call_accumulator.get("arguments", "")
        if not name and not arguments:
            return None
        return {"name": name, "arguments": arguments}

    def has_accumulated_output(self) -> bool:
        """Return True when any text, tool calls, or function calls were gathered."""
        return bool(
            self.full_response
            or self.tool_call_accumulator
            or self.function_call_accumulator
        )

    async def heartbeat_generator(self) -> AsyncIterator[str]:
        """
        Generate heartbeat messages to keep the connection alive.

        Yields:
            SSE heartbeat messages
        """
        while not self.is_cancelled and not self.error_occurred:
            await asyncio.sleep(self.heartbeat_interval)
            if self.is_timed_out():
                logger.warning(f"Stream timeout for conversation {self.conversation_id}")
                self.cancel()
                yield f"data: {json.dumps({'error': {'message': 'Stream timeout - no activity'}})}\n\n"
                break
            yield f": heartbeat {datetime.now(timezone.utc).isoformat()}\n\n"

    async def safe_stream_generator(
        self,
        stream: Union[Iterator, AsyncIterator],
        save_callback: Optional[callable] = None
    ) -> AsyncIterator[str]:
        """
        Safely generate streaming responses with error handling and cleanup.

        Args:
            stream: The stream to process (sync or async iterator)
            save_callback: Optional callback to save the full response

        Yields:
            SSE formatted messages
        """
        try:
            # Send initial metadata
            yield f"event: stream_start\ndata: {json.dumps({'conversation_id': self.conversation_id, 'model': self.model_name, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            self.update_activity()

            def iter_logical_lines(raw_chunk: str) -> List[str]:
                return raw_chunk.splitlines() if ("\n" in raw_chunk or raw_chunk.count("data:") > 1) else [raw_chunk]

            def append_content(text_piece: str) -> bool:
                if not text_piece:
                    return True
                chunk_size = len(text_piece.encode("utf-8"))
                if self.response_size + chunk_size > self.max_response_size:
                    return False
                self.full_response.append(text_piece)
                self.response_size += chunk_size
                return True

            def process_line(raw_line: str) -> Tuple[List[str], bool]:
                outputs: List[str] = []
                stripped_leading = raw_line.lstrip("\ufeff\u200b\u200c\u200d\u2060")
                candidate = stripped_leading.strip()
                if not candidate and not stripped_leading:
                    return outputs, False
                if candidate.startswith(":") or candidate.startswith("event:"):
                    return outputs, False
                if candidate.startswith("data:"):
                    payload_str = candidate[len("data:"):].strip()
                    if payload_str == "[DONE]":
                        outputs.append("data: [DONE]\n\n")
                        self.update_activity()
                        return outputs, True
                    try:
                        data = json.loads(payload_str)
                    except Exception:
                        outputs.append(f"data: {payload_str}\n\n")
                        self.update_activity()
                        return outputs, False
                    if isinstance(data, dict) and "error" in data:
                        try:
                            outputs.append(f"data: {json.dumps({'error': data.get('error')})}\n\n")
                        except Exception:
                            outputs.append(f"data: {json.dumps({'error': {'message': 'Upstream error'}})}\n\n")
                        self.error_occurred = True
                        return outputs, True
                    if isinstance(data, dict):
                        choices = data.get("choices")
                        if isinstance(choices, list) and choices:
                            for choice in choices:
                                delta = choice.get("delta") or {}
                                tool_calls_delta = delta.get("tool_calls")
                                if tool_calls_delta:
                                    self._accumulate_tool_calls(tool_calls_delta)
                                function_call_delta = delta.get("function_call")
                                if function_call_delta:
                                    self._accumulate_function_call(function_call_delta)
                                if "content" in delta and delta["content"] is not None:
                                    text_piece = str(delta["content"])
                                    try:
                                        if self.text_transform:
                                            text_piece = self.text_transform(text_piece)
                                    except StopStreamWithError as stopper:
                                        err_payload = {
                                            "error": {
                                                "message": str(stopper) or "Stream blocked by policy",
                                                "type": stopper.error_type,
                                            }
                                        }
                                        # Combine error and DONE into a single chunk to ensure clients see DONE
                                        combined = f"data: {json.dumps(err_payload)}\n\n" + "data: [DONE]\n\n"
                                        outputs.append(combined)
                                        self.done_sent = True
                                        self.error_occurred = True
                                        return outputs, True
                                    except StopIteration:
                                        return outputs, True
                                    except Exception as transform_err:
                                        logger.debug(f"text_transform error ignored: {transform_err}")
                                    if text_piece and not append_content(text_piece):
                                        outputs.append(
                                            f"data: {json.dumps({'error': {'message': 'Response size limit exceeded'}})}\n\n"
                                        )
                                        self.error_occurred = True
                                        return outputs, True
                                    delta["content"] = text_piece
                            outputs.append(f"data: {json.dumps(data)}\n\n")
                            self.update_activity()
                            return outputs, False
                    outputs.append(f"data: {json.dumps(data)}\n\n")
                    self.update_activity()
                    return outputs, False
                # Non-SSE chunk: preserve spaces (avoid stripping)
                text_piece = stripped_leading
                try:
                    text_piece = str(text_piece)
                except Exception:
                    pass
                try:
                    if self.text_transform:
                        text_piece = self.text_transform(text_piece)
                except StopStreamWithError as stopper:
                    err_payload = {
                        "error": {
                            "message": str(stopper) or "Stream blocked by policy",
                            "type": stopper.error_type,
                        }
                    }
                    combined = f"data: {json.dumps(err_payload)}\n\n" + "data: [DONE]\n\n"
                    outputs.append(combined)
                    self.done_sent = True
                    self.error_occurred = True
                    return outputs, True
                except StopIteration:
                    return outputs, True
                except Exception as transform_err:
                    logger.debug(f"text_transform error ignored: {transform_err}")
                if text_piece and not append_content(text_piece):
                    outputs.append(f"data: {json.dumps({'error': {'message': 'Response size limit exceeded'}})}\n\n")
                    self.error_occurred = True
                    return outputs, True
                if text_piece:
                    outputs.append(
                        f"data: {json.dumps({'choices': [{'delta': {'content': text_piece}}]})}\n\n"
                    )
                    self.update_activity()
                return outputs, False

            # Process the stream
            if hasattr(stream, '__aiter__'):
                # Async iterator
                async for chunk in stream:
                    if self.is_cancelled:
                        logger.info(f"Stream processing cancelled for {self.conversation_id}")
                        break

                    if self.is_timed_out():
                        logger.warning(f"Stream timeout during processing for {self.conversation_id}")
                        yield f"data: {json.dumps({'error': {'message': 'Stream timeout'}})}\n\n"
                        break

                    try:
                        raw_str = chunk.decode('utf-8', errors='replace') if isinstance(chunk, bytes) else str(chunk)
                        stop_stream = False
                        for logical_line in iter_logical_lines(raw_str):
                            outputs, should_stop = process_line(logical_line)
                            for out in outputs:
                                yield out
                            if should_stop:
                                stop_stream = True
                                break
                        if stop_stream:
                            break
                    except Exception as e:
                        logger.error(f"Error processing stream chunk for {self.conversation_id}: {e}")
                        self.error_occurred = True
                        yield f"data: {json.dumps({'error': {'message': f'Error processing chunk: {str(e)}'}})}\n\n"
                        break
            else:
                # Sync iterator
                def sync_iterator():
                    try:
                        for chunk in stream:
                            if self.is_cancelled:
                                break
                            yield chunk
                    except StopIteration:
                        pass

                for chunk in sync_iterator():
                    if self.is_cancelled:
                        break

                    if self.is_timed_out():
                        logger.warning(f"Stream timeout during sync processing for {self.conversation_id}")
                        yield f"data: {json.dumps({'error': {'message': 'Stream timeout'}})}\n\n"
                        break

                    try:
                        raw_str = chunk.decode('utf-8', errors='replace') if isinstance(chunk, bytes) else str(chunk)
                        stop_stream = False
                        for logical_line in iter_logical_lines(raw_str):
                            outputs, should_stop = process_line(logical_line)
                            for out in outputs:
                                yield out
                            if should_stop:
                                stop_stream = True
                                break
                        if stop_stream:
                            break
                    except Exception as e:
                        logger.error(f"Error processing sync stream chunk for {self.conversation_id}: {e}")
                        self.error_occurred = True
                        yield f"data: {json.dumps({'error': {'message': f'Error processing chunk: {str(e)}'}})}\n\n"
                        break

        except asyncio.CancelledError:
            # Client disconnected
            logger.info(f"Client disconnected from stream for {self.conversation_id}")
            self.cancel()
        except GeneratorExit:
            # Generator is being closed; do not yield anything here
            logger.info(f"Stream generator closed for {self.conversation_id}")
            self.cancel()
            # Re-raise to ensure proper generator closure semantics
            raise
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error in stream for {self.conversation_id}: {e}", exc_info=True)
            self.error_occurred = True
            yield f"data: {json.dumps({'error': {'message': f'Stream error: {str(e)}'}})}\n\n"

        finally:
            # Cleanup and final message
            try:
                # Always attempt to close the upstream stream first
                try:
                    if hasattr(stream, "aclose") and callable(getattr(stream, "aclose")):
                        # Async generator
                        await stream.aclose()  # type: ignore[attr-defined]
                    elif hasattr(stream, "close") and callable(getattr(stream, "close")):
                        # Sync generator
                        stream.close()  # type: ignore[attr-defined]
                except Exception:
                    # Best effort; ignore cleanup errors
                    pass

                # If cancelled (e.g., client disconnect or generator close), do not yield or await further
                if self.is_cancelled:
                    return

                if not self.is_cancelled:
                    # Send completion marker(s). If error occurred, still send [DONE] for graceful finish.
                    if not self.error_occurred:
                        done_payload = {
                            "id": f"chatcmpl-{datetime.now(timezone.utc).timestamp()}",
                            "object": "chat.completion.chunk",
                            "created": int(datetime.now(timezone.utc).timestamp()),
                            "model": self.model_name,
                            "choices": [{"delta": {}, "finish_reason": "stop", "index": 0}],
                            "conversation_id": self.conversation_id
                        }
                        yield f"data: {json.dumps(done_payload)}\n\n"
                    # Emit terminal DONE sentinel and mark it as sent to avoid duplicates
                    yield "data: [DONE]\n\n"
                    self.done_sent = True

                # Save the full response/tool calls if callback provided (only when not cancelled)
                has_output = self.has_accumulated_output()
                if (
                    not self.is_cancelled
                    and save_callback
                    and not self.error_occurred
                    and has_output
                ):
                    full_text = "".join(self.full_response)
                    aggregated_tool_calls = self.get_accumulated_tool_calls()
                    aggregated_function_call = self.get_accumulated_function_call()
                    try:
                        # Support flexible callback signatures (text only or extended)
                        maybe_result = None
                        try:
                            maybe_result = save_callback(
                                full_text,
                                aggregated_tool_calls,
                                aggregated_function_call,
                            )
                        except TypeError:
                            maybe_result = save_callback(full_text)
                        if hasattr(maybe_result, "__await__"):
                            await maybe_result
                        logger.info(
                            "Saved streaming response for %s (text_len=%d, tool_calls=%d, function_call=%s)",
                            self.conversation_id,
                            len(full_text),
                            len(aggregated_tool_calls or []),
                            "yes" if aggregated_function_call else "no",
                        )
                    except Exception as e:
                        logger.error(f"Failed to save streaming response for {self.conversation_id}: {e}")

                # Send stream end event (only when not cancelled)
                if not self.is_cancelled:
                    yield f"event: stream_end\ndata: {json.dumps({'conversation_id': self.conversation_id, 'success': not self.error_occurred, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                    # Ensure final [DONE] sentinel for client compatibility (unless already sent)
                    if not self.done_sent:
                        yield "data: [DONE]\n\n"
                        self.done_sent = True

            except Exception as e:
                logger.error(f"Error in stream cleanup for {self.conversation_id}: {e}")


async def create_streaming_response_with_timeout(
    stream: Union[Iterator, AsyncIterator],
    conversation_id: str,
    model_name: str,
    save_callback: Optional[callable] = None,
    idle_timeout: int = STREAMING_IDLE_TIMEOUT,
    heartbeat_interval: int = HEARTBEAT_INTERVAL,
    text_transform: Optional[callable] = None,
) -> AsyncIterator[str]:
    """
    Create a streaming response with timeout and error handling.

    Args:
        stream: The stream to process
        conversation_id: ID of the conversation
        model_name: Name of the model
        save_callback: Optional callback to save the response
        idle_timeout: Timeout for idle connections
        heartbeat_interval: Interval for heartbeat messages

    Yields:
        SSE formatted messages
    """
    handler = StreamingResponseHandler(
        conversation_id=conversation_id,
        model_name=model_name,
        idle_timeout=idle_timeout,
        heartbeat_interval=heartbeat_interval,
        text_transform=text_transform,
    )

    # Create tasks for streaming and heartbeat using persistent generator instances
    async def stream_with_heartbeat():
        stream_gen = handler.safe_stream_generator(stream, save_callback)
        heartbeat_gen = handler.heartbeat_generator()

        stream_task: Optional[asyncio.Task] = asyncio.create_task(stream_gen.__anext__())
        heartbeat_task: Optional[asyncio.Task] = asyncio.create_task(heartbeat_gen.__anext__())

        try:
            while not handler.is_cancelled and not handler.error_occurred:
                done, pending = await asyncio.wait(
                    {stream_task, heartbeat_task},
                    return_when=asyncio.FIRST_COMPLETED
                )

                should_exit = False
                for task in done:
                    try:
                        result = task.result()
                        if task is stream_task:
                            # Stream chunk
                            if result is not None:
                                yield result
                            # Schedule next chunk
                            stream_task = asyncio.create_task(stream_gen.__anext__())
                        else:
                            # Heartbeat
                            if result is not None:
                                yield result
                            # Schedule next heartbeat
                            heartbeat_task = asyncio.create_task(heartbeat_gen.__anext__())
                    except StopAsyncIteration:
                        # A generator ended naturally; exit the loop without flagging cancel
                        should_exit = True
                    except asyncio.CancelledError:
                        # Task was cancelled (likely due to shutdown); exit loop
                        should_exit = True
                    except Exception as e:
                        logger.error(f"Error in streaming task: {e}")
                        handler.error_occurred = True
                        should_exit = True

                # Do not cancel pending tasks on normal loop progression; keep them running

                if should_exit:
                    # Also cancel the latest scheduled tasks in case we created replacements
                    for t in (stream_task, heartbeat_task):
                        if t is not None and not t.done():
                            t.cancel()
                    gather_targets = tuple(filter(None, (stream_task, heartbeat_task)))
                    if gather_targets:
                        try:
                            await asyncio.gather(*gather_targets, return_exceptions=True)
                        except Exception:
                            pass
                    # As a safety net, emit a final [DONE] only if it hasn't been sent yet
                    try:
                        if not handler.done_sent and not handler.is_cancelled:
                            yield "data: [DONE]\n\n"
                            handler.done_sent = True
                    except Exception:
                        pass
                    break
        finally:
            # Ensure any pending tasks are cancelled and awaited exactly once
            remaining_tasks = [t for t in (stream_task, heartbeat_task) if t is not None]
            for task in remaining_tasks:
                if not task.done():
                    task.cancel()
            if remaining_tasks:
                try:
                    await asyncio.gather(*remaining_tasks, return_exceptions=True)
                except Exception:
                    pass
            # Ensure generators are properly closed; avoid yielding here
            try:
                await stream_gen.aclose()
            except Exception:
                pass
            try:
                await heartbeat_gen.aclose()
            except Exception:
                pass

    async for message in stream_with_heartbeat():
        yield message


class StopStreamWithError(Exception):
    """Signal the streaming handler to stop after emitting an SSE error payload."""
    def __init__(self, message: str = "Stream blocked by policy", error_type: str = "stream_error"):
        super().__init__(message)
        self.error_type = error_type


#
# End of streaming_utils.py
#######################################################################################################################
