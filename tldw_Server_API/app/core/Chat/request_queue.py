# request_queue.py
# Description: Request queuing system with backpressure and priority management
#
# Imports
import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import IntEnum
from heapq import heappush, heappop
from typing import Any, Dict, Optional, Callable, Tuple
from loguru import logger
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from functools import partial

#######################################################################################################################
#
# Types:

class RequestPriority(IntEnum):
    """Request priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4

@dataclass(order=True)
class QueuedRequest:
    """Represents a queued request with priority."""
    priority: int
    timestamp: float = field(compare=False)
    request_id: str = field(compare=False)
    request_data: Any = field(compare=False)
    future: asyncio.Future = field(compare=False)
    client_id: str = field(compare=False)
    estimated_tokens: int = field(compare=False, default=0)
    # Optional processor for actual work execution
    processor: Optional[Callable[..., Any]] = field(compare=False, default=None)
    processor_args: Tuple[Any, ...] = field(compare=False, default_factory=tuple)
    processor_kwargs: Dict[str, Any] = field(compare=False, default_factory=dict)
    streaming: bool = field(compare=False, default=False)
    # For streaming jobs, a channel to emit provider chunks (bytes or str). Sentinel None indicates end.
    stream_channel: Optional[asyncio.Queue] = field(compare=False, default=None)

#######################################################################################################################
#
# Classes:

class RequestQueue:
    """
    Priority-based request queue with backpressure management.
    """

    def __init__(
        self,
        max_queue_size: int = 100,
        max_concurrent: int = 10,
        timeout: float = 300.0
    ):
        """
        Initialize the request queue.

        Args:
            max_queue_size: Maximum number of queued requests
            max_concurrent: Maximum concurrent processing
            timeout: Request timeout in seconds
        """
        self.max_queue_size = max_queue_size
        self.max_concurrent = max_concurrent
        self.timeout = timeout

        self.queue = []  # Priority queue
        self.processing_count = 0
        self.total_processed = 0
        self.total_rejected = 0
        # Track active request IDs to prevent duplicates
        self._active_request_ids: set = set()

        self._lock = asyncio.Lock()
        self._processing_semaphore = asyncio.Semaphore(max_concurrent)
        self._workers = []
        self._running = False
        # Rolling recent activity (last N jobs)
        self._recent_activity = deque(maxlen=200)
        # Event to wake workers when new items arrive (avoids polling delay)
        self._has_items = asyncio.Event()
        # Dedicated thread pool for processor execution to reduce scheduling variance
        # and guarantee at-most max_concurrent worker threads.
        self._executor = ThreadPoolExecutor(max_workers=max(1, int(max_concurrent)))

    async def start(self, num_workers: int = 4):
        """
        Start the queue workers.

        Args:
            num_workers: Number of worker tasks
        """
        if self._running:
            return

        self._running = True
        # Ensure event starts cleared
        self._has_items.clear()
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)

        # Pre-warm the dedicated executor to reduce first-run latency for processors
        try:
            warm_n = max(1, min(self.max_concurrent, num_workers))
            loop = asyncio.get_running_loop()
            await asyncio.gather(*[
                loop.run_in_executor(self._executor, lambda: None)
                for _ in range(warm_n)
            ])
        except Exception:
            pass

        logger.info("Started {} queue workers", num_workers)

    async def stop(self):
        """Stop the queue workers."""
        self._running = False

        # Cancel all workers
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        try:
            self._executor.shutdown(wait=True)
        except Exception:
            pass

        logger.info("Stopped queue workers")

    def is_running(self) -> bool:
        """Return True if the queue has active worker tasks processing items."""
        if not self._running:
            return False
        alive = False
        for worker in list(self._workers):
            try:
                if not worker.done():
                    alive = True
                    break
            except Exception:
                alive = True
                break
        if not alive:
            self._running = False
        return alive

    async def _worker(self, worker_id: str):
        """
        Worker task that processes queued requests.

        Args:
            worker_id: Worker identifier
        """
        logger.debug("Worker {} started", worker_id)

        # Timeout for waiting on empty queue (60 seconds) - prevents indefinite waits
        wait_timeout = 60.0

        while self._running:
            try:
                # Get next request from queue
                request = await self._get_next_request()
                if not request:
                    # No requests; wait until enqueued instead of polling, with timeout
                    try:
                        await asyncio.wait_for(self._has_items.wait(), timeout=wait_timeout)
                    except asyncio.TimeoutError:
                        # Timeout is expected when queue is idle; just continue loop
                        continue
                    # Loop will attempt to fetch again
                    continue

                # Check if request has timed out
                if time.time() - request.timestamp > self.timeout:
                    logger.warning(f"Request {request.request_id} timed out in queue")
                    try:
                        request.future.set_exception(
                            TimeoutError(f"Request timed out after {self.timeout}s in queue")
                        )
                    except asyncio.InvalidStateError:
                        logger.debug(f"Future already resolved for timed-out request {request.request_id}")
                    # Clean up request ID for timed-out requests
                    async with self._lock:
                        self._active_request_ids.discard(request.request_id)
                    continue

                # Process request
                async with self._processing_semaphore:
                    self.processing_count += 1
                    process_succeeded = False
                    try:
                        # Check if the request was cancelled before starting
                        if request.future.cancelled():
                            logger.info(f"Request {request.request_id} was cancelled before processing")
                            process_succeeded = True  # Count as processed (client initiated cancel)
                            continue

                        # Execute the actual request processing
                        result = await self._process_request(request)

                        # Check if cancelled during processing
                        if request.future.cancelled():
                            logger.info(f"Request {request.request_id} was cancelled during processing")
                            process_succeeded = True
                            continue

                        try:
                            request.future.set_result(result)
                            process_succeeded = True
                        except asyncio.InvalidStateError:
                            # Future was already resolved (e.g., cancelled by client)
                            logger.debug(f"Future already resolved for request {request.request_id}")
                            process_succeeded = True  # Still count as processed
                    except asyncio.CancelledError:
                        # Request was cancelled - propagate but count as handled
                        logger.info(f"Request {request.request_id} processing was cancelled")
                        process_succeeded = True
                        raise
                    except Exception as e:
                        logger.error(f"Error processing request {request.request_id}: {e}")
                        try:
                            if not request.future.cancelled():
                                request.future.set_exception(e)
                        except asyncio.InvalidStateError:
                            logger.debug(f"Future already resolved for failed request {request.request_id}")
                    finally:
                        self.processing_count -= 1
                        # Update total_processed only when process completed (success or client cancelled)
                        if process_succeeded:
                            self.total_processed += 1
                        # Remove request ID from active tracking
                        async with self._lock:
                            self._active_request_ids.discard(request.request_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)

        logger.debug("Worker {} stopped", worker_id)

    async def _get_next_request(self) -> Optional[QueuedRequest]:
        """Get the next request from the priority queue."""
        async with self._lock:
            if self.queue:
                item = heappop(self.queue)
                # If queue becomes empty after pop, clear the wake event
                if not self.queue:
                    self._has_items.clear()
                return item
        return None

    async def _process_request(self, request: QueuedRequest) -> Any:
        """
        Process a request (placeholder for actual processing).

        Args:
            request: The request to process

        Returns:
            Processing result
        """
        # If a processor is provided, execute it; otherwise perform placeholder work
        start_ts = time.time()
        if request.processor is None:
            logger.debug(
                "Processing request {} (no processor; admission-only)",
                request.request_id,
            )
            duration = time.time() - start_ts
            # record activity
            self._recent_activity.append({
                "request_id": request.request_id,
                "client_id": request.client_id,
                "priority": request.priority,
                "streaming": request.streaming,
                "duration": duration,
                "result": "completed",
                "ts": time.time(),
            })
            return {"status": "completed", "request_id": request.request_id}

        logger.debug(
            "Processing request {} with processor; streaming={}",
            request.request_id,
            request.streaming,
        )
        loop = asyncio.get_running_loop()

        # Non-streaming: run processor in dedicated thread executor to avoid blocking loop
        if not request.streaming:
            try:
                fn = partial(
                    request.processor,
                    *request.processor_args,
                    **request.processor_kwargs,
                )
                result = await loop.run_in_executor(self._executor, fn)
                duration = time.time() - start_ts
                self._recent_activity.append({
                    "request_id": request.request_id,
                    "client_id": request.client_id,
                    "priority": request.priority,
                    "streaming": False,
                    "duration": duration,
                    "result": "completed",
                    "ts": time.time(),
                })
                return result
            except Exception as e:
                logger.error(f"Processor error for request {request.request_id}: {e}")
                self._recent_activity.append({
                    "request_id": request.request_id,
                    "client_id": request.client_id,
                    "priority": request.priority,
                    "streaming": False,
                    "duration": time.time() - start_ts,
                    "result": "error",
                    "error": str(e),
                    "ts": time.time(),
                })
                raise

        # Streaming path: processor should return an iterator (sync or async) that yields chunks
        if request.stream_channel is None:
            logger.error(f"Streaming job {request.request_id} missing stream_channel")
            raise RuntimeError("Streaming channel not provided for streaming job")

        async def _pump_async_iterator(async_iter):
            aiter = async_iter.__aiter__() if hasattr(async_iter, "__aiter__") else async_iter
            try:
                while True:
                    if request.future.cancelled() or loop.is_closed() or not self._running:
                        break
                    try:
                        chunk = await aiter.__anext__()
                    except StopAsyncIteration:
                        break
                    if request.future.cancelled() or loop.is_closed() or not self._running:
                        break
                    try:
                        await request.stream_channel.put(chunk)
                    except Exception as ch_e:
                        logger.warning(f"Failed to enqueue stream chunk for {request.request_id}: {ch_e}")
                        break
            finally:
                # Ensure async iterators are closed on cancellation or early exit
                try:
                    aclose = getattr(aiter, "aclose", None)
                    if callable(aclose):
                        await aclose()
                except Exception:
                    pass
                # Signal completion
                try:
                    await request.stream_channel.put(None)
                except Exception:
                    pass

        def _pump_sync_iterator(sync_iter):
            def _put_with_backpressure(item: Any) -> bool:
                try:
                    fut = asyncio.run_coroutine_threadsafe(request.stream_channel.put(item), loop)
                except Exception as ch_e:
                    logger.warning(f"Failed to enqueue stream chunk (sync) for {request.request_id}: {ch_e}")
                    return False
                while True:
                    try:
                        fut.result(timeout=1.0)
                        return True
                    except TimeoutError:
                        if request.future.cancelled() or loop.is_closed() or not self._running:
                            try:
                                fut.cancel()
                            except Exception:
                                pass
                            return False
                    except Exception as ch_e:
                        logger.warning(f"Failed to enqueue stream chunk (sync) for {request.request_id}: {ch_e}")
                        return False

            try:
                for chunk in sync_iter:
                    try:
                        if not _put_with_backpressure(chunk):
                            break
                    except Exception as ch_e:
                        logger.warning(f"Failed to enqueue stream chunk (sync) for {request.request_id}: {ch_e}")
                        break
            finally:
                try:
                    _put_with_backpressure(None)
                except Exception:
                    pass

        # Run the processor to obtain the stream (potentially blocking)
        try:
            fn = partial(
                request.processor,
                *request.processor_args,
                **request.processor_kwargs,
            )
            stream = await loop.run_in_executor(self._executor, fn)
        except Exception as e:
            # Emit SSE-style error payload to channel to gracefully end downstream streaming
            # Use json.dumps to properly escape the error message and prevent JSON injection
            error_payload = json.dumps({"error": {"message": str(e)[:500]}})
            err_msg = f'data: {error_payload}\n\n'
            try:
                await request.stream_channel.put(err_msg)
                await request.stream_channel.put("data: [DONE]\n\n")
                await request.stream_channel.put(None)
            except Exception:
                pass
            logger.error(f"Processor error starting stream for {request.request_id}: {e}")
            self._recent_activity.append({
                "request_id": request.request_id,
                "client_id": request.client_id,
                "priority": request.priority,
                "streaming": True,
                "duration": time.time() - start_ts,
                "result": "error",
                "error": str(e),
                "ts": time.time(),
            })
            raise

        # Pump stream depending on iterator type
        try:
            if hasattr(stream, "__aiter__"):
                await _pump_async_iterator(stream)
            else:
                # Sync iterator; run pumping in thread
                await loop.run_in_executor(self._executor, _pump_sync_iterator, stream)
            # For streaming jobs, return a simple status when pumping completes
            duration = time.time() - start_ts
            self._recent_activity.append({
                "request_id": request.request_id,
                "client_id": request.client_id,
                "priority": request.priority,
                "streaming": True,
                "duration": duration,
                "result": "stream_completed",
                "ts": time.time(),
            })
            return {"status": "stream_completed", "request_id": request.request_id}
        except Exception as e:
            # Best-effort to signal error and completion downstream
            # Use json.dumps to properly escape the error message and prevent JSON injection
            error_payload = json.dumps({"error": {"message": f"Stream error: {str(e)[:500]}"}})
            try:
                await request.stream_channel.put(f'data: {error_payload}\n\n')
                await request.stream_channel.put("data: [DONE]\n\n")
                await request.stream_channel.put(None)
            except Exception:
                pass
            logger.error(f"Streaming processor error for {request.request_id}: {e}")
            self._recent_activity.append({
                "request_id": request.request_id,
                "client_id": request.client_id,
                "priority": request.priority,
                "streaming": True,
                "duration": time.time() - start_ts,
                "result": "error",
                "error": str(e),
                "ts": time.time(),
            })
            raise

    async def enqueue(
        self,
        request_id: str,
        request_data: Any,
        client_id: str,
        priority: RequestPriority = RequestPriority.NORMAL,
        estimated_tokens: int = 0,
        *,
        processor: Optional[Callable[..., Any]] = None,
        processor_args: Tuple[Any, ...] = (),
        processor_kwargs: Optional[Dict[str, Any]] = None,
        streaming: bool = False,
        stream_channel: Optional[asyncio.Queue] = None,
    ) -> asyncio.Future:
        """
        Add a request to the queue.

        Args:
            request_id: Unique request identifier
            request_data: The request data
            client_id: Client identifier
            priority: Request priority
            estimated_tokens: Estimated token count for the request

        Returns:
            Future that will contain the result

        Raises:
            ValueError: If queue is full or request ID is duplicate
        """
        async with self._lock:
            # Check for duplicate request ID
            if request_id in self._active_request_ids:
                raise ValueError(f"Duplicate request ID: {request_id}")

            # Check queue size (backpressure)
            if len(self.queue) >= self.max_queue_size:
                self.total_rejected += 1
                raise ValueError(f"Queue full: {len(self.queue)} requests pending")

            # Track the request ID
            self._active_request_ids.add(request_id)

            # Create queued request
            future = asyncio.Future()
            if processor_kwargs is None:
                processor_kwargs = {}
            request = QueuedRequest(
                priority=priority.value,
                timestamp=time.time(),
                request_id=request_id,
                request_data=request_data,
                future=future,
                client_id=client_id,
                estimated_tokens=estimated_tokens,
                processor=processor,
                processor_args=processor_args,
                processor_kwargs=processor_kwargs,
                streaming=streaming,
                stream_channel=stream_channel,
            )

            # Add to priority queue
            heappush(self.queue, request)
            # Signal workers that items are available
            self._has_items.set()

            logger.debug(
                "Enqueued request {} with priority {}",
                request_id,
                priority.name,
            )

        return future

    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status.

        Returns:
            Dictionary with queue statistics
        """
        return {
            "queue_size": len(self.queue),
            "processing_count": self.processing_count,
            "max_queue_size": self.max_queue_size,
            "max_concurrent": self.max_concurrent,
            "total_processed": self.total_processed,
            "total_rejected": self.total_rejected,
            "is_running": self._running
        }

    def get_recent_activity(self, limit: Optional[int] = None) -> Any:
        """Return recent processed job summaries (most recent last)."""
        items = list(self._recent_activity)
        if limit is not None:
            items = items[-int(limit):]
        return items

    async def clear_queue(self):
        """Clear all pending requests."""
        async with self._lock:
            # Cancel all pending requests
            for request in self.queue:
                request.future.cancel()
                self._active_request_ids.discard(request.request_id)
            self.queue.clear()
            self._has_items.clear()
            logger.info("Cleared request queue")


