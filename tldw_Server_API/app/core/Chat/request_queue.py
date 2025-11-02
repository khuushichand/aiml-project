# request_queue.py
# Description: Request queuing system with backpressure and priority management
#
# Imports
import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from heapq import heappush, heappop
from typing import Any, Dict, Optional, Callable, Tuple
from loguru import logger
from collections import deque
from concurrent.futures import ThreadPoolExecutor

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

        logger.info(f"Started {num_workers} queue workers")

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
        logger.debug(f"Worker {worker_id} started")

        while self._running:
            try:
                # Get next request from queue
                request = await self._get_next_request()
                if not request:
                    # No requests; wait until enqueued instead of polling
                    await self._has_items.wait()
                    # Loop will attempt to fetch again
                    continue

                # Check if request has timed out
                if time.time() - request.timestamp > self.timeout:
                    logger.warning(f"Request {request.request_id} timed out in queue")
                    request.future.set_exception(
                        TimeoutError(f"Request timed out after {self.timeout}s in queue")
                    )
                    continue

                # Process request
                async with self._processing_semaphore:
                    self.processing_count += 1
                    try:
                        # Execute the actual request processing
                        # This would be replaced with actual chat processing
                        result = await self._process_request(request)
                        request.future.set_result(result)
                        self.total_processed += 1
                    except Exception as e:
                        logger.error(f"Error processing request {request.request_id}: {e}")
                        request.future.set_exception(e)
                    finally:
                        self.processing_count -= 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)

        logger.debug(f"Worker {worker_id} stopped")

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
            logger.debug(f"Processing request {request.request_id} (no processor; admission-only)")
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

        logger.debug(f"Processing request {request.request_id} with processor; streaming={request.streaming}")
        loop = asyncio.get_running_loop()

        # Non-streaming: run processor in dedicated thread executor to avoid blocking loop
        if not request.streaming:
            try:
                result = await loop.run_in_executor(
                    self._executor,
                    lambda: request.processor(*request.processor_args, **request.processor_kwargs)
                )
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
            try:
                async for chunk in async_iter:
                    try:
                        await request.stream_channel.put(chunk)
                    except Exception as ch_e:
                        logger.warning(f"Failed to enqueue stream chunk for {request.request_id}: {ch_e}")
                        break
            finally:
                # Signal completion
                try:
                    await request.stream_channel.put(None)
                except Exception:
                    pass

        def _pump_sync_iterator(sync_iter):
            try:
                for chunk in sync_iter:
                    try:
                        asyncio.run_coroutine_threadsafe(request.stream_channel.put(chunk), loop)
                    except Exception as ch_e:
                        logger.warning(f"Failed to enqueue stream chunk (sync) for {request.request_id}: {ch_e}")
                        break
            finally:
                try:
                    asyncio.run_coroutine_threadsafe(request.stream_channel.put(None), loop)
                except Exception:
                    pass

        # Run the processor to obtain the stream (potentially blocking)
        try:
            stream = await loop.run_in_executor(
                self._executor, lambda: request.processor(*request.processor_args, **request.processor_kwargs)
            )
        except Exception as e:
            # Emit SSE-style error payload to channel to gracefully end downstream streaming
            sanitized = str(e).replace("\\", " ").replace("\n", " ")
            err_msg = f'data: {{"error": {{"message": "{sanitized}"}}}}\n\n'
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
            sanitized_stream_error = str(e).replace("\\", " ").replace("\n", " ")
            try:
                await request.stream_channel.put(
                    f'data: {{"error": {{"message": "Stream error: {sanitized_stream_error}"}}}}\n\n'
                )
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
            ValueError: If queue is full
        """
        async with self._lock:
            # Check queue size (backpressure)
            if len(self.queue) >= self.max_queue_size:
                self.total_rejected += 1
                raise ValueError(f"Queue full: {len(self.queue)} requests pending")

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

            logger.debug(f"Enqueued request {request_id} with priority {priority.name}")

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
            self.queue.clear()
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

    def _check_rate_limit(self, client_id: str) -> bool:
        """
        Check if request is within rate limits.

        Args:
            client_id: Client identifier

        Returns:
            True if within limits, False otherwise
        """
        current_time = time.time()
        minute_ago = current_time - 60

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
            return False

        # Check per-client rate limit
        client_requests = self.client_request_times.get(client_id, [])
        if len(client_requests) >= self.per_client_rate_limit:
            return False

        # Record request time
        self.global_request_times.append(current_time)
        if client_id not in self.client_request_times:
            self.client_request_times[client_id] = []
        self.client_request_times[client_id].append(current_time)

        return True

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
        # Check rate limits
        if not self._check_rate_limit(client_id):
            raise ValueError(f"Rate limit exceeded for client {client_id}")

        if processor_kwargs is None:
            processor_kwargs = {}

        # Proceed with normal enqueue
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
