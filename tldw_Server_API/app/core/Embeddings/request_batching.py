# request_batching.py
# Request batching for improved throughput

import asyncio
import time
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from collections import deque
import uuid

from loguru import logger
from pydantic import BaseModel
from tldw_Server_API.app.core.Embeddings.simplified_config import get_config, ProviderConfig
from tldw_Server_API.app.core.Embeddings.metrics_integration import get_metrics
from tldw_Server_API.app.core.Embeddings.rate_limiter import get_async_rate_limiter


@dataclass
class BatchRequest:
    """Represents a single request in a batch"""
    request_id: str
    text: str
    model: str
    provider: str
    metadata: Dict[str, Any]
    future: asyncio.Future
    timestamp: float
    config_override: Optional[Dict[str, Any]] = None


class RequestBatcher:
    """
    Batches embedding requests for improved throughput.
    Collects requests and processes them in batches.
    """

    def __init__(self, config: Optional[Any] = None):
        """
        Initialize request batcher.

        Args:
            config: Optional configuration override
        """
        self.config = config or get_config()
        self.metrics = get_metrics()
        self.rate_limiter = get_async_rate_limiter()

        # Batching settings
        self.enabled = self.config.batching.enabled
        self.max_batch_size = self.config.batching.max_batch_size
        self.batch_timeout_ms = self.config.batching.batch_timeout_ms
        self.adaptive_batching = self.config.batching.adaptive_batching

        # Request queues per model
        self.queues: Dict[Tuple[str, str, str], deque] = {}
        self.processing_tasks: Dict[Tuple[str, str, str], asyncio.Task] = {}

        # Statistics
        self.stats = {
            'total_batches': 0,
            'total_requests': 0,
            'average_batch_size': 0,
            'average_wait_time': 0
        }

        # Adaptive batching parameters
        self.adaptive_params = {
            'current_batch_size': self.max_batch_size,
            'current_timeout': self.batch_timeout_ms,
            'throughput_history': deque(maxlen=10)
        }

        logger.info(
            f"Request batcher initialized: "
            f"enabled={self.enabled}, "
            f"max_batch_size={self.max_batch_size}, "
            f"timeout={self.batch_timeout_ms}ms"
        )

    async def submit_request(
        self,
        text: str,
        model: str,
        provider: str,
        metadata: Optional[Dict[str, Any]] = None,
        config_override: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Submit a request for batching.

        Args:
            text: Input text
            model: Model name
            provider: Provider name
            metadata: Optional metadata

        Returns:
            Embedding result when ready
        """
        metadata = metadata or {}
        user_id = metadata.get("user_id")

        if (
            user_id
            and getattr(self.config.security, "enable_rate_limiting", False)
        ):
            allowed, retry_after = await self.rate_limiter.check_rate_limit_async(user_id)
            if not allowed:
                tier = "free"
                limiter = getattr(self.rate_limiter, "rate_limiter", None)
                if limiter and getattr(limiter, "user_tiers", None):
                    tier = limiter.user_tiers.get(user_id, "free")
                try:
                    self.metrics.log_rate_limit_hit(user_id, tier)
                except Exception:
                    pass
                retry_after_msg = f" Retry after {retry_after}s." if retry_after else ""
                raise RuntimeError(
                    f"Rate limit exceeded for user '{user_id}'.{retry_after_msg}"
                )

        if not self.enabled:
            # Batching disabled, process immediately
            return await self._process_single(
                text,
                model,
                provider,
                metadata,
                config_override=config_override,
            )

        # Create request
        loop = asyncio.get_running_loop()
        request = BatchRequest(
            request_id=str(uuid.uuid4()),
            text=text,
            model=model,
            provider=provider,
            metadata=metadata,
            config_override=config_override,
            future=loop.create_future(),
            timestamp=time.time()
        )

        # Get or create queue for this model/config
        queue_key = self._queue_key(provider, model, config_override)
        if queue_key not in self.queues:
            self.queues[queue_key] = deque()

        task = self.processing_tasks.get(queue_key)
        if task is None or task.done():
            if task is not None and task.done():
                try:
                    reason = "cancelled" if task.cancelled() else f"finished (error={task.exception()})"
                except Exception:
                    reason = "finished"
                logger.debug(f"Restarting processing task for queue {self._queue_label(queue_key)}: previous task {reason}.")

            new_task = asyncio.create_task(self._process_queue(queue_key))
            self.processing_tasks[queue_key] = new_task

            def _remove_task(completed: asyncio.Task, key: str = queue_key) -> None:
                if self.processing_tasks.get(key) is completed:
                    self.processing_tasks.pop(key, None)

            new_task.add_done_callback(_remove_task)

        # Add to queue
        self.queues[queue_key].append(request)

        # Wait for result
        return await request.future

    async def _process_queue(self, queue_key: str):
        """
        Process requests from a queue.

        Args:
            queue_key: Queue identifier (provider:model)
        """
        queue = self.queues[queue_key]
        provider, model, _ = queue_key

        while True:
            try:
                # Collect batch
                batch = await self._collect_batch(queue)

                if not batch:
                    # No requests, wait a bit
                    await asyncio.sleep(0.01)
                    continue

                # Process batch
                await self._process_batch(batch, provider, model)

            except asyncio.CancelledError:
                logger.debug(f"Processing task for queue {queue_key} cancelled; shutting down.")
                raise
            except Exception as e:
                logger.error(f"Error processing batch queue {queue_key}: {e}")
                # Don't crash the processing task
                await asyncio.sleep(0.1)

    async def _collect_batch(self, queue: deque) -> List[BatchRequest]:
        """
        Collect requests into a batch.

        Args:
            queue: Request queue

        Returns:
            List of requests to process
        """
        batch = []
        start_time = time.time()

        # Determine batch parameters
        if self.adaptive_batching:
            max_size = self.adaptive_params['current_batch_size']
            timeout_ms = self.adaptive_params['current_timeout']
        else:
            max_size = self.max_batch_size
            timeout_ms = self.batch_timeout_ms

        timeout_seconds = timeout_ms / 1000.0

        # Collect requests until batch is full or timeout
        while len(batch) < max_size:
            if queue:
                batch.append(queue.popleft())
            else:
                # Queue empty, wait for more or timeout
                elapsed = time.time() - start_time

                if batch and elapsed >= timeout_seconds:
                    # Timeout reached with partial batch
                    break
                elif not batch:
                    # No requests yet, wait longer
                    await asyncio.sleep(0.001)

                    # Check timeout even for first request
                    if time.time() - start_time > timeout_seconds * 10:
                        break
                else:
                    # Have some requests, wait a bit more
                    remaining = timeout_seconds - elapsed
                    if remaining > 0:
                        await asyncio.sleep(min(0.001, remaining))
                    else:
                        break

        return batch

    async def _process_batch(
        self,
        batch: List[BatchRequest],
        provider: str,
        model: str
    ):
        """
        Process a batch of requests.

        Args:
            batch: List of requests
            provider: Provider name
            model: Model name
        """
        if not batch:
            return

        batch_start = time.time()

        try:
            # Extract texts
            texts = [req.text for req in batch]
            override_config = next(
                (req.config_override for req in batch if req.config_override is not None),
                None,
            )

            # Log batch metrics
            self.metrics.log_batch_size(provider, len(texts))

            # Process batch
            # Import here to avoid circular dependency
            from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
                create_embeddings_batch_async as embeddings_create_embeddings_batch_async,
            )

            # Create config for batch
            batch_config = override_config or self._build_user_app_config(provider, model)

            # Get embeddings
            embeddings = await embeddings_create_embeddings_batch_async(
                texts,
                batch_config,
                model_id_override=f"{provider}:{model}"
            )

            # Distribute results
            for i, req in enumerate(batch):
                if i < len(embeddings):
                    req.future.set_result(embeddings[i])
                else:
                    req.future.set_exception(
                        ValueError(f"No embedding returned for request {i}")
                    )

            # Update statistics
            batch_time = time.time() - batch_start
            wait_times = [batch_start - req.timestamp for req in batch]
            avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0

            self.stats['total_batches'] += 1
            self.stats['total_requests'] += len(batch)
            self.stats['average_batch_size'] = (
                self.stats['total_requests'] / self.stats['total_batches']
            )
            self.stats['average_wait_time'] = (
                self.stats['average_wait_time'] * 0.9 + avg_wait * 0.1
            )

            # Update adaptive parameters
            if self.adaptive_batching:
                self._update_adaptive_params(len(batch), batch_time)

            logger.debug(
                f"Processed batch: size={len(batch)}, "
                f"time={batch_time:.3f}s, "
                f"avg_wait={avg_wait:.3f}s"
            )

        except Exception as e:
            logger.error(f"Error processing batch: {e}")

            # Set error for all requests
            for req in batch:
                if not req.future.done():
                    req.future.set_exception(e)

    async def _process_single(
        self,
        text: str,
        model: str,
        provider: str,
        metadata: Optional[Dict[str, Any]] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Process a single request without batching.

        Args:
            text: Input text
            model: Model name
            provider: Provider name
            metadata: Optional metadata

        Returns:
            Embedding result
        """
        metadata = metadata or {}

        # If a config override is present we need to honour it by delegating
        # to the synchronous embedding loader, but we still do the work in an
        # executor so the event loop remains responsive.
        if config_override:
            loop = asyncio.get_running_loop()

            def _invoke_sync():
                from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import create_embedding

                return create_embedding(
                    text,
                    config_override,
                    model_id_override=f"{provider}:{model}",
                )

            return await loop.run_in_executor(None, _invoke_sync)

        # Try the async embedding service first so we avoid blocking.
        from tldw_Server_API.app.core.Embeddings.async_embeddings import get_async_embedding_service
        service = get_async_embedding_service()
        user_id = metadata.get("user_id")

        provider_candidates = []
        for candidate in (
            provider,
            self._normalize_provider_name(provider),
            self._alias_provider_name(provider),
        ):
            if candidate and candidate not in provider_candidates:
                provider_candidates.append(candidate)

        last_provider_error: Optional[ValueError] = None
        for candidate in provider_candidates:
            try:
                return await service.create_embedding(
                    text=text,
                    model=model,
                    provider=candidate,
                    user_id=user_id,
                    use_batching=False,
                )
            except ValueError as exc:
                last_provider_error = exc
                continue

        # Fall back to executor-based call if the async service cannot satisfy
        # the request (for example when the provider/model pair is not registered
        # in the async embedding config). This mirrors the legacy behaviour
        # without tying up the event loop.
        loop = asyncio.get_running_loop()

        def _invoke_sync_default():
            from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import create_embedding

            config = self._build_user_app_config(provider, model)
            return create_embedding(
                text,
                config,
                model_id_override=f"{provider}:{model}",
            )

        if last_provider_error:
            logger.debug(
                "Async provider resolution failed for provider '{provider}' (model '{model}'): {error}; falling back to executor path.",
                provider=provider,
                model=model,
                error=last_provider_error,
            )

        return await loop.run_in_executor(None, _invoke_sync_default)

    def _build_user_app_config(self, provider: str, model: str) -> Dict[str, Any]:
        """Construct full user app config for embeddings executor."""
        provider_config = None
        candidates = {
            provider,
            self._normalize_provider_name(provider),
        }
        alias = self._alias_provider_name(provider)
        if alias:
            candidates.add(alias)

        for candidate in candidates:
            provider_config = self.config.get_provider(candidate)
            if provider_config is not None:
                break
        if provider_config is None:
            raise ValueError(f"Provider '{provider}' is not configured for embeddings batching.")

        model_id = f"{provider}:{model}"

        normalized_provider = self._normalize_provider_name(provider)

        model_entry: Dict[str, Any] = {
            "provider": normalized_provider,
            "model_name_or_path": model
        }
        if provider_config.api_key:
            model_entry["api_key"] = provider_config.api_key
        if provider_config.api_url:
            model_entry["api_url"] = provider_config.api_url

        user_app_config: Dict[str, Any] = {
            "embedding_config": {
                "default_model_id": model_id,
                "models": {
                    model_id: model_entry
                }
            }
        }

        provider_section = self._build_provider_section(provider_config)
        if provider_section:
            user_app_config.update(provider_section)

        return user_app_config

    @staticmethod
    def _normalize_provider_name(provider: str) -> str:
        """Normalize provider identifiers for embedding config compatibility."""
        mapping = {
            "local": "local_api"
        }
        return mapping.get(provider.lower(), provider)

    @staticmethod
    def _alias_provider_name(provider: str) -> Optional[str]:
        """Return alternate configuration key for provider names."""
        mapping = {
            "local_api": "local",
            "local": "local_api",
        }
        return mapping.get(provider.lower())

    @staticmethod
    def _fingerprint_config(config: Optional[Dict[str, Any]]) -> str:
        """Return a stable fingerprint for a config override."""
        if config is None:
            return "__default__"

        def _normalize(value: Any) -> Any:
            if isinstance(value, BaseModel):
                return _normalize(value.model_dump())
            if isinstance(value, dict):
                return {key: _normalize(value[key]) for key in sorted(value.keys())}
            if isinstance(value, (list, tuple)):
                return [_normalize(v) for v in value]
            if isinstance(value, set):
                return sorted(_normalize(v) for v in value)
            if callable(value):
                return getattr(value, "__qualname__", repr(value))
            return value

        try:
            normalized = _normalize(config)
            payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
            return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
        except Exception as exc:
            try:
                logger.debug(f"Falling back to identity fingerprint for config override due to: {exc}")
            except Exception:
                pass
            return f"cfg_fallback:{id(config)}"

    def _queue_key(
        self,
        provider: str,
        model: str,
        config_override: Optional[Dict[str, Any]],
    ) -> Tuple[str, str, str]:
        """Build queue key incorporating provider, model, and config override."""
        return (provider, model, self._fingerprint_config(config_override))

    @staticmethod
    def _queue_label(queue_key: Tuple[str, str, str]) -> str:
        """Readable label for queue keys (for logging/tests)."""
        provider, model, fingerprint = queue_key
        return f"{provider}:{model}:{fingerprint}"

    @staticmethod
    def _build_provider_section(provider_config: ProviderConfig) -> Optional[Dict[str, Any]]:
        """Build provider-specific top-level config payload (e.g., API keys)."""
        section_key_map = {
            "openai": "openai_api",
            "huggingface": "huggingface_api",
            "local_api": "local_api",
            "local": "local_api"
        }

        section_key = section_key_map.get(provider_config.name.lower())
        if not section_key:
            return None

        section_payload: Dict[str, Any] = {}
        if provider_config.api_key:
            section_payload["api_key"] = provider_config.api_key
        if provider_config.api_url:
            section_payload["api_url"] = provider_config.api_url

        return {section_key: section_payload} if section_payload else None

    def _update_adaptive_params(self, batch_size: int, processing_time: float):
        """
        Update adaptive batching parameters based on performance.

        Args:
            batch_size: Size of processed batch
            processing_time: Time taken to process
        """
        # Calculate throughput
        throughput = batch_size / processing_time if processing_time > 0 else 0
        self.adaptive_params['throughput_history'].append(throughput)

        # Adjust parameters based on throughput trend
        if len(self.adaptive_params['throughput_history']) >= 3:
            recent = list(self.adaptive_params['throughput_history'])[-3:]
            avg_throughput = sum(recent) / len(recent)

            # If throughput is decreasing, reduce batch size
            if recent[-1] < avg_throughput * 0.9:
                self.adaptive_params['current_batch_size'] = max(
                    1,
                    int(self.adaptive_params['current_batch_size'] * 0.9)
                )
                logger.debug(
                    f"Reduced batch size to {self.adaptive_params['current_batch_size']}"
                )

            # If throughput is increasing, increase batch size
            elif recent[-1] > avg_throughput * 1.1:
                self.adaptive_params['current_batch_size'] = min(
                    self.max_batch_size,
                    int(self.adaptive_params['current_batch_size'] * 1.1)
                )
                logger.debug(
                    f"Increased batch size to {self.adaptive_params['current_batch_size']}"
                )

            # Adjust timeout based on batch filling rate
            if batch_size < self.adaptive_params['current_batch_size'] * 0.5:
                # Batches not filling, reduce timeout
                self.adaptive_params['current_timeout'] = max(
                    10,
                    int(self.adaptive_params['current_timeout'] * 0.9)
                )
            elif batch_size >= self.adaptive_params['current_batch_size']:
                # Batches filling completely, can increase timeout
                self.adaptive_params['current_timeout'] = min(
                    1000,
                    int(self.adaptive_params['current_timeout'] * 1.1)
                )

    def get_statistics(self) -> Dict[str, Any]:
        """Get batching statistics"""
        queue_sizes = {
            self._queue_label(key): len(queue) for key, queue in self.queues.items()
        }

        return {
            'enabled': self.enabled,
            'total_batches': self.stats['total_batches'],
            'total_requests': self.stats['total_requests'],
            'average_batch_size': self.stats['average_batch_size'],
            'average_wait_time': self.stats['average_wait_time'],
            'queue_sizes': queue_sizes,
            'adaptive_params': self.adaptive_params if self.adaptive_batching else None
        }

    async def flush_all_queues(self):
        """Force process all pending requests in queues"""
        for queue_key, queue in self.queues.items():
            if queue:
                provider, model, _ = queue_key
                batch = list(queue)
                queue.clear()
                await self._process_batch(batch, provider, model)

    async def shutdown(self):
        """Gracefully shutdown the batcher"""
        # Process remaining requests
        await self.flush_all_queues()

        # Cancel processing tasks
        current_loop = asyncio.get_running_loop()
        tasks_to_await: List[asyncio.Task] = []
        for task in list(self.processing_tasks.values()):
            task_loop = task.get_loop()
            if task_loop is current_loop:
                task.cancel()
                tasks_to_await.append(task)
            else:
                try:
                    if not task.done():
                        task_loop.call_soon_threadsafe(task.cancel)
                except Exception:
                    # Loop may already be closed; best effort cancellation
                    pass

        # Wait for tasks to complete
        if tasks_to_await:
            await asyncio.gather(*tasks_to_await, return_exceptions=True)
        self.processing_tasks.clear()

        logger.info("Request batcher shutdown complete")


# Global batcher instance
_batcher: Optional[RequestBatcher] = None


def get_batcher() -> RequestBatcher:
    """Get or create the global batcher instance."""
    global _batcher
    if _batcher is None:
        _batcher = RequestBatcher()
    return _batcher


# Convenience function for batched requests
async def create_embeddings_batch_async(
    texts: List[str],
    config: Dict[str, Any],
    model_id_override: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> List[List[float]]:
    """
    Create embeddings with automatic batching.

    Args:
        texts: List of input texts
        config: Configuration dictionary
        model_id_override: Optional model override

    Returns:
        List of embeddings
    """
    batcher = get_batcher()

    # Parse model info
    if model_id_override and ":" in model_id_override:
        provider, model = model_id_override.split(":", 1)
    else:
        # Use defaults from config
        provider = config.get("embedding_config", {}).get("default_provider", "openai")
        model = config.get("embedding_config", {}).get("default_model", "text-embedding-3-small")

    # Submit requests
    tasks = []
    for text in texts:
        task = batcher.submit_request(
            text,
            model,
            provider,
            metadata=metadata,
            config_override=config,
        )
        tasks.append(task)

    # Wait for all results
    results = await asyncio.gather(*tasks)

    return results