class RateLimitedQueue(RequestQueue):
    """
    Request queue with rate limiting per client and globally.
    """

    def __init__(
        self,
        max_queue_size: int = 100,
        max_concurrent: int = 10,
        timeout: float = 300.0,
        global_rate_limit: int = 60,  # requests per minute
        per_client_rate_limit: int = 20  # requests per minute per client
    ):
        """
        Initialize rate-limited queue.

        Args:
            max_queue_size: Maximum queue size
            max_concurrent: Maximum concurrent processing
            timeout: Request timeout
            global_rate_limit: Global requests per minute
            per_client_rate_limit: Per-client requests per minute
        """
        super().__init__(max_queue_size, max_concurrent, timeout)

        self.global_rate_limit = global_rate_limit
        self.per_client_rate_limit = per_client_rate_limit

        # Track request times for rate limiting
        self.global_request_times = []
        self.client_request_times = {}
        # Lock for thread-safe rate limit state modifications
        self._rate_limit_lock = asyncio.Lock()

    async def _reserve_rate_limit(self, client_id: str) -> Optional[float]:
        """
        Reserve a rate limit slot for this client.

        This method is thread-safe and uses locking to prevent race conditions.
        It mutates the rate-limit state on success and returns the reservation
        timestamp so callers can roll back if downstream admission fails.

        Args:
            client_id: Client identifier

        Returns:
            Reservation timestamp if within limits, None otherwise
        """
        current_time = time.time()
        minute_ago = current_time - 60

        async with self._rate_limit_lock:
            # Clean old entries
            self.global_request_times = [
                t for t in self.global_request_times if t > minute_ago
            ]

            if client_id in self.client_request_times:
                self.client_request_times[client_id] = [
                    t for t in self.client_request_times[client_id] if t > minute_ago
                ]

            # Check global rate limit
            if len(self.global_request_times) >= self.global_rate_limit:
                return None

            # Check per-client rate limit
            client_requests = self.client_request_times.get(client_id, [])
            if len(client_requests) >= self.per_client_rate_limit:
                return None

            # Record request time
            self.global_request_times.append(current_time)
            if client_id not in self.client_request_times:
                self.client_request_times[client_id] = []
            self.client_request_times[client_id].append(current_time)

            return current_time

    async def _rollback_rate_limit(self, client_id: str, reservation_ts: float) -> None:
        """Rollback a previously reserved rate-limit slot."""
        async with self._rate_limit_lock:
            try:
                self.global_request_times.remove(reservation_ts)
            except ValueError:
                pass
            client_times = self.client_request_times.get(client_id, [])
            try:
                client_times.remove(reservation_ts)
            except ValueError:
                pass
            if client_times:
                self.client_request_times[client_id] = client_times
            else:
                self.client_request_times.pop(client_id, None)

    async def enqueue(
        self,
        request_id: str,
        request_data: Any,
        client_id: str,
        priority: RequestPriority = RequestPriority.NORMAL,
        estimated_tokens: int = 0,
        *,
        processor: Optional[Callable[..., Any]] = None,
        processor_args: Tuple[Any, ...] = (),
        processor_kwargs: Optional[Dict[str, Any]] = None,
        streaming: bool = False,
        stream_channel: Optional[asyncio.Queue] = None,
    ) -> asyncio.Future:
        """
        Add a request to the queue with rate limiting.

        Args:
            request_id: Unique request identifier
            request_data: The request data
            client_id: Client identifier
            priority: Request priority
            estimated_tokens: Estimated token count
            processor: Optional callable executed when the request is serviced
            processor_args: Positional args for the processor
            processor_kwargs: Keyword args for the processor
            streaming: Whether the request expects streaming output
            stream_channel: Channel used to emit streaming chunks

        Returns:
            Future that will contain the result

        Raises:
            ValueError: If queue is full or rate limit exceeded
        """
        # Reserve rate limit capacity (async with locking)
        reservation = await self._reserve_rate_limit(client_id)
        if reservation is None:
            raise ValueError(f"Rate limit exceeded for client {client_id}")

        if processor_kwargs is None:
            processor_kwargs = {}

        # Proceed with normal enqueue; roll back reservation if admission fails
        try:
            return await super().enqueue(
                request_id,
                request_data,
                client_id,
                priority,
                estimated_tokens,
                processor=processor,
                processor_args=processor_args,
                processor_kwargs=processor_kwargs,
                streaming=streaming,
                stream_channel=stream_channel,
            )
        except Exception:
            await self._rollback_rate_limit(client_id, reservation)
            raise


# Global queue instance
_request_queue: Optional[RateLimitedQueue] = None

def get_request_queue() -> Optional[RateLimitedQueue]:
    """Get the global request queue instance."""
    return _request_queue

def initialize_request_queue(
    max_queue_size: int = 100,
    max_concurrent: int = 10,
    global_rate_limit: int = 60,
    per_client_rate_limit: int = 20
) -> RateLimitedQueue:
    """
    Initialize the global request queue.

    Args:
        max_queue_size: Maximum queue size
        max_concurrent: Maximum concurrent processing
        global_rate_limit: Global rate limit
        per_client_rate_limit: Per-client rate limit

    Returns:
        The initialized queue
    """
    global _request_queue
    _request_queue = RateLimitedQueue(
        max_queue_size=max_queue_size,
        max_concurrent=max_concurrent,
        global_rate_limit=global_rate_limit,
        per_client_rate_limit=per_client_rate_limit
    )
    return _request_queue
